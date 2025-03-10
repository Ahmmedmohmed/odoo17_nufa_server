# -*- coding: utf-8 -*-

import pytz
from datetime import datetime, timedelta
import logging
import os
import platform
import subprocess

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
try:
    from zk import ZK, const
except ImportError:
    _logger.error("Unable to import pyzk library. Try 'pip3 install pyzk'.")


class ZkMachine(models.Model):
    _name = 'zk.machine'

    name = fields.Char(string='Machine IP', required=True)
    port_no = fields.Integer(string='Port No', required=True, default="4370")
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    zk_timeout = fields.Integer(string='ZK Timeout', required=True, default="120")
    zk_after_date = fields.Datetime(string='Attend Start Date',
                                    help='If provided, Attendance module will ignore records before this date.')

    def device_connect(self, zkobj):
        try:
            conn = zkobj.connect()
            return conn
        except:
            _logger.info("zk.exception.ZKNetworkError: can't reach device.")
            raise UserError("Connection To Device cannot be established.")
            return False

    def try_connection(self):
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = info.zk_timeout
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'title': _("Leads Assigned"),
                        'message': 'Biometric Device is Up/Reachable.',
                        'next': {
                            'type': 'ir.actions.act_window_close'
                        },
                    }
                }
            else:
                raise UserError("Biometric Device is Down/Unreachable.")

    def clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = info.zk_timeout
                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
                conn = self.device_connect(zk)
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    if clear_data:
                        # conn.clear_attendance()
                        self._cr.execute("""delete from zk_machine_attendance""")
                        conn.disconnect()
                        raise UserError(_('Attendance Records Deleted.'))
                    else:
                        raise UserError(_('Unable to clear Attendance log. Are you sure attendance log is not empty.'))
                else:
                    raise UserError(
                        _('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))
            except:
                raise ValidationError(
                    'Unable to clear Attendance log. Are you sure attendance device is connected & record is not empty.')

    def zkgetuser(self, zk):
        try:
            users = zk.get_users()
            return users
        except:
            raise UserError(_('Unable to get Users.'))

    def cron_download(self):
        machines = self.env['zk.machine'].search([])
        for machine in machines:
            machine.download_attendance()

    def download_attendance(self):
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = info.zk_timeout
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=True)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                # conn.disable_device() #Device Cannot be used during this time.
                try:
                    users = conn.get_users()
                except:
                    users = False
                try:
                    attendance = conn.get_attendance()
                except:
                    attendance = False

                if attendance:
                    for each in attendance:
                        atten_time = each.timestamp
                        atten_time = datetime.strptime(atten_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')

                        if info.zk_after_date == False:
                            tmp_zk_after_date = datetime.strptime('2024-01-01', "%Y-%m-%d")
                        else:
                            tmp_zk_after_date = datetime.strptime(str(info.zk_after_date), '%Y-%m-%d %H:%M:%S')

                        if atten_time != False and atten_time > tmp_zk_after_date:
                            local_tz = pytz.timezone(
                                self.env.user.partner_id.tz or 'GMT')
                            local_dt = local_tz.localize(atten_time, is_dst=None)
                            utc_dt = local_dt.astimezone(pytz.utc)
                            utc_dt = utc_dt.strftime("%Y-%m-%d %H:%M:%S")

                            atten_time = datetime.strptime(utc_dt, "%Y-%m-%d %H:%M:%S")
                            atten_time = fields.Datetime.to_string(atten_time)
                            if users:
                                # print("EACH>>>", each.punch, each.status, each.timestamp, each.uid, each.user_id)
                                for uid in users:
                                    if uid.user_id == each.user_id:
                                        get_user_id = self.env['hr.employee'].sudo().search(
                                            [('device_id', '=', each.user_id)])
                                        if get_user_id:
                                            duplicate_atten_ids = zk_attendance.sudo().search(
                                                [('device_id', '=', each.user_id), ('punching_time', '=', atten_time)])
                                            if duplicate_atten_ids:
                                                continue
                                            else:
                                                zk_attendance.create({'employee_id': get_user_id.id,
                                                                      'punching_time': atten_time,
                                                                      'device_id': each.user_id,
                                                                      # 'attendance_type': str(each.status),
                                                                      # 'punch_type': str(each.punch),
                                                                      'address_id': info.address_id.id})
                                    else:
                                        pass
                                else:
                                    pass
                # conn.enable_device() #Enable Device Once Done.
                conn.disconnect
                self._calculate_check_in_out()
                return True

            else:
                raise UserError(_('No attendances found in Attendance Device to Download.'))
                # conn.enable_device() #Enable Device Once Done.
                conn.disconnect

        else:
            raise UserError(
                _('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))

    def _get_all_dates(self, start_date, end_date):
        all_dates = []
        for n in range((end_date - start_date).days + 1):
            date_to_add = start_date + timedelta(days=n)
            all_dates.append(date_to_add)
        return all_dates

    def _calculate_check_in_out(self):
        """
            Calculates check-in and check-out times for employees based on punching data
            and their work schedules.

            This method retrieves unprocessed punching data from the previous day,
            iterates through employees and their work schedules,
            compares punching times with planned work hours, and creates 'hr.attendance'
            records if punches fall within a reasonable range.
            """

        # Find unprocessed punching data from yesterday
        if not self.env.context.get('recalc'):
            zk_att_obj = self.env['zk.machine.attendance'].sudo().search(
                [('is_sent', '!=', True)])
        else:
            zk_att_obj = self.env['zk.machine.attendance'].sudo().search(
                [('is_sent', '=', True)])

        if zk_att_obj:
            # Model for creating attendance records
            att_obj = self.env['hr.attendance']

            # Get employee IDs from punching data
            employee_ids = zk_att_obj.mapped('employee_id')

            # Find the date range covered by the punching data
            start_date = min(zk_att_obj.mapped('punching_time')).date() - timedelta(days=1)
            end_date = max(zk_att_obj.mapped('punching_time')).date()

            # Get all dates within the range (for iterating)
            get_dates = self._get_all_dates(start_date, end_date)

            for employee in employee_ids:
                # Get employee's work calendar
                calendar_attendance_ids = self.env['resource.calendar.attendance'].search(
                    [('calendar_id', '=', employee.resource_calendar_id.id)])

                # Employee's time zone
                tz = pytz.timezone(employee.tz)

                for d in get_dates:
                    check_in_list = []
                    check_out_list = []

                    # Extract the weekday (0-6) from the check-out time
                    day_num = d.weekday()

                    # Find planned check-in and check-out times for the day
                    for line in calendar_attendance_ids:
                        if line.day_period == 'lunch':
                            continue

                        # Check if the planned work hours fall within the current date
                        elif line.date_from and line.date_to and line.date_from <= d <= line.date_to:
                            if line.dayofweek == str(day_num):
                                check_in_list.append(line.hour_from)
                                check_out_list.append(line.hour_to)
                        elif line.date_from and d >= line.date_from:
                            if line.dayofweek == str(day_num):
                                check_in_list.append(line.hour_from)
                                check_out_list.append(line.hour_to)
                        elif line.dayofweek == str(day_num):
                            check_in_list.append(line.hour_from)
                            check_out_list.append(line.hour_to)
                        else:
                            check_in_list.append(line.hour_from)
                            check_out_list.append(line.hour_to)

                    # Logic for handling 2-day work schedules
                    if employee.resource_calendar_id.is_2days:
                        next_d = d + timedelta(days=1)
                        in_minutes = max(check_in_list) % 1 * 60
                        out_minutes = min(check_out_list) % 1 * 60

                        # Construct planned check-in and check-out times considering minutes
                        planned_in = datetime(d.year, d.month, d.day, int(max(check_in_list)), int(in_minutes))
                        planned_out = datetime(next_d.year, next_d.month, next_d.day, int(min(check_out_list)),
                                               int(out_minutes))
                    else:
                        in_minutes = min(check_in_list) % 1 * 60
                        out_minutes = max(check_out_list) % 1 * 60

                        if min(check_in_list) == 24:
                            planned_in = datetime(d.year, d.month, d.day, 0, 0, 0)
                        else:
                            planned_in = datetime(d.year, d.month, d.day, int(min(check_in_list)), int(in_minutes))

                        if max(check_out_list) == 24:
                            planned_out = datetime(d.year, d.month, d.day, 23, 59, 59)
                        else:
                            planned_out = datetime(d.year, d.month, d.day, int(max(check_out_list)), int(out_minutes))

                    # Convert planned times to employee's time zone and UTC
                    local_dt_in = tz.localize(planned_in, is_dst=None)
                    local_dt_out = tz.localize(planned_out, is_dst=None)
                    utc_dt_in = local_dt_in.astimezone(pytz.utc)
                    utc_dt_out = local_dt_out.astimezone(pytz.utc)

                    # Format timestamps for comparison
                    planned_check_in = utc_dt_in.strftime("%Y-%m-%d %H:%M:%S")
                    planned_check_in = datetime.strptime(planned_check_in, "%Y-%m-%d %H:%M:%S")
                    planned_check_out = utc_dt_out.strftime("%Y-%m-%d %H:%M:%S")
                    planned_check_out = datetime.strptime(planned_check_out, "%Y-%m-%d %H:%M:%S")

                    start_list = []  # Punches for potential starting shift on previous day (2-day schedules)
                    in_list = []  # Punches within planned check-in
                    out_list = []  # Punches within planned check-out
                    for rec in zk_att_obj:
                        if rec.employee_id.id == employee.id:
                            diff_hours_in = (rec.punching_time.timestamp() - planned_check_in.timestamp()) / 60 / 60
                            diff_hour_out = (rec.punching_time.timestamp() - planned_check_out.timestamp()) / 60 / 60

                            # Check if punch falls within a reasonable window
                            if 3.0 >= diff_hours_in >= -3.0 and (not rec.is_sent or self.env.context.get('recalc')):
                                in_list.append(rec.punching_time)
                                rec.is_sent = True
                            elif 9.0 >= diff_hour_out >= -3.0 and (not rec.is_sent or self.env.context.get('recalc')):
                                out_list.append(rec.punching_time)
                                rec.is_sent = True
                            else:
                                continue
                        else:
                            continue

                    # Find the earliest check-in and latest check-out
                    check_in = min(in_list) if in_list else False
                    check_out = max(out_list) if out_list else False

                    # Create attendance record if check-in and check-out are valid
                    if check_in and check_out and check_out > check_in:
                        vals = {
                            'att_date': d,
                            'check_in': check_in,
                            'check_out': check_out,
                            'employee_id': employee.id,
                        }
                        duplicate_record = att_obj.search([('employee_id', '=', employee.id), ('att_date', '=', d)])

                        if duplicate_record and duplicate_record.check_in > check_in:
                            # print("check_in....", duplicate_record.check_in, d)
                            duplicate_record.sudo().write({'check_in': check_in})
                        elif duplicate_record and duplicate_record.check_out < check_out:
                            # print("check_out....", duplicate_record.check_out, d)
                            duplicate_record.sudo().write({'check_out': check_out})
                        elif duplicate_record:
                            continue
                        else:
                            att_obj.sudo().create(vals)

                    elif check_in:
                        vals = {
                            'att_date': d,
                            'check_in': check_in,
                            'check_out': check_in,
                            'employee_id': employee.id,
                        }
                        duplicate_record = att_obj.search([('employee_id', '=', employee.id), ('att_date', '=', d)])

                        if duplicate_record and duplicate_record.check_in > check_in:
                            # print("check_in....", duplicate_record.check_in, d)
                            duplicate_record.sudo().write({'check_in': check_in})
                        elif duplicate_record:
                            continue
                        else:
                            att_obj.sudo().create(vals)

                    elif check_out:
                        vals = {
                            'att_date': d,
                            'check_in': check_out,
                            'check_out': check_out,
                            'employee_id': employee.id,
                        }
                        duplicate_record = att_obj.search([('employee_id', '=', employee.id), ('att_date', '=', d)])

                        if duplicate_record and duplicate_record.check_out < check_out:
                            # print("check_out....", duplicate_record.check_out, d)
                            duplicate_record.sudo().write({'check_out': check_out})
                        elif duplicate_record:
                            continue
                        else:
                            att_obj.sudo().create(vals)
                    else:
                        continue  # Skip days with no relevant punches

            zk_att_obj = self.env['zk.machine.attendance'].sudo().search(
                [('is_sent', '!=', True)])

            if zk_att_obj and not self.env.context.get('recalc'):
                for rec in zk_att_obj:
                    rec.is_sent = True
