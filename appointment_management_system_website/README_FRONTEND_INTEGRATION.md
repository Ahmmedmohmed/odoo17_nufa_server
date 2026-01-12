# Salon Booking System - Frontend Integration Guide

This document provides step-by-step instructions for integrating the redesigned frontend booking system into your Odoo 17 appointment management module.

## 🎨 Design Overview

The booking system has been redesigned with a modern, clean interface using:
- **Primary Color**: #c16d4b (Warm brown)
- **Secondary**: #000000 (Black)
- **Accent 1**: #4b8fc1 (Cool blue)
- **Accent 2**: #f4e5a1 (Warm cream)

## 📁 File Structure

The frontend system consists of these key files:

```
appointment_management_system_website/
├── views/
│   └── website_templates.xml      # QWeb templates for all pages
├── static/src/
│   ├── css/
│   │   └── booking.css           # Enhanced styling with calendar grid
│   └── js/
│       └── booking.js            # Interactive functionality with OWL v2
├── BACKEND_INTEGRATION.md        # API endpoints documentation
└── README_FRONTEND_INTEGRATION.md # This file
```

## 🚀 Integration Steps

### Step 1: Update Assets Manifest

Ensure your `__manifest__.py` includes the frontend assets:

```python
'assets': {
    'web.assets_frontend': [
        'appointment_management_system_website/static/src/css/booking.css',
        'appointment_management_system_website/static/src/js/booking.js',
    ],
},
```

### Step 2: Update Website Templates

The `website_templates.xml` file contains these main templates:

- `booking_layout` - Base layout with cart sidebar
- `category_selection` - Service category selection page
- `service_selection` - Individual services selection
- `booking_calendar` - Calendar grid for slot selection
- `package_service_selection` - Package booking workflow
- `location_selection` - Inside/outside location choice
- `address_input` - Address form for outside bookings
- `booking_home` - Landing page
- `cart_widget` - Shopping cart component

### Step 3: Update Controllers

Your controller should handle these routes:

```python
# Main pages
@http.route('/appointment/booking', type='http', auth='public', website=True)
def booking_home(self, **kwargs):
    return request.render('appointment_management_system_website.booking_home')

@http.route('/appointment/booking/categories', type='http', auth='public', website=True)
def booking_categories(self, **kwargs):
    categories = self._get_appointment_categories()
    return request.render('appointment_management_system_website.category_selection', {
        'categories': categories
    })

@http.route('/appointment/booking/services/<int:category_id>', type='http', auth='public', website=True)
def booking_services(self, category_id, **kwargs):
    services = self._get_category_services(category_id)
    return request.render('appointment_management_system_website.service_selection', {
        'services': services,
        'category_id': category_id
    })

@http.route('/appointment/booking/calendar', type='http', auth='public', website=True)
def booking_calendar(self, **kwargs):
    return request.render('appointment_management_system_website.booking_calendar')
```

### Step 4: Implement API Endpoints

Create these API endpoints as documented in `BACKEND_INTEGRATION.md`:

```python
@http.route('/book-appointment/api/categories', type='json', auth='public')
def api_get_categories(self, **kwargs):
    # Return appointment categories
    pass

@http.route('/book-appointment/api/services', type='json', auth='public')
def api_get_services(self, category_id, **kwargs):
    # Return services for category
    pass

@http.route('/book-appointment/api/slots', type='json', auth='public')
def api_get_slots(self, date, employee_id=None, **kwargs):
    # Return available slots
    pass

@http.route('/book-appointment/api/cart/add', type='json', auth='user')
def api_add_to_cart(self, slot_id, service_id, **kwargs):
    # Add booking to cart and reserve slot
    pass

# ... more API endpoints
```

### Step 5: Calendar Grid Implementation

The calendar grid is the core feature. It displays:

1. **Header**: Employee names with photos and branch info
2. **Time Column**: 8 AM to 7 PM time slots
3. **Slot Cards**: Available appointment slots with:
   - Service price
   - End time
   - Branch name  
   - "Book" button

**CSS Classes for Calendar**:
- `.cal` - Main calendar container
- `.cal-head` - Header with employee columns
- `.cal-body` - Body with time slots
- `.slot-card` - Individual bookable slots
- `.emp-col` - Employee columns
- `.time-col` - Time column

### Step 6: Cart Functionality

The cart system supports:

- **Single Services**: Individual appointment bookings
- **Package Services**: Multiple services booked together
- **Mixed Cart**: Combination of single and package services
- **Real-time Updates**: Cart updates as slots are added/removed
- **Slot Reservation**: Automatic 10-minute hold on selected slots

**Cart Features**:
- Add/remove individual items
- Clear all items
- Show pricing breakdown
- Display appointment details
- Proceed to checkout

### Step 7: Mobile Responsiveness

The design includes mobile-specific features:
- Responsive grid layouts
- Touch-friendly buttons
- Collapsible cart sidebar
- Optimized calendar for smaller screens
- Keyboard navigation support

## 🔧 Customization Options

### Theme Colors

Update the CSS variables in `booking.css`:

```css
:root {
    --appointment-black: #000000;
    --appointment-primary: #c16d4b;          /* Your brand color */
    --appointment-complementary-1: #4b8fc1;  /* Accent color 1 */
    --appointment-complementary-2: #f4e5a1;  /* Accent color 2 */
}
```

### Calendar Settings

Modify calendar hours in `booking.js`:

```javascript
const startHour = 8; // 8 AM
const endHour = 19;  // 7 PM
```

### Slot Duration

Configure default slot duration:

```javascript
const slotDuration = 30; // 30 minutes
```

## 🔌 Backend Integration

### Required Models

Ensure these models exist and have the required fields:

1. **pos.category** - Service categories
   - `name` - Category name
   - `image_1920` - Category image
   - `is_appointment_category` - Boolean flag

2. **product.template** - Services
   - `name` - Service name  
   - `description` - Service description
   - `is_package` - Package flag
   - `package_services` - Related services for packages

3. **appointment.employee.slot** - Time slots
   - `employee_id` - Employee reference
   - `date` - Appointment date
   - `time` - Appointment time (float)
   - `state` - Slot state ('draft', 'wait', 'done', 'cancel')

4. **hr.employee** - Staff members
   - `name` - Employee name
   - `image_1920` - Employee photo
   - `department_id` - Branch/department

### Slot State Management

Critical for preventing double-bookings:

1. **Draft**: Visible to all users, available for booking
2. **Wait**: Reserved (in cart), invisible to others, auto-release after 10 minutes
3. **Done**: Confirmed booking, permanently unavailable
4. **Cancel**: Cancelled appointment, can be made available again

## 📱 User Flow

### Single Service Booking
1. Select category → 2. Choose service → 3. Pick location → 4. Book calendar slot → 5. Add to cart

### Package Booking  
1. Select category → 2. Choose package → 3. Configure each service individually → 4. Add all to cart

### Cart & Checkout
1. Review cart items → 2. Proceed to invoice preview → 3. Complete payment → 4. Confirmation

## 🧪 Testing Checklist

- [ ] Category selection loads and displays properly
- [ ] Service selection shows correct services for category  
- [ ] Location selection (inside/outside) works
- [ ] Address input appears for outside bookings
- [ ] Calendar displays available slots correctly
- [ ] Employee dropdown opens reliably
- [ ] Date selection updates available slots
- [ ] Slot booking adds to cart
- [ ] Cart displays items correctly
- [ ] Package booking flow works end-to-end
- [ ] Mobile layout is responsive
- [ ] Checkout process completes successfully

## 🔍 Troubleshooting

### Common Issues

**Calendar not loading slots:**
- Check API endpoint `/book-appointment/api/slots`
- Verify employee and date parameters
- Ensure slots exist in database with state='draft'

**Employee dropdown not working:**
- Check JavaScript console for errors
- Verify employee data has required fields
- Test click event handlers

**Cart not updating:**
- Check session management
- Verify cart API endpoints
- Test slot reservation logic

**Mobile layout issues:**
- Check CSS media queries
- Test on actual mobile devices
- Verify touch event handling

### Debug Mode

Enable debug mode in booking.js:

```javascript
const DEBUG_MODE = true; // Set to true for console logging
```

## 📞 Support

For integration support:
1. Check `BACKEND_INTEGRATION.md` for API specifications
2. Review browser console for JavaScript errors
3. Test individual API endpoints with Postman/curl
4. Verify database slot state management

## 🎯 Performance Tips

1. **Lazy Loading**: Load categories/services on demand
2. **Caching**: Cache branch and employee data
3. **Debouncing**: Limit API call frequency
4. **Background Updates**: Use async for cart operations
5. **Mobile Optimization**: Test on actual devices

The booking system is designed to be production-ready with proper error handling, accessibility features, and responsive design for an optimal user experience across all devices.