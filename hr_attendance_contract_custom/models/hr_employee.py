# -*- coding: utf-8 -*-

from odoo import models


class HREmployee(models.Model):
    _inherit = "hr.employee"

    def _late_hours(self, date_from, date_to, act_hour_period):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('act_late_in', '>', act_hour_period)])
            total_hours = sum(attendance_obj.mapped('act_late_in'))
            return total_hours

    def _diff_hours(self, date_from, date_to, act_hour_period):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('act_diff_time', '>', act_hour_period)])
            total_hours = sum(attendance_obj.mapped('act_diff_time'))
            return total_hours

    def _late_penalties(self, date_from, date_to):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('late_in', '>', 0)])
            total_days = sum(attendance_obj.mapped('late_in'))
            return total_days

    def _diff_penalties(self, date_from, date_to):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('diff_time', '>', 0)])
            total_days = sum(attendance_obj.mapped('diff_time'))
            return total_days

    def _working_hours(self, date_from, date_to, hour_period):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('is_weekend', '=', 0), ('is_public_holiday', '=', 0), ('over_time', '>', hour_period)])
            total_hours = sum(attendance_obj.mapped('over_time'))
            return total_hours

    def _weekend_hours(self, date_from, date_to):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('is_weekend', '=', 1)])
            total_hours = sum(attendance_obj.mapped('over_time'))
            return total_hours

    def _public_holiday_hours(self, date_from, date_to):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('is_public_holiday', '=', 1)])
            total_hours = sum(attendance_obj.mapped('over_time'))
            return total_hours

    def _absence_days(self, date_from, date_to, payslip_id):
        for rec in self:
            attendance_obj = self.env['hr.attendance'].search(
                [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                 ('is_weekend', '=', 0), ('is_public_holiday', '=', 0)])
            payslip_obj = self.env['hr.payslip'].search([('id', '=', payslip_id)])
            actual_days = len(attendance_obj)
            planned_days = payslip_obj.worked_days_line_ids.filtered(lambda x: x.work_entry_type_id.id == 1)
            total_days = planned_days.number_of_days - actual_days
            return total_days

    def _absence_penalties(self, date_from, date_to, payslip_id):
        for rec in self:
            contract_id = self.env['hr.contract'].search([('employee_id', '=', rec.id),
                                                          ('state', 'in', ['open', 'close'])])
            policy_id = contract_id[-1].att_policy_id if contract_id else False
            absence_rule_id = policy_id.absence_rule_id if policy_id else False

            total = 0
            if absence_rule_id:
                count = self._absence_days(date_from, date_to, payslip_id)

                if count == 0:
                    total = 0
                elif count == 1:
                    total = absence_rule_id.first
                elif count == 2:
                    total = absence_rule_id.first + absence_rule_id.second
                elif count == 3:
                    total = absence_rule_id.first + absence_rule_id.second + absence_rule_id.third
                elif count == 4:
                    total = absence_rule_id.first + absence_rule_id.second + absence_rule_id.third + absence_rule_id.fourth
                elif count == 5:
                    total = absence_rule_id.first + absence_rule_id.second + absence_rule_id.third + absence_rule_id.fourth + absence_rule_id.fifth
                else:
                    total = absence_rule_id.first + absence_rule_id.second + absence_rule_id.third + absence_rule_id.fourth + absence_rule_id.fifth + (
                            absence_rule_id.fifth * (count - 5))
            return total

    def _tamper_penalties(self, date_from, date_to):
        for rec in self:
            contract_id = self.env['hr.contract'].search([('employee_id', '=', rec.id),
                                                          ('state', 'in', ['open', 'close'])])
            policy_id = contract_id[-1].att_policy_id if contract_id else False
            tamper_rule_id = policy_id.tamper_rule_id if policy_id else False

            total = 0
            if tamper_rule_id:
                attendance_obj = self.env['hr.attendance'].search(
                    [('employee_id', '=', rec.id), ('att_date', '>=', date_from), ('att_date', '<=', date_to),
                     ('is_tamper', '>', 0)])
                count = len(attendance_obj)

                if count == 0:
                    total = 0
                elif count == 1:
                    total = tamper_rule_id.first
                elif count == 2:
                    total = tamper_rule_id.first + tamper_rule_id.second
                elif count == 3:
                    total = tamper_rule_id.first + tamper_rule_id.second + tamper_rule_id.third
                elif count == 4:
                    total = tamper_rule_id.first + tamper_rule_id.second + tamper_rule_id.third + tamper_rule_id.fourth
                elif count == 5:
                    total = tamper_rule_id.first + tamper_rule_id.second + tamper_rule_id.third + tamper_rule_id.fourth + tamper_rule_id.fifth
                else:
                    total = tamper_rule_id.first + tamper_rule_id.second + tamper_rule_id.third + tamper_rule_id.fourth + tamper_rule_id.fifth + (
                            tamper_rule_id.fifth * (count - 5))
            return total
