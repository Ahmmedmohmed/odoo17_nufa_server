# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    resource_calendar_id = fields.Many2one(
        'resource.calendar',  # لازم نحدد اسم الموديل المربوط بيه
        required=True,
        default=lambda self: self.env.company.resource_calendar_id,
        check_company=False,  # 🚀 السطر السحري اللي هيفك القيود بين الفروع
        help="Employee's working schedule."
    )


    is_appointment_employee = fields.Boolean(string='Appointment Employee')
    location_id = fields.Many2one('stock.location', string='Location')


    def action_available_in_appointment(self):
        self.write({'is_appointment_employee': True})


    def action_unavailable_in_appointment(self):
        self.write({'is_appointment_employee': False})