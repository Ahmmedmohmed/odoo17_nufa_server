# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (c) 2021 CDS Solutions SRL. (http://cdsegypt.com)
#    Maintainer: Eng.Ramadan Khalil (<ramadan.khalil@cdsegypt.com>)
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    attendance_sheet_ids = fields.One2many(comodel_name='attendance.sheet', inverse_name='payslip_id',
                                           string='Attendance Sheets', ondelete='cascade')

    overtime_no = fields.Integer(string="Overtime No", compute='_compute_att_sheet_data')
    overtime_hours = fields.Float(string="Overtime Hours", compute='_compute_att_sheet_data')
    late_no = fields.Integer(string="Late No", compute='_compute_att_sheet_data')
    late_hours = fields.Float(string="Late Hours", compute='_compute_att_sheet_data')
    absent_no = fields.Integer(string="Absent No", compute='_compute_att_sheet_data')
    absent_hours = fields.Float(string="Absent Hours", compute='_compute_att_sheet_data')
    diff_no = fields.Integer(string="Diff No", compute='_compute_att_sheet_data')
    diff_hours = fields.Float(string="Diff Hours", compute='_compute_att_sheet_data')
    worked_days = fields.Integer(string="Work Days No", compute='_compute_att_sheet_data')
    worked_hours = fields.Float(string="Work Days Hours", compute='_compute_att_sheet_data')
    # no_unpaid_leave = fields.Float(compute="_compute_att_sheet_data",
    #                                string="No Unpaid Leave Times")
    # tot_unpaid_leave = fields.Float(compute="_compute_att_sheet_data",
    #                                 string="Total Unpaid Leave")

    def _compute_att_sheet_data(self):
        for slip in self:
            overtime_no = overtime_hours = late_no = late_hours = absent_no = absent_hours = diff_no = diff_hours = worked_days = worked_hours = 0
            # no_unpaid_leave = 0
            # tot_unpaid_leave = 0
            for sheet in slip.attendance_sheet_ids:
                overtime_no += sheet.no_overtime
                overtime_hours += sheet.tot_overtime
                late_no += sheet.no_late
                late_hours += sheet.tot_late
                absent_no += sheet.no_absence
                absent_hours += sheet.tot_absence
                diff_no += sheet.no_difftime
                diff_hours += sheet.tot_difftime
                worked_hours += sheet.tot_worked_hour
                # no_unpaid_leave += sheet.no_unpaid_leave
                # tot_unpaid_leave += sheet.tot_unpaid_leave
                
            slip.overtime_no = overtime_no
            slip.overtime_hours = overtime_hours
            slip.late_no = late_no
            slip.late_hours = late_hours
            slip.absent_no = absent_no
            slip.absent_hours = absent_hours
            slip.diff_no = diff_no
            slip.diff_hours = diff_hours
            slip.worked_days = worked_days
            slip.worked_hours = worked_hours
            # slip.no_unpaid_leave = no_unpaid_leave
            # slip.tot_unpaid_leave = tot_unpaid_leave

    def set_payslip_attendance_sheet(self):
        self.ensure_one()
        sheet_ids = self.env['attendance.sheet'].search(
            [('employee_id', '=', self.employee_id.id), ('date_from', '>=', self.date_from),
             ('date_to', '<=', self.date_to), ('state', '=', 'done')])
        if sheet_ids:
            self.write({'attendance_sheet_ids': [(6, 0, sheet_ids.ids)]})

    def _get_new_worked_days_lines(self):
        res = super(HrPayslip, self)._get_new_worked_days_lines()
        if self.contract_id and self.contract_id.attendance_sheet_based:
            self.set_payslip_attendance_sheet()
        return res

    def compute_sheet(self):
        for slip in self:
            if slip.contract_id and slip.contract_id.attendance_sheet_based:
                slip.set_payslip_attendance_sheet()
                if not slip.attendance_sheet_ids:
                    raise UserError(_('No Approved Attendance Sheet Found For Employee : %s') % (slip.employee_id.name))
        return super(HrPayslip, self).compute_sheet()
