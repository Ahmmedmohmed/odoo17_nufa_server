# appointment_management_system_pos - Module Memory

## Overview
Odoo 17 POS (Point of Sale) integration module for the appointment management system. Adds appointment booking workflow directly inside the POS interface using OWL components. Allows cashiers to create appointments, add them to POS orders, handle payment, and manage refunds.

**Version:** 1.0  
**Category:** Custom  
**Dependencies:** `appointment_management_system`, `point_of_sale`  
**Application:** Yes  
**Assets:** Loaded into `point_of_sale._assets_pos`

---

## Backend Models

### pos.config (`models/pos_config.py`) - Inherited
- **Added Fields:**
  - `allow_appointment` (Boolean) - Enables appointment functionality in POS
- **Methods:**
  - `_employee_domain_appointment()` - Returns domain for appointment employees filtered by company
- **Also extends:** `res.config.settings` with related `allow_appointment` field

### pos.order (`models/pos_order.py`) - Inherited
- **Added Fields:**
  - `isAppointment` (Boolean) - Flags order as containing appointment services
- **Key Methods:**
  - `_process_order()` - Override: sets isAppointment=True if any line has appointment service
  - `search_paid_order_ids()` - Override: filters OUT appointment orders from paid orders list
  - `search_appointment_order_ids()` - NEW: searches specifically for appointment orders (isAppointment=True, not draft/cancelled)
  - `_export_appointment_for_ui(order)` - Exports appointment order data for frontend, filters lines by state='2' (Approved)
  - `export_appointment_for_ui()` - Batch export using mapped()
- **Heavy imports:** collections, datetime, functools, itertools, markupsafe, base64, logging, psycopg2, pytz, re

### pos.order.line (`models/pos_order_line.py`) - Inherited
- **Added Fields:**
  - `is_appointment_line` (Boolean)
  - `employee_name` (Char)
  - `branch_name` (Char)
  - `appointment_type` (Char)
  - `date` (Char)
  - `slot_name` (Char)
  - `appointment_id` (Many2one -> appointment.management, ondelete='restrict')
- **Key Methods:**
  - `_export_appointment_for_ui(orderline)` - Exports line with refund policy price calculation (applies percentage based on hours_before_appointment)
  - `export_appointment_for_ui()` - Batch export

### pos.session (`models/pos_session.py`) - Inherited
- **Data Loading (when allow_appointment=True):**
  - `appointment.product.category` - POS categories with is_appointment_category=True
  - `appointment.product.service` - Products with is_appointment_service=True, grouped by categ_id
  - `appointment.package.line` - All package lines, indexed by id
  - Also extends `_loader_params_product_product()` to include appointment fields
- **Note:** Has `print(service_by_categ_id)` debug statement in `_get_pos_ui_appointment_product_service`

---

## Frontend (OWL) Components

### AppointmentButton (`static/src/app/AppointmentButton/`)
- **Template:** `appointment_management_system_pos.AppointmentButton`
- **Location:** Added as control button on ProductScreen (condition: `config.allow_appointment`)
- **Behavior:** Disabled if no partner selected on order. Opens AppointmentPopup. On confirm, iterates `appointmentDetails.services`, adds each as order line with custom price and appointment metadata.
- **Note:** Contains `debugger` statement in click handler

### AppointmentPopup (`static/src/app/AppointmentPopup/`)
- **Template:** `appointment_management_system_pos.AppointmentPopup`
- **Extends:** AbstractAwaitablePopup
- **Components:** AppointmentSeviceList, AppointmentSeviceDetails, AppointmentSevicePackSelection, CategorySelector, Input
- **Behavior:**
  - Displays appointment categories as tabs
  - Shows products filtered by category and search
  - On product select: initializes `pos.appointmentDetails` with service data structure
  - For packages: loads all package lines as individual services
  - Calls `pos.getBranches()` on service selection
  - On confirm: validates all services have required fields, calls `createAppointments()` (RPC to `product.product.action_create_appointments`)
  - On cancel: clears selection state

### AppointmentSeviceDetails (`static/src/app/AppointmentSeviceDetails/`)
- **Template:** `appointment_management_system_pos.AppointmentSeviceDetails`
- **Purpose:** Service configuration form (shown after selecting a service)
- **UI:** Table with dropdowns for Type (inside/outside), Branch, Employee, Date, Appointments (time slots)
- **Cascade logic:** Each dropdown change resets downstream selections and triggers data fetch:
  - Type change -> fetch branches
  - Branch change -> fetch employees
  - Employee change -> fetch dates
  - Date change -> fetch available slots
- **Data fetching:** Uses `orm.call()` to `product.product` methods:
  - `action_get_appointment_branch`
  - `action_get_appointment_employee`
  - `action_get_appointment_date`
  - `action_get_appointment_employee_slot`
- **For packages:** Shows service tabs at top for switching between services

### AppointmentSeviceItem (`static/src/app/AppointmentSeviceItem/`)
- **Extends:** ProductCard
- **Added Props:** `onRemoveClick`, `orderMenu`
- **Behavior:** Highlights selected service with green border, shows remove button

### AppointmentSeviceList (`static/src/app/AppointmentSeviceList/`)
- **Components:** AppointmentSeviceItem
- **Behavior:** Grid of service items with click and remove handlers, product info popup support

### AppointmentSevicePackSelection (`static/src/app/AppointmentSevicePackSelection/`)
- **Purpose:** Tab-like selection for services within a package
- **Behavior:** Click selects service, highlights with green border

---

## Model Overrides (Frontend)

### Order (`static/src/overrides/models/order.js`)
- **Patches:** `Order.prototype.set_orderline_options`
- **Adds:** appointment_id, appointment_name, employee_name, branch_name, appointment_type, date, slot_name, is_appointment_line to orderline from options

### Orderline (`static/src/overrides/models/orderline.js`)
- **Patches:** `Orderline.prototype`
- **Overrides:** `setup`, `export_as_JSON`, `init_from_JSON`, `getDisplayData`
- **Adds all appointment fields** to orderline lifecycle (creation, serialization, deserialization, display)

### PosStore (`static/src/overrides/models/pos_store.js`)
- **Patches:** `PosStore.prototype._processData`
- **Loads (when allow_appointment):**
  - `appointment_categories` from loaded data
  - `appointment_services` and `appointment_services_by_categ_id`
  - `appointment_package_by_id`
- **Methods:**
  - `getBranches(selectedService)` - Fetches branches for service via RPC

---

## Screen Overrides

### PaymentScreen (`static/src/overrides/payment_screen/payment_screen.js`)
- **Patches:** `PaymentScreen.prototype.afterOrderValidation`
- **Behavior:** After order validation, calls `action_update_appointment` for each appointment line:
  - Normal payment: sets status='2' (Approved)
  - Refund (refunded_orderline_id): sets status='3' (Completed)

### ProductScreen (`static/src/overrides/product_screen/product_screen.xml`)
- **Extension:** Adds appointment details (name, employee, branch, type, date-slot) inside Orderline display

### TicketScreen (`static/src/overrides/ticket_screen/ticket_screen.js`)
- **Patches:** Multiple methods for "APPOINTMENT" filter tab:
  - `getNumpadButtons()` - Disables most numpad buttons for appointment filter
  - `_getFilterOptions()` - Adds "APPOINTMENT" filter option
  - `onFilterSelected()` / `onSearch()` / `getFilteredOrderList()` - Handles appointment filter
  - `_fetchAppointmentOrders()` - Fetches appointment orders via `pos.order.search_appointment_order_ids`, caches results
  - `addAdditionalRefundInfo()` - Copies appointment data to refund order lines

### TicketScreen XML (`static/src/overrides/ticket_screen/ticket_screen.xml`)
- **Extension:** Shows appointment details in order line display

### OrderReceipt XML (`static/src/overrides/models/OrderReceipt.xml`)
- **Extension:** Adds appointment details to receipt printout

---

## CSS (`static/src/css/PosSelectionCombo.css`)
- Styles for appointment popup: full-width modal, product grid with green border highlight, remove buttons, scrollable selection area

## Backend Views
- **pos_config.xml:** Adds `allow_appointment` toggle in POS settings under Interface section
- **pos_order.xml:** Adds `is_appointment_line` (hidden) and `appointment_id` (optional) columns to POS order line tree

---

## Data Flow
1. Cashier selects partner -> clicks "Appointments" button
2. Popup opens -> select category -> select service (or package)
3. Configure: type -> branch -> employee -> date -> time slot (cascade dropdowns)
4. For packages: configure each service independently via tabs
5. Confirm -> `action_create_appointments` RPC creates appointment records with state='1' and slots='wait'
6. Products added to POS order with custom prices and appointment metadata
7. Payment -> `afterOrderValidation` updates appointment to state='2', slots to 'done'
8. Refund flow: ticket screen APPOINTMENT filter -> refund -> marks appointment state='3'

## Product Visibility
- Appointment products (is_appointment_service/is_appointment_package) are hidden from the main POS product grid
- Override in `static/src/overrides/product_screen/product_list.js` patches `ProductsWidget.productsToDisplay` to filter them out
- They remain visible only inside the Appointment popup

## Known Issues / Debug Artifacts
- `debugger` statement in AppointmentButton click handler
- `print()` statement in pos_session.py `_get_pos_ui_appointment_product_service`
- Commented out code in multiple files (pos_store.js, AppointmentSevicePackSelection)
- Typo: "Sevice" instead of "Service" in all component folder/file names
