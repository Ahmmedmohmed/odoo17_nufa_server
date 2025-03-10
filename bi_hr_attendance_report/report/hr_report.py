# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrReport(models.AbstractModel):
    _name ='report.bi_hr_attendance_report.report_one_set'
    _description = 'report.bi_hr_attendance_report.report_one_set'

    @api.model
    def _get_report_values(self, docids, data=None):
        employee = False
        department = False
        if data['form_data'].get('is_employee') or data['form_data'].get('hr_employee_ids'):
            employee = data['form_data'].get('hr_employee_ids')
        
        if data['form_data'].get('is_department') or data['form_data'].get('select_all_department'):
            department = data['form_data'].get('hr_department_ids')
        start_date = data['form_data'].get('starting_date')
        end_date = data['form_data'].get('ending_date')
        docs = self.env['hr.employee'].browse(self.env.context.get('active_id'))

        employee_info_list=[]
        if employee:
            for rec in employee:
                hr_employee_object = self.env['hr.employee'].browse(rec)
                dates_list = []
                vals_dict = {}
                hr_attendance_obj = self.env['hr.attendance'].search([('employee_id', '=', hr_employee_object.id), ('check_in', '>=', start_date),('check_out', '<=', end_date)])
                for times in hr_attendance_obj:
                    date_dict = {
                    'check_in':times.check_in,
                    'check_out':times.check_out,
                    'work_h':round(times.worked_hours),

                    } 
                    dates_list.append(date_dict)
                report_department = False
                vals_dict.update({'emp_name':hr_employee_object.name,
                            'manager':hr_employee_object.parent_id.name,
                            'department':hr_employee_object.department_id.name,
                            'vals':dates_list,
                            'report_department': report_department
                            })
                employee_info_list.append(vals_dict)
        elif department:
            for record in department:
                hr_department_id = self.env['hr.department'].browse(record)
                for rec in hr_department_id.member_ids:
                    hr_employee_object = self.env['hr.employee'].browse(rec)
                    dates_list = []
                    vals_dict={}
                    hr_attendance_obj = self.env['hr.attendance'].search([('employee_id', '=', rec.id), ('check_in', '>=', start_date),('check_out', '<=', end_date)])
                    for times in hr_attendance_obj:
                        date_dict = {
                        'check_in':times.check_in,
                        'check_out':times.check_out,
                        
                        'work_h':round(times.worked_hours),
                        } 
                        dates_list.append(date_dict)
                    vals_dict.update({'emp_name':rec.name,
                                'manager':rec.parent_id.name,
                                'department':rec.department_id.name,
                                'vals':dates_list,
                                'report_department': hr_department_id.name
                                })
                    employee_info_list.append(vals_dict)
        else:
            raise ValidationError(_("Invalid field selection; please select a particular data."))

        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'emp_name':employee_info_list,
            'data': data,
        }