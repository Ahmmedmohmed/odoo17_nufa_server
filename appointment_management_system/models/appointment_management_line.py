# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AppointmentManagementLine(models.Model):
    _name = 'appointment.management.line'
    _description = 'Appointment Management Line'
    _check_company_auto = True
    _rec_name = 'appointment_id'


    product_id   = fields.Many2one('product.product', string='Service', domain=[('product_tmpl_id.is_appointment_service', '=', True)], required=True)
    employee_id  = fields.Many2one('hr.employee', string='Employee', required=True)
    quantity     = fields.Integer('Quantity', required=True)
    price_unit   = fields.Float('Unit Price', required=True)
    service_rate = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], string='Rating', required=True)
    company_id   = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    appointment_id = fields.Many2one('appointment.management', string='Appointment', required=True)