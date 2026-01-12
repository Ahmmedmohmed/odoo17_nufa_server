# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HRDepartment(models.Model):
    _inherit = 'hr.department'


    is_appointment_department = fields.Boolean(string='Appointment Department')
    is_times_confirmed = fields.Boolean(string='Is Times Confirmed')
    plan_ids = fields.One2many('appointment.department.time.plan', 'department_id', string='Associated Plans')


    def action_available_in_appointment(self):
        self.write({'is_appointment_department': True})

    def action_unavailable_in_appointment(self):
        self.write({'is_appointment_department': False})

    def action_confirm_times(self):
        self.write({'is_times_confirmed': True})


    @api.onchange('plan_ids')
    def action_unconfirm_times(self):
        self.write({'is_times_confirmed': False})