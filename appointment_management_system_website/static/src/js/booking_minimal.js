// Minimal booking system with just the essential functions
(function () {
    'use strict';

    // Global functions for template onclick handlers
    window.selectCategory = function(element) {
        const categoryId = element.dataset.categoryId;
        
        // Store category selection in sessionStorage for back navigation
        sessionStorage.setItem('selectedCategory', categoryId);
        
        // Navigate to services page
        window.location.href = `/appointment/booking/services/${categoryId}`;
    };

    // Disabled selectService - now handled in template
    // window.selectService = function(element) {
    //     const serviceId = element.dataset.serviceId;
    //     const serviceType = element.dataset.serviceType;
    //     
    //     // Store service selection in sessionStorage
    //     const serviceData = {
    //         id: serviceId,
    //         type: serviceType
    //     };
    //     
    //     sessionStorage.setItem('selectedService', JSON.stringify(serviceData));
    //     
    //     // Navigate based on service type
    //     if (serviceType === 'package') {
    //         window.location.href = `/appointment/booking/package/${serviceId}`;
    //     } else {
    //         window.location.href = '/appointment/booking/location';
    //     }
    // };

    window.selectLocation = function(locationType) {
        // Store location selection
        sessionStorage.setItem('locationType', locationType);
        
        if (locationType === 'outside') {
            window.location.href = '/appointment/booking/address';
        } else {
            window.location.href = '/appointment/booking/calendar';
        }
    };

    window.selectLocationAndProceed = function(locationType) {
        // Store location selection
        sessionStorage.setItem('locationType', locationType);
        
        // Verify current sessionStorage state
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        
        if (!selectedService.id) {
            alert('Please select a service first.');
            window.location.href = '/appointment/booking/categories';
            return;
        }
        
        if (locationType === 'outside') {
            window.location.href = '/appointment/booking/address';
        } else {
            window.location.href = '/appointment/booking/calendar';
        }
    };

    window.setAddress = function() {
        const addressInput = document.getElementById('customer_address');
        if (addressInput && addressInput.value.trim()) {
            sessionStorage.setItem('serviceAddress', addressInput.value.trim());
            window.location.href = '/appointment/booking/calendar';
        } else {
            alert('Please enter your address for outside service.');
        }
    };

    window.goBackToLocation = function() {
        window.location.href = '/appointment/booking/location';
    };

    window.proceedToCheckout = function() {
        window.location.href = '/book-appointment/preview-invoice';
    };

    window.clearCart = function() {
        if (confirm('Are you sure you want to remove all items from your cart?')) {
            // Call API to clear cart
            fetch('/book-appointment/api/cart/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            }).then(response => response.json())
            .then(data => {
                if (data.result && data.result.success) {
                    location.reload();
                }
            }).catch(error => {
                console.error('Error clearing cart:', error);
            });
        }
    };

    window.removeCartItem = function(itemId) {
        // Call API to remove item
        fetch('/book-appointment/api/cart/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                cart_key: itemId
            })
        }).then(response => response.json())
        .then(data => {
            if (data.result && data.result.success) {
                location.reload();
            }
        }).catch(error => {
            console.error('Error removing cart item:', error);
        });
    };

    // Manual calendar initialization function for testing
    window.forceInitializeCalendar = function() {
        window.calendarInitialized = false; // Reset flag
        initializeCalendar();
    };
    
    // Test function to verify JS is loaded
    window.testBookingJS = function() {
        return 'Booking JS is loaded and working!';
    };

    // Calendar functionality
    window.initializeCalendar = function() {
        // Mark as initialized to prevent double initialization
        if (window.calendarInitialized) {
            return;
        }
        window.calendarInitialized = true;
        
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        const locationType = sessionStorage.getItem('locationType') || 'inside';
        const serviceAddress = sessionStorage.getItem('serviceAddress') || '';
        
        if (!selectedService.id) {
            showCalendarError('Please select a service first.');
            return;
        }

        // Load employees for the calendar
        loadEmployeesForCalendar(selectedService.id, locationType, serviceAddress);
    };

    function loadEmployeesForCalendar(serviceId, locationType, serviceAddress) {
        // Get service plans with departments, employees, slots, and pricing
        const requestUrl = '/book-appointment/api/service-plans';
        const requestData = {
            service_id: parseInt(serviceId)
        };
        
        // Get service plans data
        fetch(requestUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: requestData,
                id: Date.now()
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.result && Object.keys(data.result).length > 0) {
                const plans = data.result;
                // Process employees from plans
                const allEmployees = {};
                
                Object.entries(plans).forEach(([planId, plan]) => {
                    // Add employees from this plan
                    Object.entries(plan.employees || {}).forEach(([empId, empData]) => {
                        const uniqueEmpId = `${planId}_${empId}`;
                        allEmployees[uniqueEmpId] = {
                            ...empData,
                            plan_id: planId,
                            original_id: empId
                        };
                    });
                });
                
                if (Object.keys(allEmployees).length === 0) {
                    showCalendarError('No employees available for this service.');
                    return;
                }
                
                renderCalendar(allEmployees, serviceId, locationType);
            } else {
                showCalendarError('No service plans found.');
            }
        })
        .catch(error => {
            console.error('Error loading employees:', error);
            showCalendarError('Error loading employees.');
        });
    }

    function renderCalendar(employees, serviceId, locationType) {
        const calHead = document.getElementById('calHead');
        const calBody = document.getElementById('calBody');
        
        if (!calHead || !calBody) {
            showCalendarError('Calendar elements not found.');
            return;
        }
        
        // Create header
        let headerHtml = '<div class="time-header">Time</div>';
        Object.entries(employees).forEach(([empId, empData]) => {
            headerHtml += `<div class="employee-header" data-employee-id="${empId}">${empData.name || 'Employee'}</div>`;
        });
        calHead.innerHTML = headerHtml;
        
        // Create body
        let bodyHtml = '';
        
        // Create time slots for all 24 hours
        for (let hour = 0; hour < 24; hour++) {
            bodyHtml += `<div class="time-cell">${hour.toString().padStart(2, '0')}:00</div>`;
            
            Object.entries(employees).forEach(([empId, empData]) => {
                bodyHtml += `<div class="employee-column" data-employee-id="${empId}"></div>`;
            });
        }
        
        calBody.innerHTML = bodyHtml;
        
        // Load slots for each employee
        loadSlotsForEmployees(employees, serviceId, locationType);
    }

    function loadSlotsForEmployees(employees, serviceId, locationType) {
        Object.entries(employees).forEach(([empId, empData]) => {
            const date = new Date().toISOString().split('T')[0]; // Today's date
            
            // Make API call to get slots
            const requestUrl = '/book-appointment/api/slots';
            const requestData = {
                service_id: parseInt(serviceId),
                employee_id: parseInt(empData.original_id),
                date: date,
                appointment_type: locationType,
                branch_id: empData.branch_id || 1
            };
            
            fetch(requestUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: requestData,
                    id: Date.now()
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.result) {
                    renderSlotsForEmployee(empId, data.result);
                } else {
                    renderSlotsForEmployee(empId, []);
                }
            })
            .catch(error => {
                console.error(`Error loading slots for employee ${empId}:`, error);
                renderSlotsForEmployee(empId, []);
            });
        });
    }

    function renderSlotsForEmployee(employeeId, slots) {
        const empCol = document.querySelector(`[data-employee-id="${employeeId}"]`);
        if (!empCol) return;
        
        // Clear existing slots
        empCol.innerHTML = '';
        
        // Convert slots object to array if needed
        let slotsArray = [];
        if (slots && typeof slots === 'object' && !Array.isArray(slots)) {
            // Convert object format {"01:00": {name: "01:00", id: 323, ids: [323, 324]}} to array
            slotsArray = Object.values(slots).map(slot => ({
                time: slot.name,
                id: slot.id,
                ids: slot.ids
            }));
        } else if (Array.isArray(slots)) {
            slotsArray = slots;
        }
        
        // Create time slots for all 24 hours
        for (let hour = 0; hour < 24; hour++) {
            const timeSlot = document.createElement('div');
            timeSlot.className = 'time-slot-cell';
            
            // Find available slots for this hour
            const hourSlots = slotsArray.filter(slot => {
                const slotHour = parseInt(slot.time.split(':')[0]);
                return slotHour === hour;
            });
            
            // Add CSS class based on slot availability
            if (hourSlots.length > 0) {
                timeSlot.classList.add('has-slots');
                
                // Add available slot buttons for this time period
                hourSlots.forEach((slot, index) => {
                    const slotButton = document.createElement('button');
                    slotButton.className = 'slot-btn available';
                    slotButton.textContent = slot.time;
                    slotButton.title = `Book appointment at ${slot.time}`;
                    slotButton.onclick = () => bookSlot(slot.ids || slot.id, employeeId, slot.time);
                    
                    timeSlot.appendChild(slotButton);
                });
            } else {
                timeSlot.classList.add('no-slots');
            }
            
            empCol.appendChild(timeSlot);
        }
    }

    window.bookSlot = function(slotId, employeeId, time) {
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        const locationType = sessionStorage.getItem('locationType') || 'inside';
        const serviceAddress = sessionStorage.getItem('serviceAddress') || '';
        
        if (!selectedService.id) {
            alert('No service selected. Please go back and select a service.');
            return;
        }
        
        // Build booking data
        const slotIds = Array.isArray(slotId) ? slotId : [slotId];
        const selectedDate = window.selectedDate || new Date().toISOString().split('T')[0];
        const bookingData = {
            service_id: parseInt(selectedService.id),
            employee_id: parseInt(employeeId.toString().split('_').pop()),
            slot_ids: slotIds,
            date: selectedDate,
            appointment_type: locationType,
            customer_address: serviceAddress,
            branch_id: 1
        };
        
        // Add to cart via API
        fetch('/book-appointment/api/cart/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    service_data: bookingData
                },
                id: Date.now()
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.result && data.result.success) {
                // Create custom dialog for better user experience
                showAppointmentBookedDialog(time, selectedService.name);
            } else {
                alert('Failed to book appointment. Please try again.');
            }
        })
        .catch(error => {
            console.error('Booking error:', error);
            alert('Error booking appointment. Please try again.');
        });
    };

    function showCalendarError(message) {
        const calBody = document.getElementById('calBody');
        if (calBody) {
            calBody.innerHTML = `<div class="error-message">${message}</div>`;
        }
    }

    // Custom dialog for appointment booking success
    function showAppointmentBookedDialog(time, serviceName) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;

        // Create modal content
        const modal = document.createElement('div');
        modal.style.cssText = `
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            text-align: center;
            max-width: 400px;
            width: 90%;
        `;

        modal.innerHTML = `
            <h3 style="color: #c16d4b; margin-bottom: 20px;">🎉 Appointment Booked!</h3>
            <p style="color: #666; margin-bottom: 10px;">
                Service: <strong>${serviceName || 'Selected Service'}</strong><br>
                Time: <strong>${time}</strong>
            </p>
            <p style="color: #666; margin-bottom: 30px;">What would you like to do next?</p>
            <div style="display: flex; gap: 15px; justify-content: center;">
                <button id="addAnother" style="
                    background: #f4e5a1;
                    color: #333;
                    border: 2px solid #c16d4b;
                    padding: 12px 20px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.3s ease;
                ">Add Another Appointment</button>
                <button id="proceedPayment" style="
                    background: #c16d4b;
                    color: white;
                    border: 2px solid #c16d4b;
                    padding: 12px 20px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: all 0.3s ease;
                ">Proceed to Payment</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Add event listeners
        document.getElementById('addAnother').onclick = function() {
            document.body.removeChild(overlay);
            window.location.href = '/appointment/booking/categories';
        };

        document.getElementById('proceedPayment').onclick = function() {
            document.body.removeChild(overlay);
            window.location.href = '/book-appointment/preview-invoice';
        };

        // Close on overlay click
        overlay.onclick = function(e) {
            if (e.target === overlay) {
                document.getElementById('addAnother').click();
            }
        };
    }

    // Initialize calendar if on calendar page
    document.addEventListener('DOMContentLoaded', function() {
        if (window.location.pathname.includes('/appointment/booking/calendar')) {
            setTimeout(() => {
                initializeCalendar();
            }, 100);
        }
    });

})();