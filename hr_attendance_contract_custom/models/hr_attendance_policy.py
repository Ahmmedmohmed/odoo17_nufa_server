# -*- coding: utf-8 -*-

from odoo import models, fields


class HrAttendancePolicy(models.Model):
    _name = 'hr.attendance.policy'
    _description = 'HR Attendance Policies'

    name = fields.Char(string="Policy Name", required=True)
    late_rule_id = fields.Many2one(comodel_name="hr.late.rule", string="Late In Rule", required=True)
    diff_rule_id = fields.Many2one(comodel_name="hr.diff.rule", string="Difference Time Rule", required=True)
    absence_rule_id = fields.Many2one(comodel_name="hr.absence.rule", string="Absence Rule", required=True)
    tamper_rule_id = fields.Many2one(comodel_name="hr.tamper.rule", string="Tamper Rule", required=True)

    def get_late(self, period, cnt):
        # res = period
        res = 0
        flag = False
        no = 1
        cnt_flag = False
        # factor = 1
        if period <= 0:
            return 0, cnt
        if self.late_rule_id:
            time_ids = self.late_rule_id.line_ids.sorted(key=lambda r: r.time, reverse=True)
            for line in time_ids:
                if period >= line.time:
                    for counter in cnt:
                        if counter[0] == line.time:
                            cnt_flag = True
                            no = counter[1]
                            counter[1] += 1
                            break

                    if no >= 6 and line.sixth >= 0:
                        res = line.sixth
                    elif no >= 5 and line.fifth >= 0:
                        res = line.fifth
                    elif no >= 4 and line.fourth >= 0:
                        res = line.fourth
                    elif no >= 3 and line.third >= 0:
                        res = line.third
                    elif no >= 2 and line.second >= 0:
                        res = line.second
                    elif no >= 1 and line.first >= 0:
                        res = line.first
                    elif no == 0:
                        res = 0

                    if not cnt_flag:
                        cnt.append([line.time, 2])
                    flag = True

                    # if line.type == 'rate':
                    #     res = line.rate * period * factor
                    # elif line.type == 'fix':
                    #     res = line.amount * factor
                    break

            if not flag:
                res = 0
        return res, cnt

    def get_diff(self, period, cnt):
        # res = period
        res = 0
        flag = False
        no = 1
        cnt_flag = False
        # factor = 1
        if period <= 0:
            return 0, cnt
        if self.diff_rule_id:
            time_ids = self.diff_rule_id.line_ids.sorted(key=lambda r: r.time, reverse=True)
            for line in time_ids:
                if period >= line.time:
                    for counter in cnt:
                        if counter[0] == line.time:
                            cnt_flag = True
                            no = counter[1]
                            counter[1] += 1
                            break

                    if no >= 5 and line.fifth >= 0:
                        res = line.fifth
                    elif no >= 4 and line.fourth >= 0:
                        res = line.fourth
                    elif no >= 3 and line.third >= 0:
                        res = line.third
                    elif no >= 2 and line.second >= 0:
                        res = line.second
                    elif no >= 1 and line.first >= 0:
                        res = line.first
                    elif no == 0:
                        res = 0

                    if not cnt_flag:
                        cnt.append([line.time, 2])
                    flag = True

                    # if line.type == 'rate':
                    #     res = line.rate * period * factor
                    # elif line.type == 'fix':
                    #     res = line.amount * factor
                    break

            if not flag:
                res = 0
        return res, cnt


class HrLateRule(models.Model):
    _name = 'hr.late.rule'
    _description = 'Late In Rules'

    name = fields.Char(string='Rule Name', required=True)
    line_ids = fields.One2many(comodel_name='hr.late.rule.line', inverse_name='late_id', string='Late In Periods')


class HrLateRuleLine(models.Model):
    _name = 'hr.late.rule.line'
    _description = 'Late In Rule Lines'
    # type = [('fix', 'Fixed'), ('rate', 'Rate')]

    late_id = fields.Many2one(comodel_name='hr.late.rule', string='Late Rule')
    time = fields.Float('Time')
    # type = fields.Selection(string="Type", selection=type, required=True)
    # rate = fields.Float(string='Rate')
    # amount = fields.Float('Amount')
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)
    sixth = fields.Float('Sixth Time', default=1)


class HrDiffRule(models.Model):
    _name = 'hr.diff.rule'
    _description = 'Diff Time Rule'

    name = fields.Char(string='Rule Name', required=True)
    line_ids = fields.One2many(comodel_name='hr.diff.rule.line',
                               inverse_name='diff_id',
                               string='Difference time Periods')


class HrDiffRuleLine(models.Model):
    _name = 'hr.diff.rule.line'
    _description = 'Diff Time Rule Line'
    # type = [('fix', 'Fixed'), ('rate', 'Rate')]

    diff_id = fields.Many2one(comodel_name='hr.diff.rule', string='Diff Rule')
    time = fields.Float('Time')
    # type = fields.Selection(string="Type", selection=type, required=True)
    # rate = fields.Float(string='Rate')
    # amount = fields.Float('Amount')
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)


class HrAbsenceRule(models.Model):
    _name = 'hr.absence.rule'
    _description = 'Absence Rules'

    name = fields.Char(string='Rule Name', required=True)
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)


class HrTamperRule(models.Model):
    _name = 'hr.tamper.rule'
    _description = 'Tamper Rules'

    name = fields.Char(string='Rule Name', required=True)
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)
