# appointment_management_system - Module Memory

## Overview
Core Odoo 17 module for salon/appointment management. Provides the foundational data models, business logic, and backend views for managing appointments, services, employees, departments, time plans, slots, and pricing.

**Version:** 1.0  
**Category:** Custom  
**Dependencies:** `base`, `hr`, `product`, `stock`, `point_of_sale`  
**Application:** Yes

---

## Models

### appointment.management (`models/appointment_management.py`)
- **_name:** `appointment.management`
- **Key Fields:**
  - `sequence` (Char) - Auto-generated via `ir.sequence` with prefix "A" and padding 5 (e.g., A00001)
  - `partner_id` (Many2one -> res.partner) - Customer
  - `partner_phone` (Char) - Related to partner phone
  - `date` (Datetime) - Appointment date/time
  - `branch_id` (Many2one -> res.company) - Branch location
  - `company_id` (Many2one -> res.company) - Current company (readonly)
  - `product_id` (Many2one -> product.product) - Service (domain: is_appointment_service=True)
  - `employee_id` (Many2one -> hr.employee) - Assigned employee (domain: is_appointment_employee=True)
  - `price_unit` (Float) - Service price
  - `service_rate` (Selection) - Rating: 0=Low, 1=Medium, 2=High, 3=Very High
  - `state` (Selection) - States: 1=Partial Approved, 2=Approved, 3=Completed, 4=Cancelled
  - `appointment_type` (Selection) - inside/outside (default: inside)
  - `notes` (Text)
  - `slot_ids` (Many2many -> appointment.employee.slot)
- **Key Methods:**
  - `action_appointment_complate()` - Marks state=3, creates stock.picking if components exist (transfers from employee location to company destination)
  - `create()` / `write()` - Validates slot_ids to prevent FK constraint violations
- **Ordering:** By `state` field

### product.product (`models/product.py`) - Inherited
- **Added Fields:**
  - `is_appointment_service` (Boolean)
  - `is_appointment_package` (Boolean)
  - `appointment_package_line_ids` (One2many -> appointment.package.line)
  - `plan_ids` (One2many -> appointment.service.price.plan)
  - `product_component_ids` (One2many -> product.component)
- **Key Methods (all on product.product):**
  - `action_update_appointment(appointment_id, status)` - Updates appointment state and slot states
  - `action_get_appointment_branch(package_id)` - Returns dict of {branch_id: branch_name} for a service
  - `action_get_available_location_types(branch_id, employee_id, package_id)` - Returns available location types (inside/outside/both)
  - `action_get_appointment_employee(branch_id, package_id)` - Returns dict of {employee_id: employee_name}; has fallback logic if no exact branch match
  - `action_get_appointment_date(employee_id, package_id)` - Returns list of next 30 date strings
  - `action_get_appointment_employee_slot(employee_id, date, type, branch, package_id)` - Returns available slot groups based on required_slots from price plan; has branch fallback (if no plan matches with given branch, searches again without branch filter)
  - `action_get_appointment_service_price(branch_id, employee_id, appointment_type, package_id)` - Calculates price from plan_ids; has fallback to department-only match
  - `action_create_appointments(partner_id, appointmentDetails)` - Creates appointments from POS/website data, handles timezone conversion (user TZ -> UTC), sets slots to 'wait'
  - `get_all_available_slot_groups_records(employee_id, appointment_date, required_slots)` - Finds consecutive available slot groups

### hr.employee (`models/hr_employee.py`) - Inherited
- **Added Fields:**
  - `is_appointment_employee` (Boolean)
  - `location_id` (Many2one -> stock.location) - For stock operations
- **Methods:** `action_available_in_appointment()`, `action_unavailable_in_appointment()`

### hr.department (`models/hr_department.py`) - Inherited
- **Added Fields:**
  - `is_appointment_department` (Boolean)
  - `is_times_confirmed` (Boolean)
  - `plan_ids` (One2many -> appointment.department.time.plan)
- **Methods:** `action_available_in_appointment()`, `action_unavailable_in_appointment()`, `action_confirm_times()`, `action_unconfirm_times()` (onchange plan_ids)

### pos.category (`models/pos_category.py`) - Inherited
- **Added Fields:**
  - `is_appointment_category` (Boolean)
  - `image` (Image, max 512x512)
- **Methods:** `action_available_in_appointment()`, `action_unavailable_in_appointment()`

### appointment.employee.slot (`models/appointment_employee_slot.py`)
- **_name:** `appointment.employee.slot`
- **Fields:**
  - `name` (Char) - Time string e.g. "08:00"
  - `employee_id` (Many2one -> hr.employee)
  - `date` (Date)
  - `time` (Float) - e.g. 8.0 for 08:00, 8.5 for 08:30
  - `state` (Selection) - draft/wait/done/cancel (default: draft)
- **Key Methods:**
  - `auto_delete_old_slots()` - Cron: deletes slots older than 20 days, unlinks from appointments first
  - `auto_reset_wait_to_draft()` - Cron: resets 'wait' slots to 'draft' if write_date > 10 min ago
  - `action_create_employee_slots()` - Cron: generates 30-minute slots for next 35 days based on department time plans
  - State change actions: `action_change_state_wait()`, `action_change_state_done()`, `action_change_state_cancel()`

### appointment.service.price.plan (`models/appointment_service_price_plan.py`)
- **_name:** `appointment.service.price.plan`
- **Fields:**
  - `service_id` (Many2one -> product.product)
  - `department_id` (Many2one -> hr.department, domain: is_appointment_department=True)
  - `branch_id` (Many2one -> res.company)
  - `currency_id` (Many2one -> res.currency)
  - `service_slot_inside` / `service_slot_outside` (Integer) - Number of 30-min slots needed
  - `service_price_inside` / `service_price_outside` (Monetary)
- **Note:** Has commented-out `location_type` Selection field (inside/outside/both)

### appointment.package.line (`models/appointment_package_line.py`)
- **_name:** `appointment.package.line`
- **Fields:** Same structure as price plan but for packages
  - `product_id` (Many2one -> product.product) - The service
  - `product_pack_id` (Many2one -> product.product) - The package
  - `department_id`, `branch_id`, `currency_id`
  - `service_slot_inside/outside`, `service_price_inside/outside`
- **Note:** Has commented-out `location_type` field

### appointment.department.time.plan (`models/appointment_department_time_plan.py`)
- **_name:** `appointment.department.time.plan`
- **Fields:**
  - `department_id` (Many2one -> hr.department)
  - `day` (Selection) - saturday through friday
  - `start_hour`, `start_minute`, `end_hour`, `end_minute` (Integer)
- **Constraints:**
  - Hours must be 1-24
  - Minutes must be 0-60
  - End time must be after start time
  - No overlapping time slots for same department+day

### appointment.refund.policy (`models/appointment_refund_policy.py`)
- **_name:** `appointment.refund.policy`
- **Fields:**
  - `hours_before_appointment` (Integer)
  - `percentage` (Float)

### product.component (`models/product_component.py`)
- **_name:** `product.component`
- **Fields:**
  - `component_id` (Many2one -> product.product) - The component product
  - `quantity` (Float)
  - `product_id` (Many2one -> product.product) - Parent product

### res.company (`models/res_company.py`) - Inherited
- **Added Fields:**
  - `location_dest_id` (Many2one -> stock.location) - For stock transfer destination
  - `picking_type_id` (Many2one -> stock.picking.type) - Operation type for transfers

---

## Data / Cron Jobs
- **ir_sequence.xml:** Sequence "A" + 5 digit padding, no company restriction
- **ir_cron.xml:**
  1. Generate Employee Slots - daily
  2. Reset Draft Slots - every 1 minute (resets 'wait' to 'draft' after 10 min)
  3. Delete Old Slots - daily (removes slots older than 20 days)

## Security
- All models have full CRUD access for all users (no group restriction in ir.model.access.csv)

## Views
- appointment_management.xml - Form/tree views for appointments
- appointment_refund_policy.xml - Refund policy views
- pos_category.xml - POS category with appointment fields
- product.xml - Product form with appointment service fields
- hr_employee.xml - Employee with appointment toggle
- hr_department.xml - Department with time plans
- appointment_employee_slot.xml - Slot management views
- res_company.xml - Company stock settings
- menus.xml - Main menu structure

## Architecture Notes
- Slot system: 30-minute increments, states: draft -> wait -> done/cancel
- Pricing: Per service+department+branch combination, separate inside/outside prices
- Packages: Group multiple services with independent pricing per service
- Stock integration: Appointment completion triggers stock transfers for product components
- Timezone handling: User TZ converted to UTC when creating appointments
