# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HREmployee(models.Model):
    _inherit = 'hr.employee'


    is_appointment_employee = fields.Boolean(string='Appointment Employee')
    is_plans_confirmed = fields.Boolean(string='Is Plans Confirmed')
    plan_ids = fields.One2many('appointment.employee.time.plan', 'employee_id', string='Associated Plans')


    def action_available_in_appointment(self):
        self.write({'is_appointment_employee': True})

    def action_unavailable_in_appointment(self):
        self.write({'is_appointment_employee': False})

    def action_confirm_plans(self):
        self.write({'is_plans_confirmed': True})

    @api.onchange('plan_ids')
    def action_unconfirm_plans(self):
        self.write({'is_plans_confirmed': False})