# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import datetime
import io
import json
import logging
import math
import re
import base64
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key

import markupsafe
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta

from odoo.addons.web.controllers.utils import clean_action
from odoo import models, fields, api, _, osv, _lt
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name
from itertools import groupby

_logger = logging.getLogger(__name__)

ACCOUNT_CODES_ENGINE_SPLIT_REGEX = re.compile(r"(?=[+-])")

ACCOUNT_CODES_ENGINE_TERM_REGEX = re.compile(
    r"^(?P<sign>[+-]?)"\
    r"(?P<prefix>([A-Za-z\d.]*|tag\([\w.]+\))((?=\\)|(?<=[^CD])))"\
    r"(\\\((?P<excluded_prefixes>([A-Za-z\d.]+,)*[A-Za-z\d.]*)\))?"\
    r"(?P<balance_character>[DC]?)$"
)

ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX = re.compile(r"tag\(((?P<id>\d+)|(?P<ref>\w+\.\w+))\)")

# Performance optimisation: those engines always will receive None as their next_groupby, allowing more efficient batching.
NO_NEXT_GROUPBY_ENGINES = {'tax_tags', 'account_codes'}

LINE_ID_HIERARCHY_DELIMITER = '|'

class AccountReport(models.Model):
    _inherit = 'account.report'

    # horizontal_group_ids = fields.Many2many(string="Horizontal Groups", comodel_name='account.report.horizontal.group')
    # footnotes_ids = fields.One2many(string="Footnotes", comodel_name='account.report.footnote', inverse_name='report_id')

    # Those fields allow case-by-case fine-tuning of the engine, for custom reports.
    # custom_handler_model_id = fields.Many2one(string='Custom Handler Model', comodel_name='ir.model')
    # custom_handler_model_name = fields.Char(string='Custom Handler Model Name', related='custom_handler_model_id.model')

    # Account Coverage Report
    # is_account_coverage_report_available = fields.Boolean(compute='_compute_is_account_coverage_report_available')

    filter_analytic_tags = fields.Boolean(string="Analytic Tag")

    # filter_analytic_groupby = fields.Boolean(
    #     string="Analytic Group By",
    #     compute=lambda x: x._compute_report_option_filter('filter_analytic_groupby'), readonly=False, store=True, depends=['root_report_id'],
    # )

    def _init_options_analytic_tag(self, options, previous_options=None):
        if not self.filter_analytic_tags:
            return


        if self.user_has_groups('analytic.group_analytic_accounting'):
            previous_analytic_tags = (previous_options or {}).get('analytic_accounts_tag', [])
            analytic_tag_ids = [int(x) for x in previous_analytic_tags]
            selected_analytic_tags = self.env['account.analytic.tag'].with_context(active_test=False).search([('id', 'in', analytic_tag_ids)])

            # options['display_analytic'] = True
            # options['analytic_accounts'] = selected_analytic_accounts.ids
            # options['selected_analytic_account_names'] = selected_analytic_accounts.mapped('name')


            # selected_analytic_tags = self.env['account.analytic.tag'].search([('id', '!=' , 0)])
            options['analytic_accounts_tag'] = selected_analytic_tags.ids
            options['selected_analytic_account_tags_names'] = selected_analytic_tags.mapped('name')


    # def _init_options_analytic_groupby(self, options, previous_options=None):
    #     if not self.filter_analytic_groupby:
    #         return
    #     enable_analytic_accounts = self.user_has_groups('analytic.group_analytic_accounting')
    #     if not enable_analytic_accounts:
    #         return

    #     options['display_analytic_groupby'] = True
    #     options['display_analytic_plan_groupby'] = True
       

    #     options['include_analytic_without_aml'] = (previous_options or {}).get('include_analytic_without_aml', False)
    #     previous_analytic_accounts = (previous_options or {}).get('analytic_accounts_groupby', [])
    #     analytic_account_ids = [int(x) for x in previous_analytic_accounts]
    #     selected_analytic_accounts = self.env['account.analytic.account'].with_context(active_test=False).search(
    #         [('id', 'in', analytic_account_ids)])
    #     options['analytic_accounts_groupby'] = selected_analytic_accounts.ids
    #     options['selected_analytic_account_groupby_names'] = selected_analytic_accounts.mapped('name')

    #     previous_analytic_plans = (previous_options or {}).get('analytic_plans_groupby', [])
    #     analytic_plan_ids = [int(x) for x in previous_analytic_plans]
    #     selected_analytic_plans = self.env['account.analytic.plan'].search([('id', 'in', analytic_plan_ids)])
    #     options['analytic_plans_groupby'] = selected_analytic_plans.ids
    #     options['selected_analytic_plan_groupby_names'] = selected_analytic_plans.mapped('name')

        # selected_analytic_tags = self.env['account.analytic.tag'].search([('id', '=' , 0)])
        # options['analytic_accounts_tag'] = selected_analytic_tags.ids
        # options['selected_analytic_account_tags_names'] = selected_analytic_tags.mapped('name')

        # self._create_column_analytic(options)

    
    #  mine
    def _get_options_domain(self, options, date_scope):
        self.ensure_one()

        available_scopes = dict(self.env['account.report.expression']._fields['date_scope'].selection)
        if date_scope and date_scope not in available_scopes: # date_scope can be passed to None explicitly to ignore the dates
            raise UserError(_("Unknown date scope: %s", date_scope))

        domain = [
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('company_id', 'in', self.get_report_company_ids(options)),
        ]
        domain += self._get_options_journals_domain(options)
        if date_scope:
            domain += self._get_options_date_domain(options, date_scope)
        domain += self._get_options_partner_domain(options)
        domain += self._get_options_all_entries_domain(options)
        domain += self._get_options_unreconciled_domain(options)
        domain += self._get_options_fiscal_position_domain(options)
        domain += self._get_options_account_type_domain(options)
        domain += self._get_options_analytic_tag_domain(options)
        domain += self._get_options_aml_ir_filters(options)
       

        if self.only_tax_exigible:
            domain += self.env['account.move.line']._get_tax_exigible_domain()

        return domain
    

    @api.model
    def _get_options_tags(self, options):
        selected_analytic_tags = [
            tag for tag in options.get('analytic_accounts_tag', [])]
        # if not tag['id'] in ('divider', 'group') and tag['selected']]
        
        # if not selected_analytic_tags:
           
        #     selected_analytic_tags = [
        #         journal for journal in options.get('journals', []) if
        #         not journal['id'] in ('divider', 'group')
        #     ]


        # return selected_analytic_tags
    @api.model
    def _get_options_analytic_tag_domain(self, options):
        all_domains = []
        selected_domains = []
        if not options.get('analytic_accounts_tag') or len(options.get('analytic_accounts_tag')) == 0:
            return []
        # selected_analytic_tags = self._get_options_tags(options)


        for opt in options.get('analytic_accounts_tag', []):
        #     if opt['id'] == 'trade_receivable':
            domain = [('analytic_tag_ids', '=', opt)]

            # elif opt['id'] == 'trade_payable':
            #     domain = [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'liability_payable')]
            # elif opt['id'] == 'non_trade_receivable':
            #     domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'asset_receivable')]
            # elif opt['id'] == 'non_trade_payable':
            #     domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'liability_payable')]
            # if opt['selected']:
            selected_domains.append(domain)
            all_domains.append(domain)
        return osv.expression.OR(selected_domains or all_domains)
    
    # @api.model
    # def _get_options_analytic_tag_domain(self, options):
    #     selected_analytic_tags = self._get_options_tags(options)
    #     return selected_analytic_tags and [('analytic_tag_ids', 'in', j) for j in selected_analytic_tags] or []
    


    def open_journal_items(self, options, params):
        ''' Open the journal items view with the proper filters and groups '''
        record_model, record_id = self._get_model_info_from_id(params.get('line_id'))
        view_id = self.env.ref(params['view_ref']).id if params.get('view_ref') else None

        ctx = {
            'search_default_group_by_account': 1,
            'search_default_posted': 0 if options.get('all_entries') else 1,
            'date_from': options.get('date').get('date_from'),
            'date_to': options.get('date').get('date_to'),
            'search_default_journal_id': params.get('journal_id', False),
            'expand': 1,
            'search_default_analytic_accounts_tag':options.get('analytic_accounts_tag')
        }

        if options['date'].get('date_from'):
            ctx['search_default_date_between'] = 1
        else:
            ctx['search_default_date_before'] = 1

        journal_type = params.get('journal_type')
        if journal_type:
            type_to_view_param = {
                'bank': {
                    'filter': 'search_default_bank',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id
                },
                'cash': {
                    'filter': 'search_default_cash',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id
                },
                'general': {
                    'filter': 'search_default_misc_filter',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_misc').id
                },
                'sale': {
                    'filter': 'search_default_sales',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_sales_purchases').id
                },
                'purchase': {
                    'filter': 'search_default_purchases',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_sales_purchases').id
                },
            }
            ctx.update({
                type_to_view_param[journal_type]['filter']: 1,
            })
            view_id = type_to_view_param[journal_type]['view_id']

        action_domain = [('display_type', 'not in', ('line_section', 'line_note'))]

        if record_id is None:
            # Default filters don't support the 'no set' value. For this case, we use a domain on the action instead
            model_fields_map = {
                'account.account': 'account_id',
                'res.partner': 'partner_id',
                'account.journal': 'journal_id',
            }
            model_field = model_fields_map.get(record_model)
            if model_field:
                action_domain += [(model_field, '=', False)]
        else:
            model_default_filters = {
                'account.account': 'search_default_account_id',
                'res.partner': 'search_default_partner_id',
                'account.journal': 'search_default_journal_id',
            }
            model_filter = model_default_filters.get(record_model)
            if model_filter:
                ctx.update({
                    'active_id': record_id,
                    model_filter: [record_id],
                })

        if options:
            for account_type in options.get('account_type', []):
                ctx.update({
                    f"search_default_{account_type['id']}": account_type['selected'] and 1 or 0,
                })

            if options.get('journals') and 'search_default_journal_id' not in ctx:
                selected_journals = [journal['id'] for journal in options['journals'] if journal.get('selected')]
                if len(selected_journals) == 1:
                    ctx['search_default_journal_id'] = selected_journals

            if options.get('analytic_accounts'):
                analytic_ids = [int(r) for r in options['analytic_accounts']]
                ctx.update({
                    'search_default_analytic_accounts': 1,
                    'analytic_ids': analytic_ids,
                })

            if options.get('analytic_accounts_tag'):
                analytic_tag_ids = [int(r) for r in options['analytic_accounts_tag']]
                ctx.update({
                    'search_default_analytic_accounts_tag': 1,
                    'analytic_tag_ids': analytic_tag_ids,
                })

        return {
            'name': self._get_action_name(params, record_model, record_id),
            'view_mode': 'tree,pivot,graph,kanban',
            'res_model': 'account.move.line',
            'views': [(view_id, 'list')],
            'type': 'ir.actions.act_window',
            'domain': action_domain,
            'context': ctx,
        }



    def get_report_information(self, options):
        """
        return a dictionary of information that will be consumed by the AccountReport component.
        """
        self.ensure_one()

        warnings = {}
        all_column_groups_expression_totals = self._compute_expression_totals_for_each_column_group(self.line_ids.expression_ids, options)

        # Convert all_column_groups_expression_totals to a json-friendly form (its keys are records)
        json_friendly_column_group_totals = self._get_json_friendly_column_group_totals(all_column_groups_expression_totals)

        return {
            'caret_options': self._get_caret_options(),
            'column_headers_render_data': self._get_column_headers_render_data(options),
            'column_groups_totals': json_friendly_column_group_totals,
            'context': self.env.context,
            'custom_display': self.env[self.custom_handler_model_name]._get_custom_display_config() if self.custom_handler_model_name else {},
            'filters': {
                'show_all': self.filter_unfold_all,
                'show_analytic': options.get('display_analytic', False),
                'show_analytic_groupby': options.get('display_analytic_groupby', False),
                'show_analytic_plan_groupby': options.get('display_analytic_plan_groupby', False),
                'show_draft': self.filter_show_draft,
                'show_hierarchy': options.get('display_hierarchy_filter', False),
                'show_period_comparison': self.filter_period_comparison,
                'show_totals': self.env.company.totals_below_sections and not options.get('ignore_totals_below_sections'),
                'show_unreconciled': self.filter_unreconciled,
                'show_hide_0_lines': self.filter_hide_0_lines,
                'display_analytic_tag_filter': self.filter_analytic_tags,
            },
            'footnotes': self.get_footnotes(options),
            'groups': {
                'analytic_accounting': self.user_has_groups('analytic.group_analytic_accounting'),
                'account_readonly': self.user_has_groups('account.group_account_readonly'),
                'account_user': self.user_has_groups('account.group_account_user'),
            },
            'lines': self._get_lines(options, all_column_groups_expression_totals=all_column_groups_expression_totals, warnings=warnings),
            'warnings': warnings,
            'report': {
                'company_name': self.env.company.name,
                'company_country_code': self.env.company.country_code,
                'name': self.name,
                'root_report_id': self.root_report_id,
            }
        }


    @api.model
    def format_value(self, options, value, currency=False, blank_if_zero=False, figure_type=None, digits=1):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        if value is None:
            return ''

        if figure_type == 'none':
            return value

        if isinstance(value, str) or figure_type == 'string':
            return str(value)

        if figure_type == 'monetary':
            if options.get('multi_currency'):
                digits = None
                currency = currency or self.env.company.currency_id
            else:
                digits = (currency or self.env.company.currency_id).decimal_places
                currency = None
        elif figure_type == 'integer':
            currency = None
            digits = 0
        elif figure_type == 'boolean':
            return _("Yes") if bool(value) else _("No")
        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount

