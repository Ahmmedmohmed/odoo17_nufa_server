# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import xlwt
import base64
from io import BytesIO

class CustomExcel(models.TransientModel):
	_name = "custom.excel.class"
	_rec_name = 'datas_fname'
	_description = "Employee Attendence Excel Report Wizard"

	file_name = fields.Binary(string="report")
	datas_fname = fields.Char(string="Filename")

class EmployeeAttendenceReportWizard(models.TransientModel):
	_name = "employee.attendence.report.wizard"
	_description = "Employee Attendence Report Wizard"

	test_field = fields.Char(string="Test Field")
	is_employee = fields.Boolean(string="Employees")
	is_department = fields.Boolean(string="Departments")
	hr_employee_ids = fields.Many2many("hr.employee", string="Employees Selection")
	hr_department_ids = fields.Many2many("hr.department", string="Departments Selection")
	select_all_employee = fields.Boolean(default=False,string="Select All Employees")
	select_all_department = fields.Boolean(default=False,string="Select All Departments")
	selection_of_attendance = fields.Char("Selection of Attendance")
	starting_date = fields.Date(string = "Start date", required=True)
	ending_date = fields.Date(string = "End date", required=True)

	@api.onchange('is_employee')
	def _onchange_is_employee(self):
		if self.is_employee:
			self.is_department = False
			self.hr_department_ids = False
		else:
			self.is_employee = False 
			self.select_all_employee = False
			self.hr_employee_ids = False

	@api.onchange('is_department')
	def _onchange_is_department(self):
		if self.is_department:
			self.is_employee = False
			self.hr_employee_ids = False
		elif self.is_department == False:
			self.select_all_department = False
			self.hr_department_ids = False

	@api.onchange('select_all_employee','select_all_department')
	def _onchange_select_all(self):
		if self.is_employee == True and self.select_all_employee == False:
			self.hr_employee_ids = False
		elif self.is_employee == True and self.select_all_employee == True:
			hr_employee_obj = self.env['hr.employee'].search([])
			self.hr_employee_ids = hr_employee_obj
		elif self.is_department == True and self.select_all_department == False:
			self.hr_department_ids = False
		elif self.is_department == True and self.select_all_department == True:
			hr_department_obj = self.env['hr.department'].search([])
			self.hr_department_ids = hr_department_obj

	def generate_employee_pdf_report(self):
		if self.starting_date > self.ending_date:
			raise ValidationError(_("Invalid DATE selection; please select a proper date and month."))
		else:
			data = {
					'form_data':self.read()[0],
					}
			return self.env.ref('bi_hr_attendance_report.action_report_attendence_report_wizard').report_action(self,data=data)

	def generate_employee_excel_report(self):
		if self.is_employee and self.hr_employee_ids:
			if self.starting_date > self.ending_date:
				raise ValidationError(_("Invalid DATE selection; please select a proper date and month"))
			
			else:
				workbook = xlwt.Workbook(encoding='utf-8')

				for employees in self.hr_employee_ids:		
					hr_attendance_obj = self.env['hr.attendance'].search([('employee_id', '=', employees.id), ('check_in', '>=', self.starting_date),('check_out', '<=', self.ending_date)])
						
					filename = "Employee Excel Report" + '.xls'
					sheet1 = workbook.add_sheet(employees.name)
					
					date_format=xlwt.XFStyle()
					date_format.num_format_str='yyyy/mm/dd' 
					
					format1 = xlwt.easyxf('align:horiz center;font:color black,bold True;borders:top_color black,bottom_color black,right_color black, left_color black,left thin, right thin,top thin, bottom thin;pattern:pattern solid, fore_color lavender')
					format2 = xlwt.easyxf('align:horiz center')
					format3 = xlwt.easyxf('align:horiz center;font:color black, height 300,bold True')

					sheet1.col(0).width = 7000
					sheet1.col(1).width = 7000
					sheet1.col(2).width = 7000
					sheet1.row(0).height = 250
					sheet1.row(1).height = 250

					sheet1.write(2,0,"From", format1)
					sheet1.write(2,1,"To", format1)
					sheet1.write(3,0,self.starting_date, date_format)
					sheet1.write(3,1,self.ending_date, date_format)
					sheet1.write(5,0,"Employee Name", format1)
					sheet1.write(5,1,"Manager Name", format1)
					sheet1.write(5,2,"Department", format1)
					sheet1.write(6,0,employees.name, format2)
					if employees.parent_id.name: 
						sheet1.write(6,1,employees.parent_id.name, format2)
					else:
						sheet1.write(6,1,"   ", format2)
					if employees.department_id.name:
						sheet1.write(6,2,employees.department_id.name, format2)
					else:
						sheet1.write(6,2,"   ", format2)
					sheet1.write(7,0,"Check In", format1)
					sheet1.write(7,1,"Check Out", format1)
					sheet1.write(7,2,"Working hours", format1)
					
					i=8
					for time in hr_attendance_obj:
						sheet1.write(i,0,time.check_in, date_format)
						sheet1.write(i,1,time.check_out, date_format)
						sheet1.write(i,2,round(time.worked_hours))
						i+=1
			
					sheet1.write_merge(0,1,0,2, "Employee Attendance Report", format3)

			stream=BytesIO()
			workbook.save(stream)
			out = base64.encodebytes(stream.getvalue())
			excel_id = self.env['custom.excel.class'].create({"datas_fname":filename,
														  "file_name":out,})
			stream.close()

		elif self.is_department and self.hr_department_ids:
			if self.starting_date > self.ending_date:
				raise ValidationError(_("Invalid DATE selection; please select a proper date and month"))
			else:
				workbook = xlwt.Workbook(encoding='utf-8')

				for departments in self.hr_department_ids:	
					hr_department_obj = self.env['hr.department'].browse(departments)
					
					for employee_department in departments.member_ids:
						hr_employee_object = self.env['hr.employee'].browse(employee_department)
						hr_attendance_obj = self.env['hr.attendance'].search([('employee_id', '=', employee_department.id), ('check_in', '>=', self.starting_date),('check_out', '<=', self.ending_date)])
												
						filename = "Department Excel Report" + '.xls'
						sheet2 = workbook.add_sheet(employee_department.name)

						date_format=xlwt.XFStyle()
						date_format.num_format_str='yyyy/mm/dd' 		
						
						format1 = xlwt.easyxf('align:horiz center;font:color black,bold True;borders:top_color black,bottom_color black,right_color black, left_color black,left thin, right thin,top thin, bottom thin;pattern:pattern solid, fore_color lavender')
						format2 = xlwt.easyxf('align:horiz center')
						format3 = xlwt.easyxf('align:horiz center;font:color black, height 300,bold True')

						sheet2.col(0).width = 7000
						sheet2.col(1).width = 7000
						sheet2.col(2).width = 7000
						sheet2.row(0).height = 250
						sheet2.row(1).height = 250

						sheet2.write(2,0,"From", format1)
						sheet2.write(2,1,"To", format1)
						sheet2.write(3,0,self.starting_date, date_format)
						sheet2.write(3,1,self.ending_date, date_format)
						sheet2.write(5,0,"Employee Name", format1)
						sheet2.write(5,1,"Manager Name", format1)
						sheet2.write(5,2,"Department", format1)
						sheet2.write(6,0,employee_department.name, format2)
						if employee_department.parent_id.name: 
							sheet2.write(6,1,employee_department.parent_id.name, format2)
						else:
							sheet2.write(6,1,"   ", format2)
						if employee_department.department_id.name:
							sheet2.write(6,2,employee_department.department_id.name, format2)
						else:
							sheet2.write(6,2,"   ", format2)
						sheet2.write(7,0,"Check In", format1)
						sheet2.write(7,1,"Check Out", format1)
						sheet2.write(7,2,"Working hours", format1)
						
						i=8
						for time in hr_attendance_obj:
							sheet2.write(i,0,time.check_in, date_format)
							sheet2.write(i,1,time.check_out, date_format)
							sheet2.write(i,2,round(time.worked_hours))
							i+=1
				
						sheet2.write_merge(0,1,0,2, "Attendance Report", format3)
		else:
			raise ValidationError(_("Invalid field selection; please select a particular data."))

		stream=BytesIO()
		workbook.save(stream)
		out = base64.encodebytes(stream.getvalue())
		excel_id = self.env['custom.excel.class'].create({"datas_fname":filename,
													  	  "file_name":out,})
		stream.close()

		return {
				"res_id":excel_id.id,
				"name": "Employee Report",
				"view_mode":"form",
				"res_model":"custom.excel.class",
				"view_id":False,
				"type":"ir.actions.act_window",
				"target":'new',
				}