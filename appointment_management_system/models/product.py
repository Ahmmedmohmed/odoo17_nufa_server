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

    def action_get_available_location_types(self, branch_id, employee_id, package_id=False):
        """Get available location types based on location_type selection field"""
        package_id = self.env['product.product'].browse(int(package_id)) if package_id else False
        available_types = []

        if package_id:
            for record in package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id):
                location_type = record.location_type
                if location_type == 'inside':
                    available_types = ['inside']
                elif location_type == 'outside':
                    available_types = ['outside']
                else:  # both
                    available_types = ['inside', 'outside']
                break
        else:
            employee = self.env['hr.employee'].browse(int(employee_id)) if employee_id else False
            if employee and employee.department_id:
                plan = self.plan_ids.filtered(
                    lambda r: r.branch_id.id == int(branch_id) and 
                             r.department_id.id == employee.department_id.id
                )
                if plan:
                    location_type = plan[0].location_type
                    if location_type == 'inside':
                        available_types = ['inside']
                    elif location_type == 'outside':
                        available_types = ['outside']
                    else:  # both
                        available_types = ['inside', 'outside']

        return available_types

    def action_get_appointment_employee(self, branch_id, package_id=False):
        import logging
        _logger = logging.getLogger(__name__)
        
        package_id = self.env['product.product'].browse(int(package_id))
        dict = {}

        if package_id:
            for record in package_id.appointment_package_line_ids.filtered(lambda r: r.product_id.id == self.id):
                employee_ids = record.department_id.member_ids.filtered(lambda r: r.is_appointment_employee == True)
                for employee in employee_ids:
                    dict[employee.id] = employee.display_name
        else:
            # Try exact branch match first
            matching_plans = self.plan_ids.filtered(lambda record: record.branch_id.id == int(branch_id))
            _logger.info(f"Employee lookup - Service: {self.id}, Branch: {branch_id}, Found {len(matching_plans)} matching plans")
            
            if matching_plans:
                employee_ids = matching_plans.mapped('department_id').member_ids.filtered(lambda r: r.is_appointment_employee == True)
                for employee in employee_ids:
                    dict[employee.id] = employee.display_name
            else:
                # FALLBACK: If no exact branch match, return employees from all available plans
                _logger.warning(f"Employee lookup - No employees found for branch {branch_id}, using fallback to show all available employees for service {self.id}")
                employee_ids = self.plan_ids.mapped('department_id').member_ids.filtered(lambda r: r.is_appointment_employee == True)
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
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            branch_id = int(branch_id)
            employee_obj = self.env['hr.employee'].browse(int(employee_id))
            package_obj = self.env['product.product'].browse(int(package_id)) if package_id else False

            _logger.info(f"Pricing calculation - Service: {self.id}, Branch: {branch_id}, Employee: {employee_obj.id}, Type: {appointment_type}, Package: {package_obj.id if package_obj else 'None'}")
            
            # Add file-based debugging
            debug_file = "/tmp/cart_debug.log"
            with open(debug_file, "a") as f:
                f.write(f"PRODUCT PRICE CALC - Service: {self.id}, Branch: {branch_id}, Employee: {employee_obj.id}, Department: {employee_obj.department_id.id if employee_obj.department_id else 'None'}, Type: {appointment_type}\n")

            # Check if employee has department
            if not employee_obj.department_id:
                _logger.warning(f"Employee {employee_obj.id} has no department assigned")
                return 0.0

            if appointment_type == 'inside' and package_obj:
                package_line = package_obj.appointment_package_line_ids.filtered(
                    lambda r: r.product_id.id == self.id and r.branch_id.id == branch_id and r.department_id.id == employee_obj.department_id.id
                )
                _logger.info(f"Package inside pricing - found {len(package_line)} matching lines")
                if package_line:
                    price = float(package_line[0].service_price_inside)
                    _logger.info(f"Package inside price: {price}")
                    return price
                return 0.0

            elif appointment_type == 'outside' and package_obj:
                package_line = package_obj.appointment_package_line_ids.filtered(
                    lambda r: r.product_id.id == self.id and r.branch_id.id == branch_id and r.department_id.id == employee_obj.department_id.id
                )
                _logger.info(f"Package outside pricing - found {len(package_line)} matching lines")
                if package_line:
                    price = float(package_line[0].service_price_outside)
                    _logger.info(f"Package outside price: {price}")
                    return price
                return 0.0

            elif appointment_type == 'inside':
                plan = self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_obj.department_id.id)
                _logger.info(f"Service inside pricing - found {len(plan)} matching plans")
                
                with open(debug_file, "a") as f:
                    f.write(f"PRODUCT PRICE CALC - Looking for plans with branch {branch_id} and department {employee_obj.department_id.id}\n")
                    f.write(f"PRODUCT PRICE CALC - Found {len(plan)} matching plans\n")
                
                if plan:
                    price = float(plan[0].service_price_inside)
                    _logger.info(f"Service inside price: {price}")
                    
                    with open(debug_file, "a") as f:
                        f.write(f"PRODUCT PRICE CALC - Returning price: {price}\n")
                    
                    return price
                else:
                    # FALLBACK: Try to find plan with matching department_id only (ignoring branch_id mismatch)
                    department_plan = self.plan_ids.filtered(lambda r: r.department_id.id == employee_obj.department_id.id)
                    if department_plan:
                        price = float(department_plan[0].service_price_inside)
                        _logger.warning(f"Service inside pricing - Using fallback plan for department {employee_obj.department_id.id}, price: {price}")
                        
                        with open(debug_file, "a") as f:
                            f.write(f"PRODUCT PRICE CALC - FALLBACK - Using department-only match, price: {price}\n")
                        
                        return price
                    
                    # Debug: show available plans
                    available_plans = [(p.branch_id.id, p.department_id.id, p.service_price_inside) for p in self.plan_ids]
                    _logger.info(f"Available plans for service {self.id}: {available_plans}")
                    
                    with open(debug_file, "a") as f:
                        f.write(f"PRODUCT PRICE CALC - No matching plans found. Available plans: {available_plans}\n")
                
                return 0.0

            else:  # outside
                plan = self.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.department_id.id == employee_obj.department_id.id)
                _logger.info(f"Service outside pricing - found {len(plan)} matching plans")
                if plan:
                    price = float(plan[0].service_price_outside)
                    _logger.info(f"Service outside price: {price}")
                    return price
                else:
                    # FALLBACK: Try to find plan with matching department_id only (ignoring branch_id mismatch)
                    department_plan = self.plan_ids.filtered(lambda r: r.department_id.id == employee_obj.department_id.id)
                    if department_plan:
                        price = float(department_plan[0].service_price_outside)
                        _logger.warning(f"Service outside pricing - Using fallback plan for department {employee_obj.department_id.id}, price: {price}")
                        
                        with open(debug_file, "a") as f:
                            f.write(f"PRODUCT PRICE CALC - FALLBACK OUTSIDE - Using department-only match, price: {price}\n")
                        
                        return price
                    
                    # Debug: show available plans
                    _logger.info(f"Available plans for service {self.id}: {[(p.branch_id.id, p.department_id.id, p.service_price_outside) for p in self.plan_ids]}")
                return 0.0
        except Exception as e:
            _logger.error(f"Error calculating appointment service price: {str(e)}")
            return 0.0



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
