# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import OrderedDict



class Product(models.Model):
    _inherit = 'product.product'


    is_appointment_service = fields.Boolean(string='Appointment Service')
    is_appointment_package = fields.Boolean(string='Appointment Package')
    appointment_package_line_ids = fields.One2many('appointment.package.line', 'product_pack_id', string='Appointment Package Lines')
    plan_ids = fields.One2many('appointment.service.price.plan', 'service_id', string='Associated Plans')
    product_component_ids = fields.One2many('product.component', 'product_id', string='Components')


    def action_update_appointment(self, appointment_id, status):
        appointment_id = self.env['appointment.management'].sudo().search([('id', '=', appointment_id)])
        for slot in appointment_id.slot_ids:
            slot.sudo().update({'state':'done' if status == '2' else 'draft'})
        appointment_id.write({'state': status})


    def action_get_appointment_branch(self, package_id=False):
        package_id = self.env['product.product'].browse(int(package_id))
        dict = {}

        if package_id:
            for record in package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id):
                dict[record.branch_id.id] = record.branch_id.display_name
        else:
            branch_ids = self.plan_ids.mapped('branch_id')
            for branch in branch_ids:
                dict[branch.id] = branch.display_name
        return dict


    def action_get_appointment_employee(self, branch_id, package_id=False):
        package_id = self.env['product.product'].browse(int(package_id))
        dict = {}

        if package_id:
            for record in package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id):
                employee_ids = record.department_id.member_ids.filtered(lambda r: r.is_appointment_employee == True)
                for employee in employee_ids:
                    dict[employee.id] = employee.display_name
        else:
            employee_ids = self.plan_ids.filtered(lambda record: record.branch_id.id == int(branch_id)).mapped('department_id').member_ids.filtered(lambda r: r.is_appointment_employee == True)
            for employee in employee_ids:
                dict[employee.id] = employee.display_name

        return dict


    def action_get_appointment_date(self, employee_id, package_id=False):
        days_list = []

        for x in range(30):
            days_list.append(str(date.today() + timedelta(days=x)))

        return days_list


    def action_get_appointment_employee_slot(self, employee_id, date, type, branch, package_id=False):
        package_id = self.env['product.product'].browse(int(package_id))
        slots = 99
        dict = {}
        date = datetime.strptime(date, '%Y-%m-%d').date()
        employee_id = self.env['hr.employee'].browse(int(employee_id))

        if package_id:
            for record in package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id):
                if type == 'inside':
                    slots = record.service_slot_inside
                if type == 'outside':
                    slots = record.service_slot_outside
        else:
            # Handle null branch_id by providing a default or filtering it out
            branch_filter = []
            if branch and str(branch).strip():
                branch_filter = [('branch_id', '=', int(branch))]
            
            service_plan_id = self.env['appointment.service.price.plan'].search([
                ('service_id', '=', self.id), 
                ('department_id', '=', employee_id.department_id.id)
            ] + branch_filter)
            
            if service_plan_id and type == 'inside':
                slots = service_plan_id.service_slot_inside
            if service_plan_id and type == 'outside':
                slots = service_plan_id.service_slot_outside

        return self.get_all_available_slot_groups_records(employee_id.id, date, slots)


    def action_get_appointment_service_price(self, branch_id, employee_id, appointment_type, package_id=False):
        branch_id = int(branch_id)
        employee_id = self.env['hr.employee'].browse(int(employee_id))
        package_id = self.env['product.product'].browse(int(package_id)) if package_id else False

        if appointment_type == 'inside' and package_id:
            return package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id and r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id).service_price_inside

        elif appointment_type == 'outside' and package_id:
            return package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id and r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id).service_price_outside

        elif appointment_type == 'inside':
            plan = self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id)
            return plan.service_price_inside if plan else False

        else:
            plan = self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_id.department_id.id)
            return plan.service_price_outside if plan else False



    def action_create_appointments(self, partner_id, appointmentDetails):
        package_id = appointmentDetails['service_id'] if appointmentDetails['isSelectedServicePack'] else False

        for record in appointmentDetails['services']:
            service_id = self.env['product.product'].browse(int(record))
            appointmentDetail = appointmentDetails['services'][record]
            requested_slot_ids = appointmentDetail.get('slot_ids', [])
            slot_ids = self.env['appointment.employee.slot'].sudo().search([('id', 'in', requested_slot_ids)])
            
            # Skip this service if no valid slots are found
            if not slot_ids:
                continue

            price = service_id.action_get_appointment_service_price(appointmentDetail.get('branch_id'), appointmentDetail.get('employee_id'), appointmentDetail.get('appointment_type'), package_id)

            date = datetime.strptime(appointmentDetail.get('date'), "%Y-%m-%d").date()
            time_str = slot_ids.mapped('name')[0]
            time = datetime.strptime(time_str, "%H:%M").time()
            combined = datetime.combine(date, time).replace(tzinfo=ZoneInfo(self.env.user.tz))

            local_dt = datetime.combine(date, time).replace(tzinfo=ZoneInfo(self.env.user.tz))
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
            final_dt = utc_dt.replace(tzinfo=None)

            appointment_id = self.env['appointment.management'].sudo().create({
                'partner_id': partner_id,
                'date': final_dt,
                'product_id': record,
                'employee_id': appointmentDetail.get('employee_id'),
                'branch_id': appointmentDetail.get('branch_id'),
                'price_unit': price,
                'appointment_type': appointmentDetail.get('appointment_type'),
                'state': '1',
                'slot_ids': [(6, 0, slot_ids.ids)]
            })

            appointmentDetails['services'][record]['appointment_id'] = appointment_id.id
            appointmentDetails['services'][record]['appointment_name'] = appointment_id.sequence
            appointmentDetails['services'][record]['price'] = price

            for slot in appointment_id.slot_ids:
                slot.sudo().update({'state': 'wait'})

        return appointmentDetails


    def get_all_available_slot_groups_records(self, employee_id, appointment_date, required_slots):
        available_slots = self.env['appointment.employee.slot'].search([('employee_id', '=', int(employee_id)), ('date', '=', appointment_date), ('state', '=', 'draft')])

        if not available_slots:
            return []

        sorted_slots = sorted(available_slots, key=lambda s: s.time)

        consecutive_groups = []
        current_group = [sorted_slots[0]]

        for i in range(1, len(sorted_slots)):
            prev_time = round(sorted_slots[i - 1].time, 1)
            curr_time = round(sorted_slots[i].time, 1)

            if curr_time == prev_time + 0.5:
                current_group.append(sorted_slots[i])
            else:
                consecutive_groups.append(current_group)
                current_group = [sorted_slots[i]]

        if current_group:
            consecutive_groups.append(current_group)

        result_groups = []
        for group in consecutive_groups:
            if len(group) >= required_slots:
                for i in range(len(group) - required_slots + 1):
                    selected = group[i:i + required_slots]
                    result_groups.append(selected)
        result = {}

        for group in result_groups:
            # Skip empty groups to prevent IndexError
            if not group:
                continue
                
            slot_ids = []

            for slot in group:
                slot_ids.append(slot.id)

            result[group[0].name] = {'name': group[0].name, 'id': group[0].id, 'ids': slot_ids}
        return result
