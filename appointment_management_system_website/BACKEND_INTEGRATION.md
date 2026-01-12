# Backend Integration Guide for Salon Booking System

This document outlines the required backend API endpoints and their payloads for the frontend booking system to function properly.

## Theme Colors Used

- **Primary**: #c16d4b (Warm brown)
- **Black**: #000000 
- **Complementary 1**: #4b8fc1 (Cool blue)
- **Complementary 2**: #f4e5a1 (Warm cream)

## Required API Endpoints

### 1. Categories API

**Endpoint**: `/book-appointment/api/categories`  
**Method**: POST  
**Description**: Fetch all appointment categories

**Response Format**:
```json
[
  {
    "id": 1,
    "name": "Hair Services",
    "image": "/web/image/pos.category/1/image_1920" // optional
  },
  {
    "id": 2,
    "name": "Spa Services",
    "image": "/web/image/pos.category/2/image_1920"
  }
]
```

### 2. Services API

**Endpoint**: `/book-appointment/api/services`  
**Method**: POST  
**Payload**: `{"category_id": 1}`

**Response Format**:
```json
[
  {
    "id": 1,
    "name": "Haircut",
    "description": "Professional haircut service",
    "is_package": false,
    "image": "/web/image/product.template/1/image_1920"
  },
  {
    "id": 2,
    "name": "Spa Package",
    "description": "Complete spa experience",
    "is_package": true,
    "package_services": [
      {"id": 3, "name": "Facial"},
      {"id": 4, "name": "Massage"}
    ]
  }
]
```

### 3. Branches API

**Endpoint**: `/book-appointment/api/branches`  
**Method**: POST

**Response Format**:
```json
[
  {
    "id": 1,
    "name": "Main Branch",
    "address": "123 Main St"
  },
  {
    "id": 2,
    "name": "Downtown Branch", 
    "address": "456 Downtown Ave"
  }
]
```

### 4. Employees API

**Endpoint**: `/book-appointment/api/employees`  
**Method**: POST  
**Payload**: `{"branch_id": 1}` (optional)

**Response Format**:
```json
[
  {
    "id": 1,
    "name": "Sarah Johnson",
    "branch_id": 1,
    "branch_name": "Main Branch",
    "image": "/web/image/hr.employee/1/image_1920"
  },
  {
    "id": 2,
    "name": "Mike Wilson",
    "branch_id": 1,
    "branch_name": "Main Branch",
    "image": false
  }
]
```

### 5. Available Dates API

**Endpoint**: `/book-appointment/api/available-dates`  
**Method**: POST  
**Payload**: 
```json
{
  "service_id": 1,
  "branch_id": 1,
  "location_type": "inside"
}
```

**Response Format**:
```json
["2024-01-15", "2024-01-16", "2024-01-17"]
```

### 6. Available Slots API

**Endpoint**: `/book-appointment/api/slots`  
**Method**: POST  
**Payload**: 
```json
{
  "date": "2024-01-15",
  "service_id": 1,
  "employee_id": 1,
  "branch_id": 1,
  "location_type": "inside"
}
```

**Response Format**:
```json
[
  {
    "id": 1,
    "employee_id": 1,
    "time": "09:00",
    "duration": 60,
    "state": "draft",
    "price": 50.00,
    "end_time": "10:00"
  },
  {
    "id": 2,
    "employee_id": 1,
    "time": "10:30",
    "duration": 60,
    "state": "draft",
    "price": 50.00,
    "end_time": "11:30"
  }
]
```

### 7. Calendar Grid Slots API (For Calendar View)

**Endpoint**: `/book-appointment/api/calendar-slots`  
**Method**: POST  
**Payload**: 
```json
{
  "date": "2024-01-15",
  "employee_ids": [1, 2, 3],
  "service_id": 1
}
```

**Response Format**:
```json
{
  "employees": [
    {
      "id": 1,
      "name": "Sarah Johnson",
      "branch_name": "Main Branch"
    }
  ],
  "slots": [
    {
      "id": 1,
      "employee_id": 1,
      "time": "09:00",
      "duration": 60,
      "state": "draft",
      "price": 50.00,
      "branch_name": "Main Branch"
    }
  ]
}
```

## Cart Management APIs

### 8. Add to Cart API

**Endpoint**: `/book-appointment/api/cart/add`  
**Method**: POST  
**Payload** (Single Service):
```json
{
  "slot_id": 1,
  "service_id": 1,
  "employee_id": 1,
  "location_type": "inside",
  "address": "" // required if location_type is "outside"
}
```

**Payload** (Package):
```json
{
  "service_data": {
    "service_id": 2,
    "package_id": 2,
    "service_name": "Spa Package",
    "is_package": true,
    "package_services": {
      "3": {
        "service_name": "Facial",
        "employee_name": "Sarah Johnson",
        "slot_id": 1,
        "date": "2024-01-15",
        "time": "09:00",
        "price": 40.00,
        "location_type": "inside",
        "branch_id": 1
      },
      "4": {
        "service_name": "Massage", 
        "employee_name": "Mike Wilson",
        "slot_id": 2,
        "date": "2024-01-15",
        "time": "11:00",
        "price": 60.00,
        "location_type": "inside",
        "branch_id": 1
      }
    },
    "price": 100.00
  }
}
```

**Response Format**:
```json
{
  "success": true,
  "cart_key": "item_1234567890_abcdef123"
}
```

### 9. Remove from Cart API

**Endpoint**: `/book-appointment/api/cart/remove`  
**Method**: POST  
**Payload**: `{"item_id": "item_1234567890_abcdef123"}`

**Response Format**:
```json
{"success": true}
```

### 10. Clear Cart API

**Endpoint**: `/book-appointment/api/cart/clear`  
**Method**: POST

**Response Format**:
```json
{"success": true}
```

### 11. Get Cart API

**Endpoint**: `/book-appointment/api/cart`  
**Method**: POST

**Response Format**:
```json
{
  "item_1234567890_abcdef123": {
    "service_id": 1,
    "service_name": "Haircut",
    "employee_name": "Sarah Johnson",
    "employee_id": 1,
    "branch_name": "Main Branch",
    "date": "2024-01-15",
    "time_slot": "09:00 AM",
    "price": 50.00,
    "location_type": "inside",
    "is_package": false
  },
  "item_0987654321_fedcba321": {
    "service_id": 2,
    "service_name": "Spa Package",
    "price": 100.00,
    "is_package": true,
    "package_services": {
      "3": {
        "service_name": "Facial",
        "employee_name": "Sarah Johnson"
      },
      "4": {
        "service_name": "Massage",
        "employee_name": "Mike Wilson"
      }
    }
  }
}
```

### 12. Checkout API

**Endpoint**: `/book-appointment/api/checkout`  
**Method**: POST  
**Payload**: 
```json
{
  "cart_items": [/* cart items array */]
}
```

**Response Format**:
```json
{
  "success": true,
  "checkout_url": "/book-appointment/invoice-preview"
}
```

## Slot State Management

### Important: Slot Reservation Logic

1. **Draft State**: Slots are visible to all users
2. **Wait State**: Slots are reserved (added to cart) but not paid - invisible to other users
3. **Done State**: Slots are booked and paid - invisible to other users
4. **Auto-Release**: Slots in "wait" state should automatically revert to "draft" after 10 minutes if not paid

### Database Table Reference

The frontend expects slots to come from the `appointment.employee.slot` table with these fields:
- `id`: Unique slot identifier
- `employee_id`: Reference to hr.employee
- `date`: Date of the slot
- `time`: Time as float (e.g., 9.5 for 9:30 AM)
- `state`: One of 'draft', 'wait', 'done', 'cancel'
- `name`: Human-readable time (e.g., "09:30")

## Client-Side Validations

The frontend performs these validations:
1. **Address Required**: For "outside" bookings, address must be provided
2. **User Authentication**: User must be logged in to proceed to checkout
3. **Slot Availability**: Slots are checked before adding to cart
4. **Form Completion**: All required fields must be filled

## Calendar UI Features

### Single Service Booking
- Vertical time axis (8 AM - 7 PM)
- Horizontal columns for employees
- Each slot shows: price, end time, branch name, "Book" button
- Responsive design for mobile

### Package Booking
- Sequential booking of each service in package
- Same calendar UI for each service
- Progress tracking through package services
- All services added to cart together at the end

## Error Handling

The frontend expects standardized error responses:
```json
{
  "success": false,
  "error": "Slot no longer available"
}
```

Common error scenarios:
- Slot already booked by another user
- Invalid employee/branch/service combination
- User not authenticated
- Required fields missing

## Browser Support

The booking system supports:
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers (iOS Safari, Chrome Mobile)
- Keyboard navigation for accessibility
- Screen reader compatibility

## Performance Considerations

1. **Lazy Loading**: Categories, services, and slots are loaded on demand
2. **Caching**: Employee and branch data can be cached client-side
3. **Debouncing**: API calls are debounced to prevent excessive requests
4. **Background Updates**: Cart updates and slot reservations happen asynchronously