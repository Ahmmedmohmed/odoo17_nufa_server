# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AppointmentEmployeeTimePlan(models.Model):
    _name = "appointment.employee.time.plan"


    employee_id = fields.Many2one('hr.employee', string="Employee")
    day = fields.Selection([('saturday', 'Saturday'), ('sunday', 'Sunday'), ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday')], required=True)
    start_hour = fields.Integer(string="Start Hour")
    start_minute = fields.Integer(string="Start Minute")
    end_hour = fields.Integer(string="End Hour")
    end_minute = fields.Integer(string="End Minute")


    @api.constrains('start_hour', 'end_hour')
    def _check_hours_value(self):
        if not 1 <= self.start_hour <= 24:
            raise ValidationError(_('Hours Value Must Be Between (1 - 24).'))

        if not 1 <= self.end_hour <= 24:
            raise ValidationError(_('Hours Value Must Be Between (1 - 24).'))


    @api.constrains('start_minute')
    def _check_minutes_value(self):
        if not 0 <= self.start_minute <= 60:
            raise ValidationError(_('Minutes Value Must Be Between (0 - 60).'))

        if not 0 <= self.end_minute <= 60:
            raise ValidationError(_('Minutes Value Must Be Between (0 - 60).'))


    @api.constrains('start_hour', 'start_minute', 'end_hour', 'end_minute', 'day', 'employee_id')
    def _check_time_conflicts(self):
        for slot in self:
            start_total = (slot.start_hour * 60) + slot.start_minute
            end_total = (slot.end_hour * 60) + slot.end_minute

            if start_total >= end_total:
                raise ValidationError("End time must be after start time.")

            same_day_slots = self.search([('id', '!=', slot.id), ('employee_id', '=', slot.employee_id.id), ('day', '=', slot.day)])

            for other in same_day_slots:
                other_start = other.start_hour * 60 + other.start_minute
                other_end = other.end_hour * 60 + other.end_minute

                # Check for overlap
                if not (end_total <= other_start or start_total >= other_end):
                    raise ValidationError(
                        f"Time slot conflict with another slot on {slot.day}: "
                        f"{slot.start_hour}:{slot.start_minute:02d} - {slot.end_hour}:{slot.end_minute:02d} "
                        f"overlaps with {other.start_hour}:{other.start_minute:02d} - {other.end_hour}:{other.end_minute:02d}"
                    )