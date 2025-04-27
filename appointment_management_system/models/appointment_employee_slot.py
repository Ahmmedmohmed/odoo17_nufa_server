# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta


class AppointmentEmployeeSlot(models.Model):
    _name = 'appointment.employee.slot'
    _description = 'Appointment Refund Policy'


    name = fields.Char(string='Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    time = fields.Float(string='Time', required=True)
    state = fields.Selection([('draft', 'Draft'), ('wait', 'Waiting'), ('done', 'Done')])


    @api.model
    def action_create_employee_slots(self):
        today = fields.Date.today()
        employee_ids = self.env['hr.employee'].search([('is_appointment_employee', '=', True)])

        for employee in employee_ids:
            time_plans = self.env['appointment.employee.time.plan'].search([('employee_id', '=', employee.id)])

            existing_slots = self.env['appointment.employee.slot'].search([('employee_id', '=', employee.id), ('date', '>=', today), ('date', '<=', today + timedelta(days=7))])
            existing_slot_keys = set((slot.date, slot.time) for slot in existing_slots)

            for plan in time_plans:
                day_of_week = plan.day
                start_time  = plan.start_hour * 60 + plan.start_minute
                end_time    = plan.end_hour * 60 + plan.end_minute

                for day_offset in range(10):
                    current_date = today + timedelta(days=day_offset)

                    if current_date.strftime('%A').lower() == day_of_week:
                        current_slot_start = start_time

                        while current_slot_start + 30 <= end_time:
                            slot_hour   = int(current_slot_start // 60)
                            slot_minute = int(current_slot_start % 60)
                            time_float  = slot_hour + (slot_minute / 60.0)

                            if (current_date, time_float) not in existing_slot_keys:
                                self.create({'name': f'{slot_hour:02d}:{slot_minute:02d}', 'employee_id': employee.id, 'date': current_date, 'time': time_float, 'state': 'draft'})
                                existing_slot_keys.add((current_date, time_float))

                            current_slot_start += 30