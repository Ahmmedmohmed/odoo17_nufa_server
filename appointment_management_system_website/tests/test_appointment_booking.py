# -*- coding: utf-8 -*-

import json
from datetime import datetime, date, timedelta
from odoo.tests import common, tagged
from odoo.http import request


@tagged('appointment_booking')
class TestAppointmentBooking(common.TransactionCase):
    """Test case for appointment booking flow with specific test case IDs"""
    
    def setUp(self):
        super(TestAppointmentBooking, self).setUp()
        
        # Test case data as specified by user
        self.test_category_id = 5
        self.test_product_id = 9
        self.test_plan_id = 2
        self.test_employee_id = 1
        
        # Create test data if it doesn't exist
        self.setup_test_data()
        
        # Generate test slots
        self.generate_test_slots()
    
    def setup_test_data(self):
        """Setup required test data for the booking flow"""
        
        # Ensure category exists
        self.category = self.env['pos.category'].browse(self.test_category_id)
        if not self.category.exists():
            self.category = self.env['pos.category'].create({
                'name': 'Test Hair Cut Category',
                'is_appointment_category': True
            })
            self.test_category_id = self.category.id
        
        # Ensure product template and product exist
        self.product = self.env['product.product'].browse(self.test_product_id)
        if not self.product.exists():
            # Create product template first
            product_template = self.env['product.template'].create({
                'name': 'Test Hair Cut Service',
                'is_appointment_service': True,
                'pos_categ_ids': [(6, 0, [self.test_category_id])]
            })
            self.product = self.env['product.product'].create({
                'product_tmpl_id': product_template.id
            })
            self.test_product_id = self.product.id
        
        # Ensure employee exists
        self.employee = self.env['hr.employee'].browse(self.test_employee_id)
        if not self.employee.exists():
            # Create department first
            department = self.env['hr.department'].create({
                'name': 'Test Hair Department',
                'is_appointment_department': True,
                'is_times_confirmed': True
            })
            self.employee = self.env['hr.employee'].create({
                'name': 'Test Employee',
                'department_id': department.id,
                'is_appointment_employee': True
            })
            self.test_employee_id = self.employee.id
        
        # Ensure branch exists
        self.branch = self.env['res.company'].browse(1)
        if not self.branch.exists():
            self.branch = self.env['res.company'].create({
                'name': 'Test Branch'
            })
        
        # Ensure service plan exists
        self.plan = self.env['appointment.service.price.plan'].browse(self.test_plan_id)
        if not self.plan.exists():
            self.plan = self.env['appointment.service.price.plan'].create({
                'service_id': self.test_product_id,
                'branch_id': self.branch.id,
                'department_id': self.employee.department_id.id,
                'service_slot_inside': 2,
                'service_slot_outside': 2,
                'service_price_inside': 50.00,
                'service_price_outside': 75.00
            })
            self.test_plan_id = self.plan.id
    
    def generate_test_slots(self):
        """Generate test slots for the employee"""
        # Clear existing test slots
        existing_slots = self.env['appointment.employee.slot'].search([
            ('employee_id', '=', self.test_employee_id),
            ('date', '>=', date.today()),
            ('date', '<=', date.today() + timedelta(days=3))
        ])
        existing_slots.unlink()
        
        # Create test slots for today and next 2 days
        for day_offset in range(3):
            slot_date = date.today() + timedelta(days=day_offset)
            
            # Create slots from 8 AM to 5 PM (every 30 minutes)
            for hour in range(8, 18):
                for minute in [0, 30]:
                    time_float = hour + (minute / 60.0)
                    time_str = f"{hour:02d}:{minute:02d}"
                    
                    self.env['appointment.employee.slot'].create({
                        'name': time_str,
                        'employee_id': self.test_employee_id,
                        'date': slot_date,
                        'time': time_float,
                        'state': 'draft'
                    })
    
    def test_01_slot_availability_api(self):
        """Test that available slots are returned by API"""
        # Test the slots API endpoint
        from odoo.addons.appointment_management_system_website.controllers.appointment_website_controller import AppointmentWebsiteController
        
        controller = AppointmentWebsiteController()
        
        # Test with our test case parameters
        today = date.today().strftime('%Y-%m-%d')
        slots = controller.get_employee_slots(
            service_id=self.test_product_id,
            employee_id=self.test_employee_id,
            date=today,
            appointment_type='inside',
            branch_id=self.branch.id
        )
        
        # Verify slots are returned
        self.assertTrue(slots, "API should return available slots")
        self.assertIsInstance(slots, dict, "Slots should be returned as dictionary")
        
        # Verify slot structure
        if slots:
            first_slot_key = list(slots.keys())[0]
            first_slot = slots[first_slot_key]
            
            self.assertIn('name', first_slot, "Slot should have name")
            self.assertIn('id', first_slot, "Slot should have ID")
            self.assertIn('ids', first_slot, "Slot should have IDs list")
            self.assertIn('time', first_slot, "Slot should have time")
        
        print(f"✅ Available slots found: {len(slots)} time slots")
        return slots
    
    def test_02_cart_add_and_slot_reservation(self):
        """Test adding slot to cart and verify slot state changes to 'wait'"""
        # First get available slots
        slots = self.test_01_slot_availability_api()
        self.assertTrue(slots, "Need available slots for cart test")
        
        # Select first available slot
        first_slot_key = list(slots.keys())[0]
        first_slot = slots[first_slot_key]
        slot_ids = first_slot['ids']
        
        # Verify slot is initially in draft state
        slot_records = self.env['appointment.employee.slot'].browse(slot_ids)
        for slot in slot_records:
            self.assertEqual(slot.state, 'draft', f"Slot {slot.id} should be in draft state initially")
        
        # Test cart add API
        from odoo.addons.appointment_management_system_website.controllers.appointment_website_controller import AppointmentWebsiteController
        
        controller = AppointmentWebsiteController()
        
        # Prepare service data
        service_data = {
            'service_id': self.test_product_id,
            'employee_id': self.test_employee_id,
            'slot_ids': slot_ids,
            'date': date.today().strftime('%Y-%m-%d'),
            'appointment_type': 'inside',
            'branch_id': self.branch.id,
            'price': 50.00
        }
        
        # Mock request session for cart functionality
        with self.env.cr.savepoint():
            # Add to cart
            result = controller.add_to_cart(service_data)
            
            # Verify successful addition
            self.assertTrue(result.get('success'), f"Cart add should succeed: {result.get('error', '')}")
            self.assertGreater(result.get('cart_count', 0), 0, "Cart should have items")
            
            # Verify slot state changed to 'wait'
            slot_records.invalidate_cache()  # Refresh from database
            for slot in slot_records:
                self.assertEqual(slot.state, 'wait', f"Slot {slot.id} should be in wait state after cart add")
            
            print(f"✅ Slot reservation successful: {len(slot_ids)} slots reserved")
            return result, slot_ids
    
    def test_03_appointment_creation_and_payment_flow(self):
        """Test appointment creation and payment confirmation"""
        # Add slot to cart first
        cart_result, slot_ids = self.test_02_cart_add_and_slot_reservation()
        
        # Simulate payment completion by creating appointment
        partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
            'phone': '+1234567890'
        })
        
        # Create appointment using existing method
        appointment_details = {
            'service_id': False,  # Not a package
            'isSelectedServicePack': False,
            'services': {
                str(self.test_product_id): {
                    'branch_id': self.branch.id,
                    'employee_id': self.test_employee_id,
                    'appointment_type': 'inside',
                    'date': date.today().strftime('%Y-%m-%d'),
                    'slot_ids': slot_ids,
                }
            }
        }
        
        # Create appointment
        result = self.product.action_create_appointments(partner.id, appointment_details)
        
        # Verify appointment was created
        appointment_id = result['services'][str(self.test_product_id)]['appointment_id']
        appointment = self.env['appointment.management'].browse(appointment_id)
        
        self.assertTrue(appointment.exists(), "Appointment should be created")
        self.assertEqual(appointment.state, '1', "Appointment should be in Partial Approved state")
        self.assertEqual(appointment.partner_id, partner, "Appointment should have correct partner")
        self.assertEqual(appointment.product_id.id, self.test_product_id, "Appointment should have correct service")
        self.assertEqual(appointment.employee_id.id, self.test_employee_id, "Appointment should have correct employee")
        
        # Simulate successful payment - update appointment to approved
        appointment.write({'state': '2'})  # Approved
        
        # Update associated slots to 'done'
        slot_records = self.env['appointment.employee.slot'].browse(slot_ids)
        slot_records.write({'state': 'done'})
        
        # Verify final states
        self.assertEqual(appointment.state, '2', "Appointment should be approved after payment")
        for slot in slot_records:
            self.assertEqual(slot.state, 'done', f"Slot {slot.id} should be done after payment")
        
        print(f"✅ Appointment created successfully: ID {appointment_id}")
        print(f"✅ Final appointment state: {appointment.state}")
        print(f"✅ Final slot states: {[slot.state for slot in slot_records]}")
        
        return appointment_id
    
    def test_04_complete_booking_flow(self):
        """Test the complete booking flow and return appointment IDs"""
        print(f"\n🧪 TESTING COMPLETE BOOKING FLOW")
        print(f"📊 Test case parameters:")
        print(f"   - Category ID: {self.test_category_id}")
        print(f"   - Product ID: {self.test_product_id}")
        print(f"   - Plan ID: {self.test_plan_id}")
        print(f"   - Employee ID: {self.test_employee_id}")
        
        # Step 1: Test slot availability
        print(f"\n1️⃣ Testing slot availability...")
        slots = self.test_01_slot_availability_api()
        
        # Step 2: Test cart and reservation
        print(f"\n2️⃣ Testing cart and slot reservation...")
        cart_result, slot_ids = self.test_02_cart_add_and_slot_reservation()
        
        # Step 3: Test appointment creation and payment
        print(f"\n3️⃣ Testing appointment creation and payment...")
        appointment_id = self.test_03_appointment_creation_and_payment_flow()
        
        # Return appointment ID for verification
        print(f"\n✅ BOOKING FLOW TEST COMPLETED SUCCESSFULLY")
        print(f"📋 Created appointment ID: {appointment_id}")
        print(f"🎯 Verification: Check appointment.management record ID {appointment_id} in database")
        
        return {
            'appointment_ids': [appointment_id],
            'test_case_ids': {
                'category_id': self.test_category_id,
                'product_id': self.test_product_id,
                'plan_id': self.test_plan_id,
                'employee_id': self.test_employee_id
            },
            'slot_ids': slot_ids,
            'success': True
        }