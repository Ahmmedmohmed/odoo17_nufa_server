# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models, Command
from odoo.osv import expression
from odoo.tools.misc import formatLang

import markupsafe
import uuid

class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    def _line_value_changed_analytic_tag_ids(self, line):
        self.ensure_one()
        self._lines_turn_auto_balance_into_manual_line(line)



class BankRecWidgetLine(models.Model):
    _inherit = "bank.rec.widget.line"

    # This model is never saved inside the database.
    # _auto=False' & _table_query = "0" prevent the ORM to create the corresponding postgresql table.

    analytic_tag_ids = fields.Many2many(
        comodel_name='account.analytic.tag',
        compute='_compute_analytic_tag_ids',
        store=True,
        readonly=False,
    )

    @api.depends('source_aml_id')
    def _compute_analytic_tag_ids(self):
        for line in self:
            if line.flag in ('aml', 'new_aml', 'liquidity', 'exchange_diff'):
                line.analytic_tag_ids = line.source_aml_id.analytic_tag_ids
            else:
                line.analytic_tag_ids = line.analytic_tag_ids


    
  
    def _get_aml_values(self, **kwargs):
        self.ensure_one()
        return {
            'name': self.name,
            'account_id': self.account_id.id,
            'currency_id': self.currency_id.id,
            'amount_currency': self.amount_currency,
            'balance': self.debit - self.credit,
            'reconcile_model_id': self.reconcile_model_id.id,
            'analytic_distribution': self.analytic_distribution,
            'tax_repartition_line_id': self.tax_repartition_line_id.id,
            'tax_ids': [Command.set(self.tax_ids.ids)],
            'tax_tag_ids': [Command.set(self.tax_tag_ids.ids)],
            'group_tax_id': self.group_tax_id.id,
            'analytic_tag_ids': self.analytic_tag_ids,
            **kwargs,
        }
