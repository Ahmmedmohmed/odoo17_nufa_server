# -*- coding: utf-8 -*-

from odoo import tools
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    device_id = fields.Char(string='Biometric Device ID')
    # resource_calendar_id = fields.Many2one(required=True)

    @api.constrains('device_id')
    def check_unique_deviceid(self):
        records = self.env['hr.employee'].search(
            [('device_id', '=', self.device_id), ('device_id', '!=', False), ('id', '!=', self.id)])
        if records:
            raise UserError(_('Another User with same Biometric Device ID already exists.'))


class ZkMachine(models.Model):
    _name = 'zk.machine.attendance'
    _description = 'Zk Attendance'

    device_id = fields.Char(string='Biometric Device ID')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    # punch_type = fields.Selection([('0', 'Check In'),
    #                                ('1', 'Check Out'),
    #                                ('2', 'Break Out'),
    #                                ('3', 'Break In'),
    #                                ('4', 'Overtime In'),
    #                                ('5', 'Overtime Out')],
    #                               string='Punching Type')
    #
    # attendance_type = fields.Selection([('1', 'Finger'),
    #                                     ('15', 'Face'),
    #                                     ('2', 'Type_2'),
    #                                     ('3', 'Password'),
    #                                     ('4', 'Card')], string='Category')
    punching_time = fields.Datetime(string='Punching Time')
    address_id = fields.Many2one('res.partner', string='Working Address')
    is_sent = fields.Boolean('Is Sent?', default=False)


class ReportZkDevice(models.Model):
    _name = 'zk.report.daily.attendance'
    _auto = False
    _order = 'punching_day desc'

    name = fields.Many2one('hr.employee', string='Employee')
    punching_day = fields.Date(string='Date')
    address_id = fields.Many2one('res.partner', string='Working Address')
    # attendance_type = fields.Selection([('1', 'Finger'),
    #                                     ('15', 'Face'),
    #                                     ('2', 'Type_2'),
    #                                     ('3', 'Password'),
    #                                     ('4', 'Card')],
    #                                    string='Category')
    # punch_type = fields.Selection([('0', 'Check In'),
    #                                ('1', 'Check Out'),
    #                                ('2', 'Break Out'),
    #                                ('3', 'Break In'),
    #                                ('4', 'Overtime In'),
    #                                ('5', 'Overtime Out')], string='Punching Type')
    punching_time = fields.Datetime(string='Punching Time')
    is_sent = fields.Boolean('Is Sent?', default=False)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'zk_report_daily_attendance')
        self._cr.execute("""
            create or replace view zk_report_daily_attendance as (
                select
                    min(z.id) as id,
                    z.employee_id as name,
                    z.write_date as punching_day,
                    z.address_id as address_id,
                    --z.attendance_type as attendance_type,
                    z.punching_time as punching_time,
                    --z.punch_type as punch_type,
                    z.is_sent as is_sent
                from zk_machine_attendance z
                    join hr_employee e on (z.employee_id=e.id)
                GROUP BY
                    z.employee_id,
                    z.write_date,
                    z.address_id,
                    --z.attendance_type,
                    --z.punch_type,
                    z.punching_time,
                    z.is_sent
            )
        """)
