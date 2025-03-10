from odoo import fields, models

class AccountReport(models.Model):
    _inherit = 'account.report'

    # horizontal_group_ids = fields.Many2many(string="Horizontal Groups", comodel_name='account.report.horizontal.group')
    # footnotes_ids = fields.One2many(string="Footnotes", comodel_name='account.report.footnote', inverse_name='report_id')

    # custom_handler_model_id = fields.Many2one(string='Custom Handler Model', comodel_name='ir.model')
    # custom_handler_model_name = fields.Char(string='Custom Handler Model Name', related='custom_handler_model_id.model')

    # is_account_coverage_report_available = fields.Boolean(compute='_compute_is_account_coverage_report_available')
    filter_analytic_tags = fields.Boolean(string="Analytic Tag")