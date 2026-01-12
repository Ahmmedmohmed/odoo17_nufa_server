# Appointment Management System Website

A professional website booking module for Odoo 17 that extends the salon appointment management system with customer-facing booking functionality.

## Features

### 🌐 Website Booking Interface
- Professional, responsive booking page accessible at `/book-appointment`
- Modern UI with brand colors (Black #000000 and Primary #c16d4b)
- Three-step booking process: Selection → Preview → Payment

### 📋 Category-Based Service Selection
- Dynamic category slider showing `pos.category` records marked as appointment categories
- Service grid with both individual services and packages
- Visual service cards with images and descriptions

### 🏢 Flexible Booking Options
- **Inside Branch**: Select branch → employee → date/time
- **Outside Branch**: Customer address input for home services
- Real-time availability checking for time slots

### 📦 Package Support
- Complete package booking workflow
- Individual service configuration within packages
- Dynamic pricing calculation

### 🛒 Live Cart Management
- Real-time cart updates with total calculation
- Add/remove services before checkout
- Session-based cart persistence

### 💳 Integrated Payment Flow
- Draft invoice preview before payment
- Seamless integration with Odoo's payment system
- Automatic appointment status updates after payment

### 👤 Customer Portal Integration
- Dedicated "My Appointments" section in customer portal
- View appointment history and details
- Responsive appointment detail pages

## Technical Architecture

### 🏗️ Built for Odoo 17
- **OWL v2 Components**: Modern JavaScript framework with reactive state management
- **Modular Assets**: Properly declared CSS/JS assets in manifest
- **Security Rules**: Comprehensive access control for portal users
- **Performance Optimized**: Efficient API endpoints and caching

### 🎨 Design System
- **Brand Colors**: Black (#000000) and Primary (#c16d4b) with complementary palette
- **Isolated Styling**: CSS scoped to avoid conflicts with core Odoo pages
- **Responsive Design**: Mobile-first approach with professional UI/UX

### 🔒 Security & Access Control
- User authentication required for booking
- Portal users can only view their own appointments
- Proper record rules and access controls
- CSRF protection on all forms

## Installation

1. **Prerequisites**: Ensure `appointment_management_system` and `appointment_management_system_pos` modules are installed

2. **Install Module**:
   ```bash
   # Place module in addons path
   # Update module list in Odoo
   # Install "Appointment Management System Website"
   ```

3. **Configure Website**:
   - Create appointment categories (`pos.category` with `is_appointment_category = True`)
   - Set up services with proper pricing plans
   - Configure employee slots and availability

## Usage

### For Salon Managers
1. **Setup Categories**: Mark relevant `pos.category` records as appointment categories
2. **Configure Services**: Set up products as appointment services with pricing plans
3. **Create Packages**: Build service packages with multiple offerings
4. **Manage Employees**: Set employee availability and appointment slots

### For Customers
1. **Browse Services**: Visit `/book-appointment` to explore categories and services
2. **Book Appointments**: Follow the three-step booking process
3. **Make Payment**: Complete booking with integrated payment system
4. **Track Appointments**: View booking history in customer portal

## API Endpoints

### Booking Flow APIs
- `GET /book-appointment` - Main booking page
- `POST /book-appointment/api/categories` - Get appointment categories
- `POST /book-appointment/api/services/<category_id>` - Get services by category
- `POST /book-appointment/api/branches/<service_id>` - Get available branches
- `POST /book-appointment/api/employees/<service_id>/<branch_id>` - Get employees
- `POST /book-appointment/api/slots/<service_id>/<employee_id>` - Get time slots
- `POST /book-appointment/api/price/<service_id>` - Get service pricing

### Cart Management
- `POST /book-appointment/api/cart/add` - Add service to cart
- `POST /book-appointment/api/cart/remove` - Remove from cart
- `POST /book-appointment/api/cart` - Get cart contents

### Portal Integration
- `GET /my/appointments` - Customer appointment list
- `GET /my/appointments/<appointment_id>` - Appointment details

## File Structure

```
appointment_management_system_website/
├── __init__.py
├── __manifest__.py
├── README.md
├── controllers/
│   ├── __init__.py
│   └── appointment_website_controller.py
├── models/
│   ├── __init__.py
│   └── appointment_booking.py
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── static/
│   ├── description/
│   │   └── icon.png
│   └── src/
│       ├── css/
│       │   └── booking.css
│       ├── js/
│       │   └── booking.js
│       └── xml/
│           └── booking_templates.xml
├── views/
│   ├── website_templates.xml
│   └── portal_templates.xml
└── data/
    └── website_menu.xml
```

## Dependencies

- `base` - Core Odoo functionality
- `website` - Website framework
- `portal` - Customer portal
- `account` - Invoicing system
- `appointment_management_system` - Core appointment system
- `appointment_management_system_pos` - POS integration

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## License

LGPL-3 - See LICENSE file for details

## Support

For technical support and feature requests, please contact the development team.

---

**Version**: 17.0.1.0.0  
**Odoo Version**: 17.0  
**Author**: Salon Management Team