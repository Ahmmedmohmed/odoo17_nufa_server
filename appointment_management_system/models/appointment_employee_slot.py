# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta, datetime


class AppointmentEmployeeSlot(models.Model):
    _name = 'appointment.employee.slot'
    _description = 'Appointment Employee Slot'


    name = fields.Char(string='Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', required=True)
    time = fields.Float(string='Time', required=True)
    appointment_datetime = fields.Char(string='Appointment Datetime')
    state = fields.Selection([('draft', 'Draft'), ('wait', 'Waiting'), ('done', 'Done'), ('cancel', 'Cancelled')], default='draft')


    @api.model
    def auto_delete_old_slots(self):
        target_date = (datetime.today() - timedelta(days=20)).date()
        old_slots = self.search([('date', '<', str(target_date))])

        if old_slots:
            appointments_to_update = self.env['appointment.management'].search([
                ('slot_ids', 'in', old_slots.ids)
            ])
            for appointment in appointments_to_update:
                appointment.slot_ids = [(3, slot.id) for slot in old_slots if slot.id in appointment.slot_ids.ids]
            
            old_slots.unlink()


    @api.model
    def auto_reset_wait_to_draft(self):
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        records = self.search([('state', '=', 'wait'), ('write_date', '<=', ten_minutes_ago.strftime('%Y-%m-%d %H:%M:%S'))])
        if records:
            records.write({'state': 'draft'})


    def action_change_state_wait(self):
        for record in self:
            record.write({'state': 'wait'})


    def action_change_state_done(self):
        for record in self:
            record.write({'state': 'done'})


    def action_change_state_cancel(self):
        for record in self:
            record.write({'state': 'cancel'})


    @api.model
    def action_create_employee_slots(self):
        today = fields.Date.today()
        department_ids = self.env['hr.department'].search([('is_appointment_department', '=', True), ('is_times_confirmed', '=', True)])
        employee_ids = self.env['hr.employee'].search([('is_appointment_employee', '=', True), ('department_id', 'in', department_ids.ids)])

        for employee in employee_ids:
            time_plans = self.env['appointment.department.time.plan'].search([('department_id', '=', employee.department_id.id)])

            existing_slots = self.env['appointment.employee.slot'].search([('employee_id', '=', employee.id), ('date', '>=', today), ('date', '<=', today + timedelta(days=30))])
            existing_slot_keys = set((slot.date, slot.time) for slot in existing_slots)

            for plan in time_plans:
                day_of_week = plan.day
                start_time  = plan.start_hour * 60 + plan.start_minute
                end_time    = plan.end_hour * 60 + plan.end_minute

                for day_offset in range(35):
                    current_date = today + timedelta(days=day_offset)

                    if current_date.strftime('%A').lower() == day_of_week:
                        current_slot_start = start_time

                        while current_slot_start + 30 <= end_time:
                            slot_hour   = int(current_slot_start // 60)
                            slot_minute = int(current_slot_start % 60)
                            time_float  = slot_hour + (slot_minute / 60.0)

                            if (current_date, time_float) not in existing_slot_keys:
                                slot_name = f'{slot_hour:02d}:{slot_minute:02d}'
                                appt_dt = f'{current_date.strftime("%Y-%m-%d")} {slot_name}:00'
                                self.create({'name': slot_name, 'employee_id': employee.id, 'date': current_date, 'time': time_float, 'appointment_datetime': appt_dt, 'state': 'draft'})
                                existing_slot_keys.add((current_date, time_float))

                            current_slot_start += 30
