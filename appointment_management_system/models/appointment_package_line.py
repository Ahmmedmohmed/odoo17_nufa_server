# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AppointmentPackageLine(models.Model):
    _name = 'appointment.package.line'


    product_id = fields.Many2one('product.product', string='Service Name', domain=[('is_appointment_service', '=', True), ('is_appointment_package', '=', False)])
    product_pack_id = fields.Many2one('product.product', string='Service Pack Name', domain=[('is_appointment_service', '=', True), ('is_appointment_package', '=', False)])


    department_id = fields.Many2one('hr.department', string='Appointment Department', required=True, domain=[('is_appointment_department', '=', True)])
    branch_id = fields.Many2one('res.company', string='Branch', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.user.company_id.currency_id.id)

    service_slot_inside   = fields.Integer(string='Slot Number (Inside)')
    service_slot_outside  = fields.Integer(string='Slot Number (Outside)')
    service_price_inside  = fields.Monetary(string='Price (Inside)')
    service_price_outside = fields.Monetary(string='Price (Outside)')
    
    # location_type = fields.Selection([
    #     ('inside', 'Inside'),
    #     ('outside', 'Outside'),
    #     ('both', 'Both')
    # ], string='Location Type', default='both', help="Control where this package service can be booked: Inside (At Branch only), Outside (At Your Location only), or Both")