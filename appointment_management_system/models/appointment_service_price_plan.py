# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AppointmentServicePricePlan(models.Model):
    _name = 'appointment.service.price.plan'


    service_id    = fields.Many2one('product.product', string='Appointment Service')
    service_product_name = fields.Char(related='service_id.display_name', string='Appointment Product Service Name')
    department_id = fields.Many2one('hr.department', string='Appointment Department', required=True)
    branch_id   = fields.Many2one('res.company', string='Branch', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)

    service_slot_inside  = fields.Integer(string='Slot Number (Inside)')
    service_slot_outside = fields.Integer(string='Slot Number (Outside)')

    service_price_inside  = fields.Monetary(string='Price (Inside)')
    service_price_outside = fields.Monetary(string='Price (Outside)')