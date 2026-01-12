# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HREmployee(models.Model):
    _inherit = 'hr.employee'


    is_appointment_employee = fields.Boolean(string='Appointment Employee')
    location_id = fields.Many2one('stock.location', string='Location')


    def action_available_in_appointment(self):
        self.write({'is_appointment_employee': True})


    def action_unavailable_in_appointment(self):
        self.write({'is_appointment_employee': False})