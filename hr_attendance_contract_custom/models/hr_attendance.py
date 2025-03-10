# -*- coding: utf-8 -*-

import pytz
from odoo import models, fields, api
from datetime import datetime, timedelta


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
    _description = 'Hr Attendance Custom'

    att_date = fields.Date("Attendance Date")
    over_time = fields.Float("Over Time", readonly=True, compute='_compute_attendances', store=True)
    act_late_in = fields.Float("Late Hours", readonly=True, compute='_compute_attendances', store=True)
    act_diff_time = fields.Float("Diff Hours", readonly=True, compute='_compute_attendances', store=True)
    late_in = fields.Float("Late Penalty")
    diff_time = fields.Float("Diff Penalty")
    is_weekend = fields.Integer("Weekend", readonly=True, compute='_compute_attendances', store=True)
    is_public_holiday = fields.Integer("Public Holiday", readonly=True, compute='_compute_attendances', store=True)
    is_tamper = fields.Integer("Tamper", readonly=True, compute='_compute_attendances', store=True)

    _sql_constraints = [('unique_attendance_date', 'UNIQUE(employee_id, att_date)', 'Attendance date already exists')]

    def get_attendances(self):
        self._compute_attendances(False)

    @api.depends('check_in', 'check_out', 'employee_id', 'att_date')
    def _compute_attendances(self, compute=True):

        # Get a list of unique employee IDs from the 'self' records
        employee_ids = self.env['hr.employee'].search([('id', 'in', self.mapped('employee_id.id'))])
        for employee_id in employee_ids:

            # Get employee's resource calendar, contract, and attendance policy
            calendar_id = employee_id.resource_calendar_id
            if calendar_id:
                calendar_attendance_ids = self.env['resource.calendar.attendance'].search(
                    [('calendar_id', '=', calendar_id.id)])
                if not calendar_attendance_ids:
                    continue
            else:
                continue
            contract_id = self.env['hr.contract'].search([('employee_id', '=', employee_id.id),
                                                          ('state', 'in', ['open', 'close'])])
            policy_id = contract_id[-1].att_policy_id if contract_id else False

            # Get employee's time zone for accurate time calculations
            tz = pytz.timezone(employee_id.tz)

            # Filter the 'self' records to those belonging to the current employee
            employee_records = self.filtered(lambda x: x.employee_id.id == employee_id.id).sorted(
                key=lambda x: x.check_in)

            late_cnt = []
            diff_cnt = []
            for rec in employee_records:

                if not rec.check_in or not rec.check_out:
                    continue

                # Convert check-in/out times to the employee's time zone for accurate comparison
                actual_check_in_tz = pytz.utc.localize(rec.check_in).astimezone(tz)
                actual_check_out_tz = pytz.utc.localize(rec.check_out).astimezone(tz)

                # Format timestamps for comparison
                actual_check_in = actual_check_in_tz.strftime("%Y-%m-%d %H:%M:%S")
                actual_check_in = datetime.strptime(actual_check_in, "%Y-%m-%d %H:%M:%S")
                actual_check_out = actual_check_out_tz.strftime("%Y-%m-%d %H:%M:%S")
                actual_check_out = datetime.strptime(actual_check_out, "%Y-%m-%d %H:%M:%S")

                # Calculate Attendance Date
                if not rec.att_date:
                    if min(calendar_attendance_ids.mapped('hour_from')) < 3 and actual_check_in.hour > 18:
                        att_date = actual_check_in.date() + timedelta(days=1)
                    elif calendar_id.is_2days and actual_check_in.hour < 18:
                        att_date = actual_check_in.date() - timedelta(days=1)
                    elif round(max(calendar_attendance_ids.mapped('hour_to')), 2) >= 21 and actual_check_in.hour < 9:
                        att_date = actual_check_in.date() - timedelta(days=1)
                    elif round(max(calendar_attendance_ids.mapped('hour_to')), 2) < 21 and actual_check_in.hour < 6:
                        att_date = actual_check_in.date() - timedelta(days=1)
                    else:
                        att_date = actual_check_in.date()
                else:
                    att_date = rec.att_date

                # Extract the weekday (0-6) from the check-out time
                day_num = att_date.weekday()

                check_in_list = []
                check_out_list = []

                # Find matching attendance records from the calendar for the current day
                for calendar_attendance_id in calendar_attendance_ids:
                    if calendar_attendance_id.day_period == 'lunch':
                        continue
                    if calendar_attendance_id.date_from and calendar_attendance_id.date_to:
                        if (calendar_attendance_id.dayofweek == str(day_num)
                                and calendar_attendance_id.date_from <= att_date <= calendar_attendance_id.date_to):
                            check_in_list.append(calendar_attendance_id.hour_from)
                            check_out_list.append(calendar_attendance_id.hour_to)
                        else:
                            continue
                    elif calendar_attendance_id.date_from:
                        if calendar_attendance_id.dayofweek == str(
                                day_num) and att_date >= calendar_attendance_id.date_from:
                            check_in_list.append(calendar_attendance_id.hour_from)
                            check_out_list.append(calendar_attendance_id.hour_to)
                        else:
                            continue
                    else:
                        if calendar_attendance_id.dayofweek == str(day_num):
                            check_in_list.append(calendar_attendance_id.hour_from)
                            check_out_list.append(calendar_attendance_id.hour_to)
                        else:
                            continue

                # Determine planned check-in/out times based on calendar attendance
                if len(check_in_list) > 1:
                    if not calendar_id.is_2days:
                        in_minutes = min(check_in_list) % 1 * 60
                        out_minutes = max(check_out_list) % 1 * 60

                        if min(check_in_list) == 24:
                            planned_check_in = datetime(att_date.year, att_date.month, att_date.day,
                                                        0, 0, 0)
                        else:
                            planned_check_in = datetime(att_date.year, att_date.month, att_date.day,
                                                        int(min(check_in_list)), int(in_minutes))
                        if max(check_out_list) == 24:
                            planned_check_out = datetime(att_date.year, att_date.month, att_date.day,
                                                         23, 59, 59)
                        else:
                            planned_check_out = datetime(att_date.year, att_date.month, att_date.day,
                                                         int(max(check_out_list)), int(out_minutes))

                    else:
                        next_d = att_date + timedelta(days=1)
                        in_minutes = max(check_in_list) % 1 * 60
                        out_minutes = min(check_out_list) % 1 * 60

                        planned_check_in = datetime(att_date.year, att_date.month, att_date.day,
                                                    int(max(check_in_list)), int(in_minutes))
                        planned_check_out = datetime(next_d.year, next_d.month, next_d.day, int(min(check_out_list)),
                                                     int(out_minutes))
                else:
                    in_minutes = check_in_list[0] % 1 * 60 if check_in_list else None
                    out_minutes = check_out_list[0] % 1 * 60 if check_out_list else None

                    planned_check_in = datetime(att_date.year, att_date.month, att_date.day, int(check_in_list[0]),
                                                int(in_minutes)) if check_in_list else None
                    planned_check_out = datetime(att_date.year, att_date.month, att_date.day, int(check_out_list[0]),
                                                 int(out_minutes)) if check_out_list else None

                # Calculate late arrival
                if planned_check_in is not None and actual_check_in > planned_check_in:
                    late_in = (actual_check_in - planned_check_in).seconds / 3600
                else:
                    late_in = 0

                # Calculate early departure
                if planned_check_out is not None and planned_check_out > actual_check_out:
                    diff_time = (planned_check_out - actual_check_out).seconds / 3600
                else:
                    diff_time = 0

                # Calculate Overtime Hours in work days
                if planned_check_out is not None and planned_check_out < actual_check_out:
                    over_time = (actual_check_out - planned_check_out).seconds / 3600
                else:
                    over_time = 0

                # Identify weekend based on missing planned times with actual check-in/out
                if planned_check_in is None:
                    is_weekend = 1
                    over_time = rec.worked_hours
                else:
                    is_weekend = 0

                # Identify public holiday
                public_holidays = rec.env['resource.calendar.leaves'].search(
                    [('company_id', '=', rec.employee_id.company_id.id), ('resource_id', '=', None),
                     ('holiday_id', '=', None), '|', ('calendar_id', '=', calendar_id.id),
                     ('calendar_id', '=', None)])
                is_public_holiday = 0
                for ph in public_holidays:
                    if not is_weekend:
                        if ph.date_from.date() <= att_date <= ph.date_to.date():
                            is_public_holiday = 1
                            over_time = rec.worked_hours
                            late_in = 0
                            diff_time = 0
                            break

                # Identify check-in/out tamper
                if (actual_check_out - actual_check_in).seconds / 3600 < 2:
                    is_tamper = 1
                    over_time = 0
                    if planned_check_in and planned_check_out:
                        if actual_check_in <= planned_check_in:
                            tamper_out = True
                        elif planned_check_in < actual_check_in < planned_check_out:
                            tamper_out = True if ((actual_check_in - planned_check_in).seconds <
                                                  (planned_check_out - actual_check_in).seconds) else False
                        else:
                            tamper_out = False

                        if tamper_out:
                            diff_time = 0
                        else:
                            late_in = 0
                else:
                    is_tamper = 0

                # Delegate calculations to attendance policy for potential grace periods, etc.
                if not policy_id or compute:
                    values = {
                        'over_time': over_time,
                        'act_late_in': late_in,
                        'act_diff_time': diff_time,
                        'is_weekend': is_weekend,
                        'is_public_holiday': is_public_holiday,
                        'is_tamper': is_tamper,
                    }
                    rec.write(values)

                    if not rec.att_date:
                        rec.att_date = att_date

                else:
                    float_late, late_cnt = policy_id.get_late(late_in, late_cnt)
                    float_diff, diff_cnt = policy_id.get_diff(diff_time, diff_cnt)

                    values = {
                        'late_in': float_late,
                        'diff_time': float_diff,
                    }
                    rec.write(values)

                    if not rec.att_date:
                        rec.att_date = att_date
