# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, timedelta


class Product(models.Model):
    _inherit = 'product.product'


    is_appointment_service = fields.Boolean(string='Appointment Service')
    plan_ids = fields.One2many('appointment.service.price.plan', 'service_id', string='Associated Plans')


    def action_get_appointment_branch(self):
        dict = {}
        branch_ids = self.plan_ids.mapped('branch_id')

        for branch in branch_ids:
            dict[branch.id] = branch.display_name

        return dict


    def action_get_appointment_employee(self, branch_id):
        dict = {}
        employee_ids = self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id).mapped('department_id').member_ids.filtered(lambda r: r.is_appointment_employee == True)

        for employee in employee_ids:
            dict[employee.id] = employee.display_name
        return dict


    def action_get_appointment_date(self, employee_id):
        days_list = []

        for x in range(10):
            days_list.append(str(date.today() + timedelta(days=x)))

        return days_list


    def action_get_appointment_employee_slot(self, employee_id, date):
        dict = {}
        date = datetime.strptime(date, '%Y-%m-%d').date()
        slot_ids = self.env['appointment.employee.slot'].sudo().search([('employee_id', '=', employee_id), ('date', '=', date), ('state', '=', 'draft')])

        for slot in slot_ids:
            dict[slot.id] = slot.display_name

        return dict


    def action_get_appointment_service_price(self, branch_id, employee_id, appointment_type):
        employee_id = self.env['hr.employee'].search([('id', '=', employee_id)])
        if appointment_type == 'inside':
            return self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id).service_price_inside
        else:
            return self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id).service_price_outside


    def action_create_appointment(self, partner_id, branch_id, employee_id, date, appointment_type, slot_id):
        price = self.action_get_appointment_service_price(branch_id, employee_id, appointment_type)
        appointment_id = self.env['appointment.management'].sudo().create({
            'partner_id': partner_id,
            'date': date,
            'product_id': self.id,
            'employee_id': employee_id,
            'branch_id': branch_id,
            'price_unit': price,
            'appointment_type': appointment_type,
            'state': 'partial',
        })

        return {'id':appointment_id.id,'price':price}

    def action_update_appointment(self, appointment_id):
        appointment_id = self.env['appointment.management'].sudo().search([('id', '=', appointment_id)])
        appointment_id.write({'state': 'approved'})