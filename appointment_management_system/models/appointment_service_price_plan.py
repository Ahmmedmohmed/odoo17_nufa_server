# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AppointmentServicePricePlan(models.Model):
    _name = 'appointment.service.price.plan'


    service_id  = fields.Many2one('product.template', string='Appointment Service')
    employee_id = fields.Many2one('hr.employee', string='Appointment Employee', required=True, domain=[('is_appointment_employee', '=', True)])
    branch_id   = fields.Many2one('res.company', string='Branch', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)

    service_duration_inside  = fields.Float(string='Duration (Inside)')
    service_duration_outside = fields.Float(string='Duration (Outside)')

    service_price_inside  = fields.Monetary(string='Price (Inside)')
    service_price_outside = fields.Monetary(string='Price (Outside)')