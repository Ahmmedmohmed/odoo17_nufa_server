# appointment_management_system_website - Module Memory

## Overview
Odoo 17 website/eCommerce integration module for appointment booking. Provides a public-facing booking interface, shopping cart integration with Odoo eCommerce, portal for customers to manage their appointments, and payment processing through Odoo's payment system.

**Version:** 17.0.1.0.0  
**Category:** Website/Website  
**Dependencies:** `base`, `website`, `website_sale`, `sale`, `portal`, `account`, `appointment_management_system`  
**Application:** No  
**License:** LGPL-3

---

## Backend Models

### appointment.management (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `website_booking` (Boolean)
  - `customer_address` (Text)
  - `sale_order_id` (Many2one -> sale.order)
  - `order_line_id` (Many2one -> sale.order.line)
  - `currency_id` (Many2one -> res.currency, computed from sale_order)
  - `cart_reservation_expiry` (Datetime) - 30-min reservation window
  - `slot_reserved` (Boolean)
  - `customer_street`, `customer_phone`, `customer_city` (Char) - For outside appointments
  - `customer_notes` (Text)
  - `cancel_reason` (Text) - Portal cancellation
  - `employee_rating` (Selection 1-5 stars)
  - `rating_comment` (Text)
  - `has_sale_order` (Boolean, computed)
- **Key Methods:**
  - `create_from_cart(appointment_data)` - Creates appointment with state='1', reserves slots with 30-min expiry
  - `confirm_appointment_payment(sale_order)` - Sets state='2', slots to 'done', links sale_order
  - `portal_cancel_appointment(reason)` - Cancels from portal, frees slots back to 'draft'
  - `portal_submit_rating(rating, comment)` - Maps 1-5 star rating to service_rate (0-3)
  - `_get_appointment_datetime(appointment_data)` - Combines date + slot time with timezone conversion (user TZ -> UTC). **Has +1 hour workaround** for frontend timezone handling issue
  - `cancel_reservation()` - Frees slots, sets state='4'
  - `cleanup_expired_reservations()` - Cron: cancels reservations past cart_reservation_expiry
  - `action_view_sale_order()` - Smart button action

### appointment.employee.slot (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `reserved_until` (Datetime)
  - `reserved_by` (Integer - appointment ID)
- **Methods:**
  - `is_available_for_booking()` - Checks draft state or expired wait reservation (auto-cleanup)
  - `reserve_slot(appointment_id, minutes)` - Sets state='wait' with expiry
  - `confirm_booking()` - Sets state='done', clears reservation

### res.partner (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `appointment_count` (Integer, computed)
- **Methods:** `action_view_appointments()`

### product.product (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `currency_id` (Many2one -> res.currency)
- **Methods:**
  - `get_website_appointment_price(appointment_type, branch_id, department_id)` - Price lookup for website
  - `get_website_appointment_duration(appointment_type, branch_id, department_id)` - Duration in slots

### sale.order (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `appointment_ids` (One2many -> appointment.management via sale_order_id)
  - `appointment_count` (Integer, computed)
- **Overrides:**
  - `action_confirm()` - Confirms pending appointments when order is confirmed
  - `action_view_appointments()` - Smart button

### sale.order.line (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `appointment_id` (Many2one -> appointment.management)
- **Overrides:**
  - `unlink()` - Cancels associated appointment reservations when line is removed

### sale.order (`models/sale_order.py`) - Separate file, also inherited
- **Added Fields:**
  - `appointment_count` (Integer, computed via order_line appointments)
- **Methods:** `action_view_appointments()` - Through order lines

### sale.order.line (`models/sale_order_line.py`) - Inherited
- **Added Fields:**
  - `is_appointment_custom_price` (Boolean) - Prevents price recalculation
- **Overrides:**
  - `_compute_price_unit()` - Skips computation for appointment custom prices
  - `_get_display_price()` / `_get_price_reduce()` - Returns stored price for appointment lines
  - `_onchange_product_id_check_availability()` - Preserves custom price
  - `create()` - Stores and restores custom price after super create
  - `write()` - Respects `skip_price_computation` context flag

### website (`models/appointment_booking.py`) - Inherited
- **Overrides:**
  - `sale_confirm_order()` - Confirms appointments after website sale

### payment.transaction (`models/appointment_booking.py`) - Inherited
- **Overrides:** `_set_pending()`, `_set_authorized()`, `_set_done()` - All call `_confirm_appointment_orders()` which confirms sale orders with pending appointments

### account.payment (`models/appointment_booking.py`) - Inherited
- **Overrides:**
  - `action_post()` - Confirms appointments when payment is posted

### account.move (`models/appointment_booking.py`) - Inherited
- **Added Fields:**
  - `appointment_ids` (One2many, computed) - Found through sale_line_ids or time-range fallback
  - `appointment_count` (Integer, computed)
- **Overrides:**
  - `action_post()` - Confirms appointments when invoice is posted/paid
  - `_write()` - Catches payment_state changes to confirm appointments
  - `action_view_appointments()` - Smart button

---

## Controllers (`controllers/appointment_website_controller.py`)

### AppointmentPortalController (extends CustomerPortal)
- **Routes:**
  - `GET /my/appointments` - Portal appointment list (paginated, sortable)
  - `GET /my/appointments/<id>` - Appointment detail page
  - `POST /my/appointments/<id>/cancel` - Cancel appointment (csrf=False)
  - `POST /my/appointments/<id>/rate` - Submit rating (csrf=False)
- **Overrides:** `_prepare_portal_layout_values()` - Adds appointment_count

### AppointmentWebsiteController (extends http.Controller)

#### Page Routes:
- `GET /appointment/booking` - Category selection page (auth required)
- `GET /appointment/booking/services/<category_id>` - Service selection (auth required)
- `GET /appointment/booking/calendar` - Calendar booking page with cart (auth required)
- `GET /book-appointment` - Legacy redirect to /appointment/booking/calendar
- `GET /book-appointment/preview-invoice` - Invoice preview before payment
- `POST /book-appointment/confirm-booking` - Creates appointments + invoice, redirects to payment
- `GET /book-appointment/payment-success` - Post-payment success page
- `GET /appointment/proceed-to-checkout` - Redirects to /shop/checkout

#### JSON API Routes (type='json'):
- `POST /appointment/cart/add` - Add to Odoo eCommerce cart + create draft appointment
- `POST /appointment/confirm/<id>` - Manual appointment confirmation (testing)
- `POST /appointment/status/<id>` - Get appointment/slot status (debugging)
- `POST /book-appointment/api/categories` - Get appointment categories
- `POST /book-appointment/api/services` - Get services by category (filtered by plan existence)
- `POST /book-appointment/api/all-services` - Get all services with plans
- `POST /book-appointment/api/all-employees` - Get all appointment employees with photos
- `POST /book-appointment/api/service-plans` - Get plans with departments, employees, pricing
- `POST /book-appointment/api/branches` - Get branches for service
- `POST /book-appointment/api/employees` - Get employees with photos for service/branch
- `POST /book-appointment/api/available-dates` - Get available dates
- `POST /book-appointment/api/slots` - Get time slots (uses service method, fallback to direct DB)
- `POST /book-appointment/api/summary-price` - Get price for summary display
- `POST /book-appointment/api/employee-name` - Get employee name
- `POST /book-appointment/api/package-services/<id>` - Get package services
- `POST /book-appointment/api/package-services` - Get package services (alternate route)

#### Session Cart API Routes (type='json'):
- `POST /book-appointment/api/cart/add` - Add to session cart + reserve slots
- `POST /book-appointment/api/cart/remove` - Remove from session cart + release slots
- `POST /book-appointment/api/cart/remove-all` - Clear entire cart + release all slots
- `POST /book-appointment/api/cart` - Get current cart contents

#### HTTP API Routes:
- `POST /book-appointment/api/price-dynamic` - Dynamic pricing (HTTP POST with JSON body)

#### Debug/Test Routes:
- `POST /book-appointment/api/test-plans` - Check plan counts
- `POST /book-appointment/api/debug-services` - Debug service loading

#### Key Helper Methods:
- `_handle_single_service_cart_addition()` - Creates appointment + Odoo sale order line
- `_handle_package_cart_addition()` - Creates multiple appointments + single package order line
- `_get_slot_price()`, `_get_service_duration()`, `_calculate_end_time()`, `_get_package_line_for_service()`
- `_filter_services_with_plans()` - Filters services that have pricing plans

---

## Frontend

### Templates (views/)
- **website_templates.xml** (~5132 lines) - Main booking interface:
  - `category_selection` - Grid of appointment categories
  - `service_selection` - Service cards with images
  - `booking_calendar` - Main booking page with sidebar service list, calendar, slot selection, cart
  - `invoice_preview` - Pre-payment invoice review
  - `payment_success` - Confirmation page
- **portal_templates.xml** - Portal views:
  - `portal_appointments` - Appointment list in /my portal
  - `portal_appointment_detail` - Single appointment detail with cancel/rate actions
  - `appointment_cancelled` / `rating_submitted` - Confirmation pages
- **authentication_required_template.xml** - Login prompt for unauthenticated users
- **appointment_views.xml** - Backend appointment form with website fields
- **sale_order_line_views.xml** - Sale order line with appointment fields

### JavaScript (`static/src/js/`)
- **booking.js** (~3166 lines) - Main booking interface logic:
  - Category/service selection
  - Employee selection with photos
  - Calendar date picker
  - Time slot selection
  - Cart management (session-based)
  - Dynamic pricing
  - Package service booking flow
  - Checkout integration
- **booking_minimal.js** - Minimal/lightweight version

### CSS (`static/src/css/`)
- **booking.css** (~1886 lines) - Complete booking interface styling
- **calendar.css** - Calendar-specific styles

### XML Templates (`static/src/xml/`)
- **booking_templates.xml** - OWL/QWeb templates for frontend components

---

## Data Files

### Cron Jobs (`data/ir_cron.xml`)
- `cleanup_expired_reservations` - Every 5 minutes, cancels expired cart reservations

### Website Menu (`data/website_menu.xml`)
- Adds "Book Appointment" menu item to website navigation

### Sample Categories (`data/sample_categories.xml`)
- Sample appointment category data

---

## Security

### Groups (`security/security.xml`)
- `group_appointment_website_user` - Hidden group for website booking access
- Portal users and internal users both get this group via implied_ids

### Record Rules
- `rule_appointment_management_portal` - Portal users can only READ their own appointments

### Access Rights (`security/ir.model.access.csv`)
- Portal users: read-only on appointment.management
- Website users: read+create on appointment.management, account.move, account.move.line

---

## Tests (`tests/`)
- `test_appointment_booking.py` - Test cases for booking functionality

---

## Architecture / Data Flow

### Two Cart Systems:
1. **Session Cart** (`/book-appointment/api/cart/*`) - Stores appointments in session, reserves slots with 'wait' state
2. **Odoo eCommerce Cart** (`/appointment/cart/add`) - Creates actual sale.order + sale.order.line + appointment.management records

### Booking Flow (eCommerce):
1. User browses categories -> services -> selects service
2. Selects branch -> employee -> date -> time slot
3. "Add to Cart" -> Creates appointment (state='1'), reserves slots ('wait'), creates sale order line
4. Checkout via Odoo eCommerce (/shop/checkout)
5. Payment triggers: payment.transaction -> sale.order.action_confirm() -> appointment.confirm_appointment_payment() -> state='2', slots='done'

### Booking Flow (Session Cart / Legacy):
1. Same service selection
2. "Add to Cart" -> Reserves slots in session, stores in session cart
3. Preview Invoice -> Confirm Booking -> Creates appointments + account.move
4. Redirect to invoice payment -> payment_success updates to state='2'

### Package Handling:
- Packages create ONE sale order line with total price
- Multiple appointment.management records (one per service in package)
- All linked to same sale_order and order_line

---

## Known Issues / Notes
- **Timezone workaround:** `_get_appointment_datetime` adds +1 hour to compensate for frontend TZ handling (Asia/Riyadh context)
- **Duplicate route:** `get_package_services` defined twice (different URL patterns)
- **Debug endpoints:** test-plans, debug-services, appointment status/confirm still active
- **csrf=False** on portal cancel and rate routes
- **sudo() usage** extensively in controllers for accessing appointment/slot/employee data
- **Duplicate SaleOrder inheritance** in both `appointment_booking.py` and `sale_order.py`
- **Post-init hook** in `__init__.py` creates website menu (may duplicate with XML data)
- Large frontend files: website_templates.xml (5132 lines), booking.js (3166 lines), booking.css (1886 lines)
