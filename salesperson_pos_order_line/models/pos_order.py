# -*- coding: utf-8 -*-

from odoo import fields, models, api


class PosOrderLine(models.Model):
    """ The class PosOrder is used to inherit pos.order.line """
    _inherit = 'pos.order.line'

    user_id = fields.Many2one('res.users', string='Salesperson',
                              help="You can see salesperson here")

    employee_id = fields.Many2one('hr.employee', string='SalesPerson',
                              help="You can see employees here")

    @api.constrains('employee_id')
    def employee_id_constrains(self):
        for rec in self:
            if rec.employee_id:
                rec.order_id.update({'employee_id': rec.employee_id.id})