from odoo import fields, models


class SalePerson(models.Model):
    _inherit = 'pos.order'

    employee_id = fields.Many2one('hr.employee', string='SalesPerson')
    config_id = fields.Many2one('pos.config', string='Session Name')
    session_id = fields.Many2one('pos.session', string='Session ID')
    date_order = fields.Datetime(string='Date')
    amount_total = fields.Float(string='Total')

