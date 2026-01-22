// Website booking system for appointments

// Define currency functions immediately - before any other code
window.getSafeCurrency = window.getSafeCurrency || function(serviceId) { 
    return window.COMPANY_CURRENCY || '$'; 
};
window.getServiceCurrency = window.getServiceCurrency || function(serviceId) { 
    return window.COMPANY_CURRENCY || '$'; 
};

(function () {
    'use strict';
    
    // Set default currency if not defined
    if (typeof window.COMPANY_CURRENCY === 'undefined') {
        window.COMPANY_CURRENCY = '$'; // Default fallback
    }
    
    // Set default service currencies if not defined
    if (typeof window.SERVICE_CURRENCIES === 'undefined') {
        window.SERVICE_CURRENCIES = {};
    }
    
    // Function to get currency for a specific service
    if (typeof window.getServiceCurrency === 'undefined') {
        window.getServiceCurrency = function(serviceId) {
            try {
                if (typeof window.SERVICE_CURRENCIES !== 'undefined' && window.SERVICE_CURRENCIES[serviceId]) {
                    return window.SERVICE_CURRENCIES[serviceId];
                }
                return window.COMPANY_CURRENCY || '$';
            } catch (e) {
                console.warn('Error in getServiceCurrency fallback:', e);
                return '$';
            }
        };
    }
    
    // Define a safe currency getter function
    window.getSafeCurrency = function(serviceId) {
        if (typeof window.getServiceCurrency === 'function') {
            return window.getServiceCurrency(serviceId);
        }
        // Ultimate fallback
        return '$';
    };

    // Global functions for template onclick handlers
    window.selectCategory = function(element) {
        const categoryId = element.dataset.categoryId;
        
        // Store category selection in sessionStorage for back navigation
        sessionStorage.setItem('selectedCategory', categoryId);
        
        // Navigate to services page
        window.location.href = `/appointment/booking/services/${categoryId}`;
    };

    window.selectService = function(element) {
        const serviceId = element.dataset.serviceId;
        const serviceType = element.dataset.serviceType;
        
        // Store service selection in sessionStorage
        const serviceData = {
        };
        
        sessionStorage.setItem('selectedService', JSON.stringify(serviceData));
        
        // Verify storage
        const stored = sessionStorage.getItem('selectedService');
        
        // Navigate based on service type
        if (serviceType === 'package') {
            window.location.href = '/appointment/booking/package';
        } else {
            window.location.href = '/appointment/booking/location';
        }
    };

    window.selectLocationAndProceed = function(locationType) {
        
        // Store location selection
        sessionStorage.setItem('locationType', locationType);
        
        // Verify current sessionStorage state
        
        if (locationType === 'outside') {
            window.location.href = '/appointment/booking/address';
        } else {
            window.location.href = '/appointment/booking/calendar';
        }
    };

    window.proceedToBooking = function() {
        const locationType = document.querySelector('input[name="location_type"]:checked')?.value;
        
        if (locationType === 'outside') {
            window.location.href = '/appointment/booking/address';
        } else {
            window.location.href = '/appointment/booking/calendar';
        }
    };

    window.proceedWithAddress = function() {
        const addressInput = document.getElementById('serviceAddress');
        if (addressInput && addressInput.value.trim()) {
            // Store address in sessionStorage
            sessionStorage.setItem('serviceAddress', addressInput.value.trim());
            window.location.href = '/appointment/booking/calendar';
        } else {
            alert('Please enter your address');
        }
    };

    window.goBackToServices = function() {
        
        const currentUrl = window.location.pathname;
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        const selectedCategory = sessionStorage.getItem('selectedCategory');
        
        // Store category ID when we select a service
        if (currentUrl.includes('/appointment/booking/calendar')) {
            window.location.href = '/appointment/booking/location';
        } else if (currentUrl.includes('/appointment/booking/location') || currentUrl.includes('/appointment/booking/address')) {
            
            // Try to get category ID from referrer or sessionStorage
            if (selectedCategory) {
                window.location.href = `/appointment/booking/services/${selectedCategory}`;
            } else {
                // Try to extract from referrer or current URL context
                const pathParts = window.location.pathname.split('/');
                
                // Look for category in referrer
                if (document.referrer) {
                    const referrerUrl = new URL(document.referrer);
                    const referrerParts = referrerUrl.pathname.split('/');
                    const categoryIndex = referrerParts.indexOf('services');
                    if (categoryIndex !== -1 && referrerParts[categoryIndex + 1]) {
                        const categoryId = referrerParts[categoryIndex + 1];
                        window.location.href = `/appointment/booking/services/${categoryId}`;
                        return;
                    }
                }
                
                // Fallback to main booking page
                window.location.href = '/appointment/booking';
            }
        } else {
            window.history.back();
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
            }).then(response => response.json())
            .then(data => {
                if (data.result && data.result.success) {
                    location.reload();
                }
            }).catch(error => {
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
        });
    };

    // Debug log to confirm script is loaded
    
    // Manual calendar initialization function for testing
    window.forceInitializeCalendar = function() {
        window.calendarInitialized = false; // Reset flag
        initializeCalendar();
    };
    
    // Test function to verify JS is loaded
    window.testBookingJS = function() {
        return 'Booking JS is loaded and working!';
    };
    
    // Test service plans API
    window.testServicePlansAPI = function(serviceId = 9) {
        
        fetch('/book-appointment/api/service-plans', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
                jsonrpc: '2.0',
                method: 'call',
                params: { service_id: parseInt(serviceId) },
            })
        })
        .then(r => {
            return r.json();
        })
        .then(data => {
            
            if (!data.result || Object.keys(data.result).length === 0) {
                testFallbackAPIs();
            } else {
            }
        })
    };
    
    function testFallbackAPIs() {
        fetch('/book-appointment/api/branches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(data => {
            
            if (data.result && Object.keys(data.result).length > 0) {
                const firstBranchId = Object.keys(data.result)[0];
                
                return fetch('/book-appointment/api/employees', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                });
            }
        })
        .then(r => r ? r.json() : null)
        .then(data => {
        })
    }

    // Manual API test function
    window.testEmployeeAPI = function() {
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        if (!selectedService.id) {
            return;
        }
        
        
        // Test branches API
        fetch('/book-appointment/api/branches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(data => {
            
            // Test employees API with first branch
            if (data.result && Object.keys(data.result).length > 0) {
                const firstBranchId = Object.keys(data.result)[0];
                
                return fetch('/book-appointment/api/employees', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    })
                });
            }
        })
        .then(r => r ? r.json() : null)
        .then(data => {
        })
    };
    
    // Comprehensive employee debugging function
    window.debugEmployees = function() {
        
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        
        // Test 1: Get all branches (no service filter)
        fetch('/book-appointment/api/branches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(r => r.json())
        .then(data => {
            
            if (data.result && Object.keys(data.result).length > 0) {
                // Test 2: Get employees for each branch (no service filter)
                const promises = Object.entries(data.result).map(([branchId, branchName]) => {
                    return fetch('/book-appointment/api/employees', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                    })
                    .then(r => r.json())
                    .then(empData => {
                        return { branchId, branchName, employees: empData };
                    });
                });
                
                return Promise.all(promises);
            }
        })
        .then(results => {
            if (results) {
                
                // Test 3: Try with service + branch combinations
                if (selectedService.id) {
                    results.forEach(({branchId, branchName}) => {
                        fetch('/book-appointment/api/employees', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            })
                        })
                        .then(r => r.json())
                        .then(data => {
                        });
                    });
                }
            }
        })
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
        
        
        // Check if calendar elements exist
        const calHead = document.getElementById('calHead');
        const calBody = document.getElementById('calBody');
        const dateNav = document.getElementById('dateNavigation');
        
        if (!selectedService.id) {
            showCalendarError('Please select a service first.');
            return;
        }
        
        // Show loading state
        showCalendarLoading();
        
        // Load employees for the selected service
        loadEmployeesForCalendar(selectedService.id, locationType, serviceAddress);
    };

    function showCalendarLoading() {
        const calBody = document.getElementById('calBody');
        if (calBody) {
            calBody.innerHTML = '<div class="loading-message">Loading available appointments...</div>';
        }
    }

    function showCalendarError(message) {
        const calBody = document.getElementById('calBody');
        if (calBody) {
            calBody.innerHTML = `<div class="error-message">${message}</div>`;
        }
    }

    function loadEmployeesForCalendar(serviceId, locationType, serviceAddress) {
        
        // Validate service ID
        if (!serviceId || isNaN(parseInt(serviceId))) {
            serviceId = 8; // Temporary fix for testing
        }
        
        // Get service plans with departments, employees, slots, and pricing
        const requestUrl = '/book-appointment/api/service-plans';
        const requestData = {
        };
        
        // Get service plans data
        fetch(requestUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
                jsonrpc: '2.0',
                method: 'call',
            })
        })
        .then(response => {
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return response.json();
        })
        .then(plansData => {
            
            if (!plansData.result || Object.keys(plansData.result).length === 0) {
                return loadEmployeesForCalendarFallback(serviceId, locationType, serviceAddress);
            }
            
            // Process service plans
            const plans = plansData.result;
            
            // Combine all employees from all plans
            const allEmployees = {};
            const planInfo = {};
            
            Object.entries(plans).forEach(([planId, plan]) => {
                
                // Store plan info for pricing and slots
                planInfo[planId] = {
                    id: plan.id,
                    branch_name: plan.branch_name,
                    department_id: plan.department_id,
                    department_name: plan.department_name,
                    slots_inside: plan.slots_inside,
                    slots_outside: plan.slots_outside,
                    price_inside: plan.price_inside,
                    price_outside: plan.price_outside,
                    duration: plan.duration,
                    employees: plan.employees
                };
                
                // Add employees from this plan
                Object.entries(plan.employees || {}).forEach(([empId, empData]) => {
                    const uniqueEmpId = `${planId}_${empId}`;
                    allEmployees[uniqueEmpId] = {
                        ...empData,
                        plan_id: planId,
                        price_inside: plan.price_inside,
                        price_outside: plan.price_outside,
                        department_id: plan.department_id
                    };
                });
            });
            
            if (Object.keys(allEmployees).length === 0) {
                showCalendarError('No employees available for this service. Please contact support.');
                return;
            }
            
            // Store plan info globally for slot loading
            window.servicePlans = planInfo;
            // Also store by service ID for easy access
            window.servicePlansByService = {};
            window.servicePlansByService[serviceId] = planInfo;
            
            // Debug: Log the loaded plan data
            console.log('📊 Loaded service plans for service', serviceId, ':', planInfo);
            console.log('📊 Plan data structure:', Object.keys(planInfo).map(planId => ({
                planId,
                price_inside: planInfo[planId].price_inside,
                price_outside: planInfo[planId].price_outside,
                department: planInfo[planId].department_name
            })));
            
            // Create date selector
            createDateSelector(locationType);
            
            // Render calendar with all employees
            renderCalendar(allEmployees, serviceId, locationType);
        })
        .catch(error => {
            showCalendarError('Unable to load available appointments. Please check your connection and try again.');
        });
    }
    
    function loadEmployeesForCalendarFallback(serviceId, locationType, serviceAddress) {
        
        // Use the old branch + employee method as fallback
        fetch('/book-appointment/api/branches', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
                jsonrpc: '2.0',
                method: 'call',
                params: {
                },
            })
        })
        .then(response => response.json())
        .then(branchesData => {
            
            if (!branchesData.result || Object.keys(branchesData.result).length === 0) {
                return loadAllDepartmentEmployees(serviceId, locationType);
            }
            
            const branches = branchesData.result;
            
            // Load employees for all branches
            return loadEmployeesForAllBranchesFallback(serviceId, branches, locationType);
        })
        .catch(error => {
            showCalendarError('Unable to load appointments. Please try again.');
        });
    }
    
    async function loadAllDepartmentEmployees(serviceId, locationType) {
        
        try {
            // Get all departments
            const departmentsData = await fetch('/book-appointment/api/branches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {}, // No service filter - get all departments
                })
            });
            
            const departments = await departmentsData.json();
            
            if (departments.result && Object.keys(departments.result).length > 0) {
                const allEmployees = {};
                
                // Load employees for each department
                for (const [deptId, deptName] of Object.entries(departments.result)) {
                    try {
                        const empData = await fetch('/book-appointment/api/employees', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                                jsonrpc: '2.0',
                                method: 'call',
                                params: { branch_id: parseInt(deptId) },
                            })
                        });
                        
                        const empResult = await empData.json();
                        
                        if (empResult.result && Object.keys(empResult.result).length > 0) {
                            Object.entries(empResult.result).forEach(([empId, empInfo]) => {
                                const uniqueId = `${deptId}_${empId}`;
                                allEmployees[uniqueId] = {
                                    ...empInfo,
                                    price_inside: 50, // Default prices
                                    price_outside: 60,
                                    duration: 60
                                };
                            });
                        }
                    } catch (error) {
                    }
                }
                
                
                if (Object.keys(allEmployees).length > 0) {
                    // Create date selector
                    createDateSelector(locationType);
                    
                    // Render calendar
                    renderCalendar(allEmployees, serviceId, locationType);
                } else {
                    showCalendarError('No employees available. Please contact support.');
                }
            }
        } catch (error) {
            showCalendarError('Unable to load appointments. Please try again.');
        }
    }
    
    async function loadEmployeesForAllBranchesFallback(serviceId, branches, locationType) {
        
        const allEmployees = {};
        
        for (const [branchId, branchName] of Object.entries(branches)) {
            try {
                const empData = await fetch('/book-appointment/api/employees', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                        jsonrpc: '2.0',
                        method: 'call',
                        params: { branch_id: parseInt(branchId) },
                    })
                });
                
                const empResult = await empData.json();
                
                if (empResult.result && Object.keys(empResult.result).length > 0) {
                    Object.entries(empResult.result).forEach(([empId, empInfo]) => {
                        const uniqueId = `${branchId}_${empId}`;
                        allEmployees[uniqueId] = {
                            ...empInfo,
                            price_inside: 50, // Default prices
                            price_outside: 60,
                            duration: 60
                        };
                    });
                }
            } catch (error) {
            }
        }
        
        
        if (Object.keys(allEmployees).length > 0) {
            // Create date selector
            createDateSelector(locationType);
            
            // Render calendar
            renderCalendar(allEmployees, serviceId, locationType);
        } else {
            showCalendarError('No employees available for this service. Please contact support.');
        }
    }
    
    function createDateSelector(locationType) {
        
        const dateNav = document.getElementById('dateNavigation');
        if (!dateNav) return;
        
        const today = new Date();
        const dates = [];
        
        // Generate next 8 days
        for (let i = 0; i < 8; i++) {
            const date = new Date(today);
            date.setDate(today.getDate() + i);
            dates.push({
            });
        }
        
        let dateHtml = '<div class="date-selector-container">';
        dateHtml += '<h3 class="date-selector-title">Select Date</h3>';
        dateHtml += '<div class="date-nav-buttons">';
        
        dates.forEach((dateInfo, index) => {
            dateHtml += `
                <button class="date-nav-btn ${dateInfo.isToday ? 'active' : ''}" 
                        data-date="${dateInfo.dateStr}" 
                        onclick="selectDate('${dateInfo.dateStr}', ${index === 0})">
                    <div class="nav-day">${dateInfo.dayName}</div>
                    <div class="nav-number">${dateInfo.dayNum}</div>
                    <div class="nav-month">${dateInfo.monthName}</div>
                </button>
            `;
        });
        
        dateHtml += '</div></div>';
        dateNav.innerHTML = dateHtml;
        
        // Store current selected date
        window.selectedDate = dates[0].dateStr;
    }
    
    window.selectDate = function(dateStr, isToday = false) {
        
        // Update active button
        document.querySelectorAll('.date-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-date="${dateStr}"]`).classList.add('active');
        
        // Store selected date
        window.selectedDate = dateStr;
        
        // Reload slots for the new date
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        const locationType = sessionStorage.getItem('locationType') || 'inside';
        
        if (selectedService.id && window.currentEmployees) {
            loadSlotsForDate(dateStr, selectedService.id, window.currentEmployees, locationType);
        }
    };
    
    async function loadEmployeesForAllBranches(serviceId, branches, locationType) {
        
        const allEmployees = {};
        
        // Load employees for each branch
        for (const [branchId, branchName] of Object.entries(branches)) {
            
            try {
                const employeesData = await fetch('/book-appointment/api/employees', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    })
                });
                
                if (!employeesData.ok) {
                    continue;
                }
                
                const employeesResult = await employeesData.json();
                
                if (employeesResult.result && Object.keys(employeesResult.result).length > 0) {
                    // Add employees with branch prefix to avoid ID conflicts
                    Object.entries(employeesResult.result).forEach(([empId, empData]) => {
                        const uniqueEmpId = `${branchId}_${empId}`;
                        allEmployees[uniqueEmpId] = {
                            ...empData,
                        };
                    });
                } else {
                    
                    // FALLBACK: Try getting employees for this branch without service filter
                    
                    try {
                        const fallbackData = await fetch('/book-appointment/api/employees', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                                // No service_id - just get all employees for this branch
                            })
                        });
                        
                        if (fallbackData.ok) {
                            const fallbackResult = await fallbackData.json();
                            
                            if (fallbackResult.result && Object.keys(fallbackResult.result).length > 0) {
                                
                                // Add these employees (without service filter)
                                Object.entries(fallbackResult.result).forEach(([empId, empData]) => {
                                    const uniqueEmpId = `${branchId}_${empId}`;
                                    allEmployees[uniqueEmpId] = {
                                        ...empData,
                                    };
                                });
                            } else {
                            }
                        }
                    } catch (fallbackError) {
                    }
                }
            } catch (error) {
            }
        }
        
        
        if (Object.keys(allEmployees).length === 0) {
            showCalendarError('No employees available for this service. Please try a different service or contact support.');
            return;
        }
        
        // Render calendar with all employees
        renderCalendar(allEmployees, serviceId, locationType);
    }
    
    async function loadEmployeesWithoutBranches(serviceId, locationType) {
        
        try {
            // Try calling employees API with just service_id (branch_id might be optional)
            const employeesData = await fetch('/book-appointment/api/employees', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        // No branch_id - let the API handle it
                    },
                })
            });
            
            
            if (!employeesData.ok) {
                throw new Error(`HTTP ${employeesData.status}: ${employeesData.statusText}`);
            }
            
            const employeesResult = await employeesData.json();
            
            if (employeesResult.result && Object.keys(employeesResult.result).length > 0) {
                renderCalendar(employeesResult.result, serviceId, locationType);
            } else {
                await debugAllEmployees();
                showCalendarError('No employees available for this service. Please try a different service or contact support.');
            }
        } catch (error) {
            showCalendarError('Unable to load available appointments. Please check your connection and try again.');
        }
    }
    
    async function debugAllEmployees() {
        
        try {
            // Try to get employees without any restrictions to see what's available
            const debugData = await fetch('/book-appointment/api/employees', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {},
                })
            });
            
            if (debugData.ok) {
                const debugResult = await debugData.json();
            }
        } catch (error) {
        }
    }

    function renderCalendar(employees, serviceId, locationType) {
        
        const calHead = document.getElementById('calHead');
        const calBody = document.getElementById('calBody');
        
        });
        
        if (!calHead || !calBody) {
            return;
        }
        
        // Create header with improved employee display
        // Store employees globally for date changes
        window.currentEmployees = employees;
        
        // Build header HTML with proper time column
        let headerHtml = '<div class="cell">⏰ TIME</div>';
        
        Object.entries(employees).forEach(([empId, empData]) => {
            let empName, branchName, price, duration;
            
            if (typeof empData === 'object') {
                empName = empData.name || empData;
                branchName = empData.branch_name || 'Main Branch';
                
                // Get price based on location type
                const locationType = sessionStorage.getItem('locationType') || 'inside';
                price = locationType === 'inside' ? (empData.price_inside || 0.0) : (empData.price_outside || 0.0);
                duration = empData.duration || 60;
            } else {
                empName = empData || 'Employee';
                branchName = 'Main Branch';
                price = 0.0;
                duration = 60;
            }
            
            headerHtml += `<div class="cell emp-header">
                <div class="emp-avatar">${empName.charAt(0).toUpperCase()}</div>
                <div class="emp-info">
                    <div class="emp-name">${empName}</div>
                    <div class="emp-branch">${branchName}</div>
                    <div class="emp-price">${window.getSafeCurrency(window.selectedServiceId || null)}${price.toFixed(2)}</div>
                    <div class="emp-duration">${duration} min</div>
                </div>
            </div>`;
        });
        
        calHead.innerHTML = headerHtml;
        
        // Set CSS grid columns with proper count
        const empCount = Object.keys(employees).length;
        console.log(`Setting grid for ${empCount} employees`);
        
        // Update CSS custom property for grid columns
        calHead.style.setProperty('--cols', empCount);
        calBody.style.setProperty('--cols', empCount);
        calHead.style.gridTemplateColumns = `100px repeat(${empCount}, 1fr)`;
        calBody.style.gridTemplateColumns = `100px repeat(${empCount}, 1fr)`;
        
        // Create time column for business hours (8 AM to 6 PM) with 30-minute intervals
        let timeColumnHtml = '';
        for (let hour = 8; hour <= 18; hour++) {
            for (let minutes = 0; minutes < 60; minutes += 30) {
                const displayHour = hour === 0 ? 12 : (hour > 12 ? hour - 12 : hour);
                const ampm = hour >= 12 ? 'PM' : 'AM';
                const minuteStr = minutes === 0 ? '00' : minutes.toString();
                timeColumnHtml += `<div class="time-slot">${displayHour}:${minuteStr} ${ampm}</div>`;
            }
        }
        
        // Create complete calendar body structure
        let bodyHtml = `<div class="time-col">${timeColumnHtml}</div>`;
        
        // Create employee columns with proper structure
        Object.entries(employees).forEach(([empId, empData]) => {
            const empName = (typeof empData === 'object' ? empData.name : empData) || 'Employee';
            console.log(`Creating column for employee ${empId}: ${empName}`);
            bodyHtml += `<div class="emp-col" data-employee-id="${empId}">
                <!-- Slots will be populated here -->
            </div>`;
        });
        
        calBody.innerHTML = bodyHtml;
        
        console.log('✅ Calendar structure created:', {
            employees: Object.keys(employees).length,
            timeSlots: (18 - 8 + 1),
            bodyHtml: bodyHtml.length
        });
        
        // Load slots for selected date (default to today)
        const selectedDate = window.selectedDate || new Date().toISOString().split('T')[0];
        loadSlotsForDate(selectedDate, serviceId, employees, locationType);
    }

    function loadSlotsForCalendar(serviceId, employees, locationType) {
        // Load slots for next 7 days
        const dates = [];
        const today = new Date();
        for (let i = 0; i < 7; i++) {
            const date = new Date(today);
            date.setDate(today.getDate() + i);
            dates.push(date.toISOString().split('T')[0]);
        }
        
        // Create date navigation
        createDateNavigation(dates, serviceId, employees, locationType);
        
        // Load slots for first date by default
        if (dates.length > 0) {
            loadSlotsForDate(dates[0], serviceId, employees, locationType);
        }
    }

    function createDateNavigation(dates, serviceId, employees, locationType) {
        const navContainer = document.getElementById('dateNavigation');
        if (!navContainer) return;
        
        let navHtml = '<div class="date-nav-buttons">';
        dates.forEach((date, index) => {
            const dateObj = new Date(date);
            const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
            const dayNum = dateObj.getDate();
            const monthName = dateObj.toLocaleDateString('en-US', { month: 'short' });
            
            navHtml += `
                <button class="date-nav-btn ${index === 0 ? 'active' : ''}" 
                        data-date="${date}" 
                        onclick="selectCalendarDate('${date}', ${serviceId}, '${locationType}')">
                    <div class="nav-day">${dayName}</div>
                    <div class="nav-number">${dayNum}</div>
                    <div class="nav-month">${monthName}</div>
                </button>
            `;
        });
        navHtml += '</div>';
        
        navContainer.innerHTML = navHtml;
    }

    window.selectCalendarDate = function(date, serviceId, locationType) {
        // Update active button
        document.querySelectorAll('.date-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-date="${date}"]`).classList.add('active');
        
        // Load employees again to get fresh data
        const employees = {}; // Get from current state or re-fetch
        const empCols = document.querySelectorAll('.emp-col');
        empCols.forEach(col => {
            const empId = col.dataset.employeeId;
            employees[empId] = empId; // Simple mapping
        });
        
        // Load slots for selected date
        loadSlotsForDate(date, serviceId, employees, locationType);
    };

    function loadSlotsForDate(date, serviceId, employees, locationType) {
        
        Object.entries(employees).forEach(([empId, empData]) => {
            
            // Extract original employee ID and plan information
            let originalEmpId = empId;
            let planId = null;
            let slotsAvailable = null;
            
            if (typeof empData === 'object' && empData.original_id) {
                originalEmpId = empData.original_id;
                planId = empData.plan_id;
                
                // Get available slots from plan based on location type
                if (window.servicePlans && window.servicePlans[planId]) {
                    const plan = window.servicePlans[planId];
                    slotsAvailable = locationType === 'inside' ? plan.slots_inside : plan.slots_outside;
                }
            }
            
            
            // For now, generate sample slots based on plan configuration
            // TODO: Replace with actual API call to get real slot availability
            const sampleSlots = generateSampleSlots(date, slotsAvailable, empData.duration || 60);
            
            // Render the sample slots immediately
            renderSlotsForEmployee(empId, sampleSlots);
            
            // You can still make the API call for real data if needed
            const requestUrl = '/book-appointment/api/slots';
            const requestData = {
            };
            
            });
            
            fetch(requestUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                    jsonrpc: '2.0',
                    method: 'call',
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
                    // Still render empty column
                    renderSlotsForEmployee(empId, []);
                }
            })
            .catch(error => {
                // Render empty column on error
                renderSlotsForEmployee(empId, []);
            });
        });
    }
    
    function generateSampleSlots(date, totalSlots, duration) {
        
        if (!totalSlots || totalSlots <= 0) return [];
        
        const slots = [];
        const startHour = 0; // 12 AM (midnight)
        const endHour = 24; // 12 AM next day
        const slotDuration = duration || 60; // Default 60 minutes
        const slotsPerHour = Math.floor(60 / slotDuration);
        
        let slotId = 1;
        
        for (let hour = startHour; hour < endHour && slots.length < totalSlots; hour++) {
            for (let slot = 0; slot < slotsPerHour && slots.length < totalSlots; slot++) {
                const minutes = slot * slotDuration;
                const timeStr = `${hour.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                
                slots.push({
                    id: slotId++,
                    time: timeStr,
                    name: timeStr,
                    ids: [slotId],
                    price: 0.0 // Price will be calculated dynamically based on employee plan
                });
            }
        }
        
        return slots;
    }

    function renderSlotsForEmployee(employeeId, slots) {
        const empCol = document.querySelector(`[data-employee-id="${employeeId}"]`);
        if (!empCol) {
            console.warn(`Employee column not found for ID: ${employeeId}`);
            return;
        }
        
        // Clear existing slots
        empCol.innerHTML = '';
        
        console.log(`Rendering slots for employee ${employeeId}:`, slots);
        
        // Convert slots object to proper format if needed
        let slotsArray = [];
        if (slots && typeof slots === 'object') {
            if (Array.isArray(slots)) {
                slotsArray = slots;
            } else {
                // Convert object format {"08:00": {name: "08:00", id: 323, ids: [323, 324]}} to array
                slotsArray = Object.values(slots);
            }
        }
        
        console.log(`Processed slots array for employee ${employeeId}:`, slotsArray);
        
        // Create time slots for business hours (8 AM to 6 PM) with 30-minute intervals - match header range
        for (let hour = 8; hour <= 18; hour++) {
            for (let minutes = 0; minutes < 60; minutes += 30) {
                const timeSlot = document.createElement('div');
                timeSlot.className = 'time-slot-cell';
                
                const timeKey = `${hour.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                
                // Find available slots for this time
                const hourSlots = slotsArray.filter(slot => {
                    if (!slot.time) return false;
                    const [slotHour, slotMinutes] = slot.time.split(':').map(n => parseInt(n));
                    return slotHour === hour && slotMinutes === minutes;
                });
            
            // Add CSS class based on slot availability
            if (hourSlots.length > 0) {
                timeSlot.classList.add('has-slots');
                
                // Add available slot buttons for this time period
                hourSlots.forEach((slot, index) => {
                    // Calculate dynamic price from employee's plan data
                    let dynamicPrice = 0.0;
                    const locationType = sessionStorage.getItem('locationType') || 'inside';
                    
                    // Get employee data to find their plan
                    const empData = window.currentEmployees && window.currentEmployees[employeeId];
                    if (empData && empData.plan_id && window.servicePlans) {
                        const plan = window.servicePlans[empData.plan_id];
                        if (plan) {
                            dynamicPrice = locationType === 'inside' ? 
                                (plan.price_inside || 0.0) : 
                                (plan.price_outside || 0.0);
                        }
                    }
                    
                    const slotButton = document.createElement('button');
                    slotButton.className = 'slot-btn available';
                    slotButton.textContent = slot.time || slot.name;
                    slotButton.title = `Book appointment at ${slot.time || slot.name} - ${window.getSafeCurrency(window.selectedServiceId || null)}${dynamicPrice.toFixed(2)}`;
                    
                    // Store slot data for booking with dynamic price
                    slotButton.dataset.slotData = JSON.stringify({
                        id: slot.id,
                        ids: slot.ids || [slot.id],
                        time: slot.time || slot.name,
                        price: dynamicPrice,
                        employee_id: employeeId
                    });
                    
                    slotButton.onclick = () => {
                        const slotData = JSON.parse(slotButton.dataset.slotData);
                        selectSlotForBooking(slotData);
                    };
                    
                    timeSlot.appendChild(slotButton);
                });
            } else {
                timeSlot.classList.add('no-slots');
                // Add empty state indicator
                const emptyDiv = document.createElement('div');
                emptyDiv.className = 'empty-slot';
                emptyDiv.textContent = '';
                timeSlot.appendChild(emptyDiv);
            }
            
            empCol.appendChild(timeSlot);
            }
        }
        
        console.log(`✅ Rendered ${slotsArray.length} slots for employee ${employeeId}`);
    }
    
    // Enhanced slot selection function with comprehensive data validation
    function selectSlotForBooking(slotData) {
        console.log('🎯 Selected slot for booking:', slotData);
        
        // Get booking context with fallbacks
        const selectedService = JSON.parse(sessionStorage.getItem('selectedService') || '{}');
        const locationType = sessionStorage.getItem('locationType') || 'inside';
        const serviceAddress = sessionStorage.getItem('serviceAddress') || '';
        const selectedDate = window.selectedDate || new Date().toISOString().split('T')[0];
        const selectedBranch = JSON.parse(sessionStorage.getItem('selectedBranch') || '{}');
        
        console.log('📋 Booking context:', {
            selectedService,
            locationType,
            serviceAddress,
            selectedDate,
            selectedBranch
        });
        
        // Validate essential data
        if (!selectedService.id) {
            showBookingMessage('No service selected. Please go back and select a service.', 'error');
            return;
        }
        
        // Get employee name
        const empId = slotData.employee_id;
        const empData = window.currentEmployees && window.currentEmployees[empId];
        const empName = empData ? (empData.name || empData) : 'Unknown Employee';
        
        // Get service and branch names
        const serviceName = selectedService.name || 'Unknown Service';
        const branchName = selectedBranch.name || 'Main Branch';
        
        let price = null;
        
        // First try to get price from slot data
        if (slotData.price && slotData.price > 0) {
            price = parseFloat(slotData.price);
            console.log('Got price from slot:', price);
        } else {
            // Get price dynamically from service plans - no hardcoded values
            console.log('Getting dynamic price for service:', selectedService?.id, 'employee:', slotData.employee_id, 'location:', locationType);
            
            if (selectedService && selectedBranch && slotData.employee_id) {
                // Use the employee's plan data that was already loaded
                console.log('🔍 Debug pricing - selectedService:', selectedService?.id, 'employee:', slotData.employee_id, 'location:', locationType);
                console.log('🔍 Debug - window.currentEmployees:', window.currentEmployees);
                console.log('🔍 Debug - window.servicePlans:', window.servicePlans);
                
                const empData = window.currentEmployees && window.currentEmployees[slotData.employee_id];
                console.log('🔍 Debug - empData for employee', slotData.employee_id, ':', empData);
                
                if (empData && empData.plan_id && window.servicePlans) {
                    const plan = window.servicePlans[empData.plan_id];
                    console.log('🔍 Debug - plan for plan_id', empData.plan_id, ':', plan);
                    
                    if (plan) {
                        // Get price based on appointment type
                        if (locationType === 'inside') {
                            price = plan.price_inside || 0.0;
                        } else {
                            price = plan.price_outside || 0.0;
                        }
                        console.log('✅ Got price from employee plan:', price, 'for plan:', empData.plan_id, 'location:', locationType);
                    } else {
                        console.log('❌ No plan found for employee plan ID:', empData.plan_id);
                    }
                } else {
                    console.log('❌ No employee data or plan ID found for employee:', slotData.employee_id);
                    console.log('   - empData exists:', !!empData);
                    console.log('   - empData.plan_id:', empData?.plan_id);
                    console.log('   - window.servicePlans exists:', !!window.servicePlans);
                }
                
                // Fallback: if no plan found, price remains 0.0
                if (!price || price <= 0) {
                    price = 0.0;
                    console.log('No matching plan found - price set to 0.0');
                }
            } else {
                console.error('Missing required data for pricing');
                price = 0.0;
            }
        }
        
        // Don't show summary if price is 0
        if (!price || price <= 0) {
            console.error('No valid price found - not showing summary');
            return;
        }
        
        // Show booking summary with enhanced styling
        const summaryDiv = document.getElementById('bookingSummary');
        const slotInfoDiv = document.getElementById('selectedSlotInfo');
        
        if (summaryDiv && slotInfoDiv) {
            slotInfoDiv.innerHTML = `
                <div class="slot-summary" style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #e2e8f0;">
                    <h5 style="font-size: 18px; font-weight: 700; color: #2d3748; margin-bottom: 16px; border-bottom: 2px solid #c16d4b; padding-bottom: 8px;">📅 Booking Details</h5>
                    
                    <div style="display: grid; gap: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">💼 Service:</strong> 
                            <span style="color: #2d3748; font-weight: 600;">${serviceName}</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">👨‍💼 Employee:</strong> 
                            <span style="color: #2d3748; font-weight: 600;">${empName}</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">📅 Date:</strong> 
                            <span style="color: #2d3748; font-weight: 600;">${new Date(selectedDate).toLocaleDateString('en-US', { 
                                weekday: 'long', 
                                year: 'numeric', 
                                month: 'long', 
                                day: 'numeric' 
                            })}</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">🕐 Time:</strong> 
                            <span style="color: #c16d4b; font-weight: 700; font-size: 16px;">${slotData.time}</span>
                        </div>
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">📍 Location:</strong> 
                            <span style="color: #2d3748; font-weight: 600;">${locationType === 'inside' ? '🏢 At Salon' : '🏠 At Your Location'}</span>
                        </div>
                        
                        ${locationType === 'inside' ? `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">🏢 Branch:</strong> 
                            <span style="color: #2d3748; font-weight: 600;">${branchName}</span>
                        </div>
                        ` : ''}
                        
                        ${serviceAddress ? `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;">
                            <strong style="color: #4a5568;">🏠 Address:</strong> 
                            <span style="color: #2d3748; font-weight: 600; text-align: right; max-width: 60%;">${serviceAddress}</span>
                        </div>
                        ` : ''}
                        
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 0; background: linear-gradient(135deg, #c16d4b 0%, #a85a3c 100%); margin: 12px -12px -12px -12px; padding-left: 12px; padding-right: 12px; border-radius: 0 0 12px 12px;">
                            <strong style="color: white; font-size: 16px;">💰 Total Price:</strong> 
                            <span id="summaryPrice" style="color: white; font-weight: 800; font-size: 20px;">${window.getSafeCurrency(window.selectedServiceId || null)}${price.toFixed(2)}</span>
                        </div>
                    </div>
                </div>
            `;
            
            // Store enhanced slot data for booking
            window.selectedSlotData = {
                ...slotData,
                service_id: selectedService.id,
                service_name: serviceName,
                employee_name: empName,
                branch_id: selectedBranch.id || 1,
                branch_name: branchName,
                date: selectedDate,
                appointment_type: locationType,
                customer_address: serviceAddress,
                price: price
            };
            
            console.log('💾 Stored slot data for booking:', window.selectedSlotData);
            
            // Show the booking summary with smooth animation
            summaryDiv.style.display = 'block';
            summaryDiv.style.opacity = '0';
            summaryDiv.style.transform = 'translateY(20px)';
            
            // Animate in
            setTimeout(() => {
                summaryDiv.style.transition = 'all 0.3s ease-out';
                summaryDiv.style.opacity = '1';
                summaryDiv.style.transform = 'translateY(0)';
            }, 10);
            
            // Scroll to booking summary
            setTimeout(() => {
                summaryDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 300);
            
        } else {
            console.warn('⚠️ Booking summary elements not found, using fallback');
            // Fallback: immediate booking
            bookSlot(slotData.ids, slotData.employee_id, slotData.time);
        }
    }
    
    // Helper function to update the summary price display
    function updateSummaryPrice(newPrice) {
        const priceElement = document.getElementById('summaryPrice');
        if (priceElement) {
            priceElement.textContent = `${window.getSafeCurrency(window.selectedServiceId || null)}${newPrice.toFixed(2)}`;
        }
        
        // Update the stored slot data with the new price
        if (window.selectedSlotData) {
            window.selectedSlotData.price = newPrice;
        }
    }
    
    // Enhanced booking confirmation function with better error handling
    window.confirmSlotBooking = function() {
        console.log('🎯 Confirming slot booking...');
        
        if (!window.selectedSlotData) {
            showBookingMessage('No slot selected. Please select a time slot first.', 'error');
            return;
        }
        
        const slotData = window.selectedSlotData;
        console.log('Selected slot data:', slotData);
        
        // Validate required data
        if (!slotData.service_id || !slotData.employee_id || !slotData.ids) {
            showBookingMessage('Invalid booking data. Please select a different slot.', 'error');
            return;
        }
        
        // Show loading state
        const confirmBtn = document.getElementById('confirmBookingBtn');
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Booking...';
        }
        
        // Prepare booking data for the API
        const bookingData = {
            service_id: parseInt(slotData.service_id),
            employee_id: parseInt(slotData.employee_id),
            slot_ids: Array.isArray(slotData.ids) ? slotData.ids : [slotData.ids],
            date: slotData.date,
            appointment_type: slotData.appointment_type || 'inside',
            customer_address: slotData.customer_address || '',
            price: parseFloat(slotData.price) || 0.0,
            branch_id: slotData.branch_id || 1
        };
        
        console.log('📤 Sending booking data:', bookingData);
        
        // Make API call with proper error handling
        fetch('/book-appointment/api/cart/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: {
                    service_data: bookingData
                },
                id: Date.now()
            })
        })
        .then(async response => {
            console.log('📥 Response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('📥 Response data:', data);
            return data;
        })
        .then(data => {
            // Reset button state
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Book This Slot';
            }
            
            if (data.result && data.result.success) {
                console.log('✅ Booking successful!');
                
                // Hide booking summary
                const summaryDiv = document.getElementById('bookingSummary');
                if (summaryDiv) {
                    summaryDiv.style.display = 'none';
                }
                
                // Show success message
                showBookingMessage(`🎉 Appointment booked successfully for ${slotData.time}!`, 'success');
                
                // Clear selected slot data
                window.selectedSlotData = null;
                
                // Refresh calendar to show updated availability
                setTimeout(() => {
                    if (typeof window.initializeCalendar === 'function') {
                        console.log('🔄 Refreshing calendar...');
                        window.initializeCalendar();
                    }
                }, 1500);
                
                // Optionally redirect to cart or next step
                setTimeout(() => {
                    if (confirm('Would you like to view your cart or continue booking?')) {
                        // Could redirect to cart page
                        console.log('User wants to view cart');
                    }
                }, 3000);
                
            } else {
                console.error('❌ Booking failed:', data);
                const errorMsg = data.result?.error || data.error?.data?.message || 'Unable to book slot. Please try again.';
                showBookingMessage(errorMsg, 'error');
                
                // Refresh calendar to show current availability
                if (typeof window.initializeCalendar === 'function') {
                    window.initializeCalendar();
                }
            }
        })
        .catch(error => {
            console.error('💥 Booking error:', error);
            
            // Reset button state
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Book This Slot';
            }
            
            let errorMessage = 'Failed to book appointment. Please try again.';
            
            if (error.message.includes('Network')) {
                errorMessage = 'Network error. Please check your connection and try again.';
            } else if (error.message.includes('404')) {
                errorMessage = 'Booking service not found. Please refresh the page.';
            } else if (error.message.includes('500')) {
                errorMessage = 'Server error. Please try again in a moment.';
            }
            
            showBookingMessage(errorMessage, 'error');
        });
    };
    
    // Enhanced message display function
    function showBookingMessage(message, type = 'info') {
        // Remove any existing messages
        const existingMessages = document.querySelectorAll('.booking-message');
        existingMessages.forEach(msg => msg.remove());
        
        // Create message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `booking-message booking-message-${type}`;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            padding: 16px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-weight: 600;
            font-size: 14px;
            max-width: 400px;
            animation: slideInRight 0.3s ease-out;
        `;
        
        // Set colors based on type
        switch (type) {
            case 'success':
                messageDiv.style.background = '#48bb78';
                messageDiv.style.color = 'white';
                break;
            case 'error':
                messageDiv.style.background = '#f56565';
                messageDiv.style.color = 'white';
                break;
            default:
                messageDiv.style.background = '#4299e1';
                messageDiv.style.color = 'white';
        }
        
        messageDiv.textContent = message;
        
        // Add animation styles
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(messageDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageDiv.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 5000);
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
        const bookingData = {
        };
        
        // Add to cart via API
        fetch('/book-appointment/api/cart/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
                jsonrpc: '2.0',
                method: 'call',
                params: {
                },
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.result && data.result.success) {
                // Create custom dialog for better user experience
                showAppointmentBookedDialog(time, selectedService.name);
            } else {
                alert(data.result?.error || 'Unable to book slot. Please try again.');
                // Refresh calendar to show current availability
                initializeCalendar();
            }
        })
        .catch(error => {
            alert('Error booking slot. Please try again.');
        });
    };

    // Initialize location radio handlers when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        
        // Check if we're on calendar page
        const isCalendarPage = window.location.pathname.includes('/appointment/booking/calendar');
        
        // Initialize calendar if we're on the calendar page
        if (isCalendarPage) {
            });
            
            // Add a small delay to ensure DOM is fully rendered
            setTimeout(() => {
                initializeCalendar();
            }, 100);
        } else {
        }
        
        // Location type change handler
        const locationRadios = document.querySelectorAll('input[name="location_type"]');
        const addressSection = document.getElementById('addressSection');
        
        locationRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (addressSection) {
                    if (this.value === 'outside') {
                        addressSection.style.display = 'block';
                    } else {
                        addressSection.style.display = 'none';
                    }
                }
            });
        });
        
        
        // Fallback: Try to initialize calendar if calendar elements exist
        setTimeout(() => {
            const calHead = document.getElementById('calHead');
            const calBody = document.getElementById('calBody');
            
            
            if (calHead && calBody && !window.calendarInitialized) {
                window.calendarInitialized = true;
                initializeCalendar();
            }
        }, 500);
    });

    // Simple appointment booking manager without complex dependencies
    class SimpleAppointmentBooking {
        constructor() {
            this.state = {
                currentStep: 1,
                serviceDetails: {
                    appointment_type: 'inside',
                    slot_ids: [],
                    customer_address: ''
                },
                categories: [],
                services: [],
                branches: [],
                employees: [],
                dates: [],
                slots: [],
                cart: {},
                cartTotal: 0,
                packageServices: [],
                currentPackageServiceIndex: 0,
                packageServiceDetails: {}
            };

            this.init();
        }

        init() {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.start());
            } else {
                this.start();
            }
        }

        start() {
            if (!document.querySelector('.booking_container')) return;
            
            this.bindEvents();
            this.loadCategories();
            this.loadCart();
        }

        bindEvents() {
            // Category selection
            document.addEventListener('click', (e) => {
                if (e.target.closest('.category_item')) {
                    const categoryId = parseInt(e.target.closest('.category_item').dataset.categoryId);
                    this.selectCategory(categoryId);
                }
            });

            // Service selection
            document.addEventListener('click', (e) => {
                if (e.target.closest('.service_item')) {
                    const serviceId = parseInt(e.target.closest('.service_item').dataset.serviceId);
                    this.selectService(serviceId);
                }
            });

            // Appointment type change
            document.addEventListener('change', (e) => {
                if (e.target.name === 'appointment_type') {
                    this.state.serviceDetails.appointment_type = e.target.value;
                    this.toggleAddressField();
                    if (this.state.selectedService) {
                        this.loadBranches();
                        // For outside appointments, auto-select first branch and load employees
                        if (e.target.value === 'outside') {
                            setTimeout(() => {
                                this.autoSelectBranchForOutside();
                            }, 100);
                        }
                    }
                }
            });

            // Branch selection
            document.addEventListener('change', (e) => {
                if (e.target.id === 'branch_select') {
                    this.state.serviceDetails.branch_id = parseInt(e.target.value) || null;
                    if (this.state.serviceDetails.branch_id) {
                        this.loadEmployees();
                    }
                }
            });

            // Employee selection is now handled by custom dropdown events

            // Date selection
            document.addEventListener('click', (e) => {
                if (e.target.closest('.date_option')) {
                    const date = e.target.closest('.date_option').dataset.date;
                    this.selectDate(date);
                }
            });

            // Slot selection
            document.addEventListener('click', (e) => {
                if (e.target.closest('.slot_option')) {
                    const slotIds = JSON.parse(e.target.closest('.slot_option').dataset.slotIds);
                    this.selectSlot(slotIds);
                }
            });

            // Cart actions
            document.addEventListener('click', (e) => {
                if (e.target.id === 'add_to_cart') {
                    this.addToCart();
                } else if (e.target.id === 'proceed_checkout') {
                    this.proceedToCheckout();
                } else if (e.target.id === 'remove_all_cart') {
                    this.removeAllFromCart();
                } else if (e.target.id === 'back_to_services') {
                    this.backToServices();
                } else if (e.target.id === 'back_to_categories') {
                    this.backToCategories();
                } else if (e.target.closest('.remove_cart_item')) {
                    e.preventDefault();
                    e.stopPropagation();
                    const cartKey = e.target.closest('.remove_cart_item').dataset.cartKey;
                    if (cartKey) {
                        this.removeFromCart(cartKey);
                    }
                }
            });

            // Address field
            document.addEventListener('input', (e) => {
                if (e.target.id === 'customer_address') {
                    this.state.serviceDetails.customer_address = e.target.value;
                }
            });
        }

        // API helper method
        async makeRequest(url, data = {}) {
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                        jsonrpc: '2.0',
                        method: 'call',
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                if (result.error) {
                    throw new Error(result.error.message || 'Server error');
                }
                
                return result.result;
            } catch (error) {
                throw error;
            }
        }

        async loadCategories() {
            try {
                const categories = await this.makeRequest('/book-appointment/api/categories');
                this.state.categories = categories || [];
                this.renderCategories();
            } catch (error) {
            }
        }

        renderCategories() {
            const container = document.getElementById('category_slider');
            if (!container) return;

            const html = this.state.categories.map(category => `
                <div class="category_item" data-category-id="${category.id}">
                    <div class="category_image">
                        ${category.image ? `<img src="${category.image}" alt="${category.name}"/>` : '<div class="category_placeholder"></div>'}
                    </div>
                    <h4 class="category_name">${category.name}</h4>
                </div>
            `).join('');

            container.innerHTML = html;
        }

        async selectCategory(categoryId) {
            this.state.selectedCategory = categoryId;
            
            // Update UI
            document.querySelectorAll('.category_item').forEach(item => {
                item.classList.remove('selected');
            });
            document.querySelector(`[data-category-id="${categoryId}"]`)?.classList.add('selected');

            // Load services
            try {
                const services = await this.makeRequest(`/book-appointment/api/services/${categoryId}`);
                this.state.services = services || [];
                this.renderServices();
                this.showSection('service_section');
            } catch (error) {
            }
        }

        renderServices() {
            const container = document.getElementById('service_grid');
            if (!container) return;

            const html = this.state.services.map(service => `
                <div class="service_item" data-service-id="${service.id}">
                    <div class="service_image">
                        ${service.image ? `<img src="${service.image}" alt="${service.name}"/>` : '<div class="service_placeholder"></div>'}
                    </div>
                    <div class="service_info">
                        <h4 class="service_name">${service.name}</h4>
                        <p class="service_description">${service.description || ''}</p>
                        <div class="service_type">
                            ${service.is_service ? '<span class="badge badge_service">Service</span>' : ''}
                            ${service.is_package ? '<span class="badge badge_package">Package</span>' : ''}
                        </div>
                    </div>
                </div>
            `).join('');

            container.innerHTML = html;
        }

        async selectService(serviceId) {
            this.state.selectedService = serviceId;
            const service = this.state.services.find(s => s.id === serviceId);
            this.state.isPackage = service?.is_package || false;

            // Update UI
            document.querySelectorAll('.service_item').forEach(item => {
                item.classList.remove('selected');
            });
            document.querySelector(`[data-service-id="${serviceId}"]`)?.classList.add('selected');

            if (this.state.isPackage) {
                // Handle package - load package services
                await this.loadPackageServices(serviceId);
                this.showSection('package_section');
                this.updateStepIndicator(2);
            } else {
                // Handle single service
                // Reset service details
                this.state.serviceDetails = {
                    appointment_type: 'inside',
                    slot_ids: [],
                    customer_address: ''
                };

                // Load branches and show details section
                await this.loadBranches();
                this.showSection('details_section');
                this.updateStepIndicator(2);
            }
        }

        async loadPackageServices(packageId) {
            try {
                const packageServices = await this.makeRequest(`/book-appointment/api/package-services/${packageId}`);
                this.state.packageServices = packageServices || [];
                this.state.currentPackageServiceIndex = 0;
                this.state.packageServiceDetails = {};
                
                // Initialize package service details for each service
                this.state.packageServices.forEach(service => {
                    this.state.packageServiceDetails[service.id] = {
                        appointment_type: 'inside',
                        slot_ids: [],
                        customer_address: ''
                    };
                });
                
                this.renderPackageServices();
                if (this.state.packageServices.length > 0) {
                    this.selectPackageService(0);
                }
            } catch (error) {
            }
        }

        renderPackageServices() {
            const container = document.getElementById('package_services');
            if (!container || this.state.packageServices.length === 0) return;

            const html = `
                <div class="package_service_list">
                    ${this.state.packageServices.map((service, index) => `
                        <div class="package_service_item ${index === this.state.currentPackageServiceIndex ? 'active' : ''}" 
                             data-service-index="${index}">
                            <div class="package_service_info">
                                <h5>${service.name}</h5>
                                <p>${service.description || ''}</p>
                                <small>Branch: ${service.branch_name}</small>
                            </div>
                            <div class="package_service_status">
                                ${this.isPackageServiceConfigured(service.id) ? 
                                    '<i class="fa fa-check-circle text-success"></i>' : 
                                    '<i class="fa fa-clock text-warning"></i>'
                                }
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="package_service_details" id="package_service_details">
                    <!-- Current service details will be rendered here -->
                </div>
            `;

            container.innerHTML = html;
            
            // Add event listeners for package service selection
            container.querySelectorAll('.package_service_item').forEach(item => {
                item.addEventListener('click', (e) => {
                    const index = parseInt(e.currentTarget.dataset.serviceIndex);
                    this.selectPackageService(index);
                });
            });
        }

        selectPackageService(index) {
            this.state.currentPackageServiceIndex = index;
            const service = this.state.packageServices[index];
            
            // Update UI
            document.querySelectorAll('.package_service_item').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector(`[data-service-index="${index}"]`)?.classList.add('active');
            
            // Render details for current service
            this.renderCurrentPackageServiceDetails(service);
        }

        renderCurrentPackageServiceDetails(service) {
            const container = document.getElementById('package_service_details');
            if (!container) return;

            const serviceDetails = this.state.packageServiceDetails[service.id];
            
            const html = `
                <h4>Configure: ${service.name}</h4>
                
                <!-- Location type -->
                <div class="detail_group">
                    <label>Service Location:</label>
                    <div class="location_options">
                        <label class="location_option">
                            <input type="radio" name="package_appointment_type_${service.id}" value="inside" 
                                   ${serviceDetails.appointment_type === 'inside' ? 'checked' : ''}/>
                            <span class="option_text">At Salon</span>
                        </label>
                        <label class="location_option">
                            <input type="radio" name="package_appointment_type_${service.id}" value="outside"
                                   ${serviceDetails.appointment_type === 'outside' ? 'checked' : ''}/>
                            <span class="option_text">At Your Location</span>
                        </label>
                    </div>
                </div>
                
                <!-- Branch selection -->
                <div class="detail_group" id="package_branch_group_${service.id}">
                    <label for="package_branch_select_${service.id}">Select Branch:</label>
                    <select id="package_branch_select_${service.id}" class="form-control">
                        <option value="">Choose a branch...</option>
                    </select>
                </div>
                
                <!-- Employee selection -->
                <div class="detail_group">
                    <label for="package_employee_select_${service.id}">Select Employee:</label>
                    <select id="package_employee_select_${service.id}" class="form-control">
                        <option value="">Choose an employee...</option>
                    </select>
                </div>
                
                <!-- Date selection -->
                <div class="detail_group">
                    <label>Select Date:</label>
                    <div class="date_options" id="package_date_options_${service.id}">
                        <!-- Dates will be loaded dynamically -->
                    </div>
                </div>
                
                <!-- Time slot selection -->
                <div class="detail_group">
                    <label>Select Time:</label>
                    <div class="slot_options" id="package_slot_options_${service.id}">
                        <!-- Slots will be loaded dynamically -->
                    </div>
                </div>
                
                <!-- Address for outside appointments -->
                <div class="detail_group" id="package_address_group_${service.id}" 
                     style="display: ${serviceDetails.appointment_type === 'outside' ? 'block' : 'none'};">
                    <label for="package_customer_address_${service.id}">Your Address:</label>
                    <textarea id="package_customer_address_${service.id}" class="form-control" rows="3" 
                              placeholder="Enter your full address...">${serviceDetails.customer_address}</textarea>
                </div>
                
                <!-- Navigation buttons -->
                <div class="package_service_actions">
                    <button type="button" class="btn btn_outline" id="cancel_package">Cancel Package</button>
                    ${this.state.currentPackageServiceIndex > 0 ? 
                        '<button type="button" class="btn btn_secondary" id="prev_package_service">Previous Service</button>' : ''
                    }
                    ${this.state.currentPackageServiceIndex < this.state.packageServices.length - 1 ? 
                        '<button type="button" class="btn btn_primary" id="next_package_service">Next Service</button>' :
                        '<button type="button" class="btn btn_primary" id="add_package_to_cart">Add Package to Cart</button>'
                    }
                </div>
            `;

            container.innerHTML = html;
            
            // Load branches first, then setup event listeners
            this.loadPackageServiceBranches(service);
            this.setupPackageServiceEventListeners(service);
        }

        async loadPackageServiceBranches(service) {
            try {
                const branches = await this.makeRequest(`/book-appointment/api/branches/${service.id}`);
                
                const select = document.getElementById(`package_branch_select_${service.id}`);
                if (select) {
                    const html = '<option value="">Choose a branch...</option>' +
                        Object.entries(branches).map(([id, name]) => 
                            `<option value="${id}">${name}</option>`
                        ).join('');
                    select.innerHTML = html;
                    
                    // Set selected value if exists
                    const serviceDetails = this.state.packageServiceDetails[service.id];
                    if (serviceDetails.branch_id) {
                        select.value = serviceDetails.branch_id;
                        // Load employees for selected branch
                        this.loadPackageServiceEmployees(service);
                    }
                }
            } catch (error) {
            }
        }

        async loadPackageServiceEmployees(service) {
            const serviceDetails = this.state.packageServiceDetails[service.id];
            if (!serviceDetails.branch_id) return;

            try {
                const employees = await this.makeRequest(`/book-appointment/api/employees/${service.id}/${serviceDetails.branch_id}`, {
                });
                
                const select = document.getElementById(`package_employee_select_${service.id}`);
                if (select) {
                    const html = '<option value="">Choose an employee...</option>' +
                        Object.entries(employees).map(([id, employeeData]) => {
                            const employee = typeof employeeData === 'object' ? employeeData : { name: employeeData, image: false };
                            return `<option value="${id}">${employee.name}</option>`;
                        }).join('');
                    select.innerHTML = html;
                    
                    // Set selected value if exists
                    const serviceDetails = this.state.packageServiceDetails[service.id];
                    if (serviceDetails.employee_id) {
                        select.value = serviceDetails.employee_id;
                    }
                }
            } catch (error) {
            }
        }

        setupPackageServiceEventListeners(service) {
            // Appointment type change
            document.querySelectorAll(`input[name="package_appointment_type_${service.id}"]`).forEach(radio => {
                radio.addEventListener('change', (e) => {
                    this.state.packageServiceDetails[service.id].appointment_type = e.target.value;
                    this.togglePackageAddressField(service.id);
                });
            });

            // Branch selection
            const branchSelect = document.getElementById(`package_branch_select_${service.id}`);
            if (branchSelect) {
                branchSelect.addEventListener('change', (e) => {
                    this.state.packageServiceDetails[service.id].branch_id = parseInt(e.target.value) || null;
                    if (this.state.packageServiceDetails[service.id].branch_id) {
                        this.loadPackageServiceEmployees(service);
                    } else {
                        // Clear employee selection if no branch selected
                        const employeeSelect = document.getElementById(`package_employee_select_${service.id}`);
                        if (employeeSelect) {
                            employeeSelect.innerHTML = '<option value="">Choose an employee...</option>';
                        }
                    }
                });
            }

            // Employee selection
            const employeeSelect = document.getElementById(`package_employee_select_${service.id}`);
            if (employeeSelect) {
                employeeSelect.addEventListener('change', (e) => {
                    this.state.packageServiceDetails[service.id].employee_id = parseInt(e.target.value) || null;
                    if (this.state.packageServiceDetails[service.id].employee_id) {
                        this.loadPackageServiceDates(service);
                    }
                });
            }

            // Address field
            const addressField = document.getElementById(`package_customer_address_${service.id}`);
            if (addressField) {
                addressField.addEventListener('input', (e) => {
                    this.state.packageServiceDetails[service.id].customer_address = e.target.value;
                });
            }

            // Navigation buttons
            const cancelBtn = document.getElementById('cancel_package');
            const prevBtn = document.getElementById('prev_package_service');
            const nextBtn = document.getElementById('next_package_service');
            const addBtn = document.getElementById('add_package_to_cart');

            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    this.cancelPackage();
                });
            }

            if (prevBtn) {
                prevBtn.addEventListener('click', () => {
                    this.selectPackageService(this.state.currentPackageServiceIndex - 1);
                });
            }

            if (nextBtn) {
                nextBtn.addEventListener('click', () => {
                    if (this.validatePackageServiceDetails(service.id)) {
                        this.selectPackageService(this.state.currentPackageServiceIndex + 1);
                    } else {
                        alert('Please fill in all required fields for this service.');
                    }
                });
            }

            if (addBtn) {
                addBtn.addEventListener('click', () => {
                    this.addPackageToCart();
                });
            }
        }

        togglePackageAddressField(serviceId) {
            const addressGroup = document.getElementById(`package_address_group_${serviceId}`);
            const serviceDetails = this.state.packageServiceDetails[serviceId];
            
            if (addressGroup) {
                addressGroup.style.display = serviceDetails.appointment_type === 'outside' ? 'block' : 'none';
            }
        }

        async loadPackageServiceDates(service) {
            const serviceDetails = this.state.packageServiceDetails[service.id];
            if (!serviceDetails.employee_id) return;

            try {
                const dates = await this.makeRequest(`/book-appointment/api/dates/${serviceDetails.employee_id}`, {
                });
                
                this.renderPackageServiceDates(service.id, dates || []);
            } catch (error) {
            }
        }

        renderPackageServiceDates(serviceId, dates) {
            const container = document.getElementById(`package_date_options_${serviceId}`);
            if (!container) return;

            const html = dates.map(date => {
                const dateObj = new Date(date);
                const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                const dayNum = dateObj.getDate();
                const monthName = dateObj.toLocaleDateString('en-US', { month: 'short' });

                return `
                    <div class="date_option" data-service-id="${serviceId}" data-date="${date}">
                        <div class="date_day">${dayName}</div>
                        <div class="date_number">${dayNum}</div>
                        <div class="date_month">${monthName}</div>
                    </div>
                `;
            }).join('');

            container.innerHTML = html;

            // Add event listeners for date selection
            container.querySelectorAll('.date_option').forEach(option => {
                option.addEventListener('click', (e) => {
                    const selectedServiceId = parseInt(e.currentTarget.dataset.serviceId);
                    const date = e.currentTarget.dataset.date;
                    this.selectPackageServiceDate(selectedServiceId, date);
                });
            });
        }

        selectPackageServiceDate(serviceId, date) {
            this.state.packageServiceDetails[serviceId].date = date;

            // Update UI
            document.querySelectorAll(`#package_date_options_${serviceId} .date_option`).forEach(option => {
                option.classList.remove('selected');
            });
            document.querySelector(`[data-service-id="${serviceId}"][data-date="${date}"]`)?.classList.add('selected');

            // Load slots
            const service = this.state.packageServices.find(s => s.id === serviceId);
            if (service) {
                this.loadPackageServiceSlots(service);
            }
        }

        async loadPackageServiceSlots(service) {
            const serviceDetails = this.state.packageServiceDetails[service.id];
            if (!serviceDetails.employee_id || !serviceDetails.date) return;

            try {
                const slots = await this.makeRequest('/book-appointment/api/slots', {
                });
                
                this.renderPackageServiceSlots(service.id, slots || {});
            } catch (error) {
            }
        }

        renderPackageServiceSlots(serviceId, slots) {
            const container = document.getElementById(`package_slot_options_${serviceId}`);
            if (!container) return;

            if (Object.keys(slots).length === 0) {
                container.innerHTML = '<p class="no_slots">No available slots for this date.</p>';
                return;
            }

            const html = Object.values(slots).map(slot => `
                <div class="slot_option" data-service-id="${serviceId}" data-slot-ids='${JSON.stringify(slot.ids)}'>
                    <span class="slot_time">${slot.name}</span>
                </div>
            `).join('');

            container.innerHTML = html;

            // Add event listeners for slot selection
            container.querySelectorAll('.slot_option').forEach(option => {
                option.addEventListener('click', (e) => {
                    const selectedServiceId = parseInt(e.currentTarget.dataset.serviceId);
                    const slotIds = JSON.parse(e.currentTarget.dataset.slotIds);
                    this.selectPackageServiceSlot(selectedServiceId, slotIds);
                });
            });
        }

        selectPackageServiceSlot(serviceId, slotIds) {
            this.state.packageServiceDetails[serviceId].slot_ids = slotIds;

            // Update UI
            document.querySelectorAll(`#package_slot_options_${serviceId} .slot_option`).forEach(option => {
                option.classList.remove('selected');
            });
            document.querySelector(`[data-service-id="${serviceId}"][data-slot-ids='${JSON.stringify(slotIds)}']`)?.classList.add('selected');
        }

        validatePackageServiceDetails(serviceId) {
            const details = this.state.packageServiceDetails[serviceId];
            
            if (details.appointment_type === 'inside') {
                return details.branch_id && details.employee_id && details.date && details.slot_ids.length > 0;
            } else {
                return details.branch_id && details.employee_id && details.date && details.slot_ids.length > 0 && details.customer_address.trim();
            }
        }

        isPackageServiceConfigured(serviceId) {
            return this.validatePackageServiceDetails(serviceId);
        }

        async addPackageToCart() {
            // Validate all package services are configured
            let allValid = true;
            for (const service of this.state.packageServices) {
                if (!this.validatePackageServiceDetails(service.id)) {
                    allValid = false;
                    break;
                }
            }

            if (!allValid) {
                alert('Please configure all services in the package before adding to cart.');
                return;
            }

            try {
                // Get package name
                const packageService = this.state.services.find(s => s.id === this.state.selectedService);
                const packageName = packageService ? packageService.name : 'خدمة الباقة';

                // Calculate total price for package
                let totalPrice = 0;
                const packageDetails = {};

                for (const service of this.state.packageServices) {
                    const serviceDetails = this.state.packageServiceDetails[service.id];
                    const price = await this.makeRequest(`/book-appointment/api/price/${service.id}`, {
                    });
                    
                    totalPrice += price;
                    packageDetails[service.id] = {
                        ...serviceDetails
                    };
                }

                const packageData = {
                };

                const result = await this.makeRequest('/book-appointment/api/cart/add', { service_data: packageData });
                if (result.success) {
                    await this.loadCart();
                    this.resetFormAfterBooking();
                    this.backToServices();
                } else {
                    alert(result.error || 'Unable to add package to cart. Please try again.');
                }
            } catch (error) {
                alert('Error adding package to cart. Please try again.');
            }
        }

        cancelPackage() {
            // Confirm with user
            if (!confirm('Are you sure you want to cancel this package booking? All progress will be lost.')) {
                return;
            }

            // Reset package state
            this.state.selectedService = null;
            this.state.isPackage = false;
            this.state.packageServices = [];
            this.state.currentPackageServiceIndex = 0;
            this.state.packageServiceDetails = {};

            // Clear service selection UI
            document.querySelectorAll('.service_item').forEach(item => {
                item.classList.remove('selected');
            });

            // Go back to service selection
            this.showSection('service_section');
            this.updateStepIndicator(1);
        }

        async getEmployeeName(employeeId) {
            // This is a simple helper to get employee name
            // In a real implementation, you might want to cache this data
            try {
                const response = await this.makeRequest('/book-appointment/api/employee-name', { employee_id: employeeId });
                return response || 'Unknown Employee';
            } catch (error) {
                return 'Unknown Employee';
            }
        }

        async loadBranches() {
            if (!this.state.selectedService) return;

            try {
                const branches = await this.makeRequest(`/book-appointment/api/branches/${this.state.selectedService}`);
                this.state.branches = branches || {};
                this.renderBranches();
            } catch (error) {
            }
        }

        renderBranches() {
            const select = document.getElementById('branch_select');
            if (!select) return;

            const html = '<option value="">Choose a branch...</option>' +
                Object.entries(this.state.branches).map(([id, name]) => 
                    `<option value="${id}">${name}</option>`
                ).join('');

            select.innerHTML = html;
        }

        async loadEmployees() {
            if (!this.state.selectedService || !this.state.serviceDetails.branch_id) return;

            try {
                const employees = await this.makeRequest(`/book-appointment/api/employees/${this.state.selectedService}/${this.state.serviceDetails.branch_id}`);
                this.state.employees = employees || {};
                this.renderEmployees();
            } catch (error) {
            }
        }

        renderEmployees() {
            const container = document.getElementById('employee_dropdown_options');
            const selectedElement = document.getElementById('employee_dropdown_selected');
            if (!container || !selectedElement) return;

            // Reset selected display
            selectedElement.querySelector('.selected_text').textContent = 'Choose an employee...';
            document.getElementById('employee_select').value = '';

            // Render employee options
            const html = Object.entries(this.state.employees).map(([id, employeeData]) => {
                const employee = typeof employeeData === 'object' ? employeeData : { name: employeeData, image: false };
                return `
                    <div class="employee_option" data-employee-id="${id}">
                        <div class="employee_image">
                            ${employee.image ? 
                                `<img src="${employee.image}" alt="${employee.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                                 <div class="employee_placeholder" style="display: none;"><i class="fa fa-user"></i></div>` : 
                                `<div class="employee_placeholder"><i class="fa fa-user"></i></div>`
                            }
                        </div>
                        <div class="employee_info">
                            <span class="employee_name">${employee.name}</span>
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = html;

            // Add event listeners for employee selection
            this.setupEmployeeDropdownEvents();
        }

        setupEmployeeDropdownEvents() {
            const selectedElement = document.getElementById('employee_dropdown_selected');
            const optionsContainer = document.getElementById('employee_dropdown_options');
            
            if (!selectedElement || !optionsContainer) return;

            // Remove existing event listeners to prevent duplicates
            const existingSelectedClone = selectedElement.cloneNode(true);
            selectedElement.parentNode.replaceChild(existingSelectedClone, selectedElement);
            
            const newSelectedElement = document.getElementById('employee_dropdown_selected');
            
            // Toggle dropdown on click
            newSelectedElement.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const isVisible = optionsContainer.style.display === 'block';
                optionsContainer.style.display = isVisible ? 'none' : 'block';
                newSelectedElement.classList.toggle('open', !isVisible);
            });

            // Handle employee selection
            optionsContainer.addEventListener('click', (e) => {
                const employeeOption = e.target.closest('.employee_option');
                if (employeeOption) {
                    const employeeId = parseInt(employeeOption.dataset.employeeId);
                    const employeeData = this.state.employees[employeeId];
                    const employeeName = typeof employeeData === 'object' ? employeeData.name : employeeData;
                    
                    // Update selected display
                    selectedElement.querySelector('.selected_text').textContent = employeeName;
                    document.getElementById('employee_select').value = employeeId;
                    
                    // Update state
                    this.state.serviceDetails.employee_id = employeeId;
                    
                    // Hide dropdown
                    optionsContainer.style.display = 'none';
                    selectedElement.classList.remove('open');
                    
                    // Load dates for selected employee
                    this.loadDates();
                }
            });

            // Close dropdown when clicking outside (remove existing handler first)
            const closeDropdown = (e) => {
                if (!newSelectedElement.contains(e.target) && !optionsContainer.contains(e.target)) {
                    optionsContainer.style.display = 'none';
                    newSelectedElement.classList.remove('open');
                }
            };
            
            // Remove existing global click handler if it exists
            if (this.employeeDropdownHandler) {
                document.removeEventListener('click', this.employeeDropdownHandler);
            }
            
            this.employeeDropdownHandler = closeDropdown;
            document.addEventListener('click', closeDropdown);
        }

        async loadDates() {
            if (!this.state.serviceDetails.employee_id) return;

            try {
                const dates = await this.makeRequest(`/book-appointment/api/dates/${this.state.serviceDetails.employee_id}`, {
                });
                this.state.dates = dates || [];
                this.renderDates();
            } catch (error) {
            }
        }

        renderDates() {
            const container = document.getElementById('date_options');
            if (!container) return;

            const html = this.state.dates.map(date => {
                const dateObj = new Date(date);
                const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                const dayNum = dateObj.getDate();
                const monthName = dateObj.toLocaleDateString('en-US', { month: 'short' });

                return `
                    <div class="date_option" data-date="${date}">
                        <div class="date_day">${dayName}</div>
                        <div class="date_number">${dayNum}</div>
                        <div class="date_month">${monthName}</div>
                    </div>
                `;
            }).join('');

            container.innerHTML = html;
        }

        selectDate(date) {
            this.state.serviceDetails.date = date;

            // Update UI
            document.querySelectorAll('.date_option').forEach(option => {
                option.classList.remove('selected');
            });
            document.querySelector(`[data-date="${date}"]`)?.classList.add('selected');

            // Load slots
            this.loadSlots();
        }

        async loadSlots() {
            if (!this.state.serviceDetails.employee_id || !this.state.serviceDetails.date) return;

            try {
                const slots = await this.makeRequest('/book-appointment/api/slots', {
                });
                this.state.slots = slots || {};
                this.renderSlots();
            } catch (error) {
            }
        }

        renderSlots() {
            const container = document.getElementById('slot_options');
            if (!container) return;

            if (Object.keys(this.state.slots).length === 0) {
                container.innerHTML = '<p class="no_slots">No available slots for this date.</p>';
                return;
            }

            const html = Object.values(this.state.slots).map(slot => `
                <div class="slot_option" data-slot-ids='${JSON.stringify(slot.ids)}'>
                    <span class="slot_time">${slot.name}</span>
                </div>
            `).join('');

            container.innerHTML = html;
        }

        selectSlot(slotIds) {
            this.state.serviceDetails.slot_ids = slotIds;

            // Update UI
            document.querySelectorAll('.slot_option').forEach(option => {
                option.classList.remove('selected');
            });
            document.querySelector(`[data-slot-ids='${JSON.stringify(slotIds)}']`)?.classList.add('selected');
        }

        toggleAddressField() {
            const addressGroup = document.getElementById('address_group');
            const branchGroup = document.getElementById('branch_group');
            
            if (this.state.serviceDetails.appointment_type === 'outside') {
                addressGroup.style.display = 'block';
                branchGroup.style.display = 'none';
            } else {
                addressGroup.style.display = 'none';
                branchGroup.style.display = 'block';
            }
        }

        autoSelectBranchForOutside() {
            // For outside appointments, automatically select first available branch to load employees
            if (this.state.serviceDetails.appointment_type === 'outside' && Object.keys(this.state.branches).length > 0) {
                const firstBranchId = Object.keys(this.state.branches)[0];
                this.state.serviceDetails.branch_id = parseInt(firstBranchId);
                
                // Load employees for the selected branch
                this.loadEmployees();
            }
        }

        async addToCart() {
            // Validate required fields
            if (!this.validateServiceDetails()) {
                alert('Please fill in all required fields.');
                return;
            }

            try {
                // Get price
                const price = await this.getServicePrice();

                // Get service name
                const service = this.state.services.find(s => s.id === this.state.selectedService);
                const serviceName = service ? service.name : 'Unknown Service';
                
                // Get employee name
                const employeeData = this.state.employees[this.state.serviceDetails.employee_id];
                const employeeName = typeof employeeData === 'object' ? employeeData.name : (employeeData || 'Unknown Employee');
                
                // Get branch name
                const branchName = this.state.branches[this.state.serviceDetails.branch_id] || '';
                
                // Get selected slot time
                const selectedSlots = this.state.slots;
                let timeSlot = '';
                if (this.state.serviceDetails.slot_ids.length > 0) {
                    // Find the slot group that contains our selected slot IDs
                    for (const [slotName, slotData] of Object.entries(selectedSlots)) {
                        if (JSON.stringify(slotData.ids) === JSON.stringify(this.state.serviceDetails.slot_ids)) {
                            timeSlot = slotName;
                            break;
                        }
                    }
                }

                const serviceData = {
                    ...this.state.serviceDetails,
                };

                const result = await this.makeRequest('/book-appointment/api/cart/add', { service_data: serviceData });
                if (result.success) {
                    await this.loadCart();
                    this.resetFormAfterBooking();
                    this.backToServices();
                } else {
                    alert(result.error || 'Unable to add to cart. Please try again.');
                    // Refresh slots to show current availability
                    await this.loadSlots();
                }
            } catch (error) {
                alert('Error adding to cart. Please try again.');
            }
        }

        validateServiceDetails() {
            const details = this.state.serviceDetails;
            
            if (details.appointment_type === 'inside') {
                return details.branch_id && details.employee_id && details.date && details.slot_ids.length > 0;
            } else {
                return details.employee_id && details.date && details.slot_ids.length > 0 && details.customer_address.trim();
            }
        }

        async getServicePrice() {
            try {
                const price = await this.makeRequest(`/book-appointment/api/price/${this.state.selectedService}`, {
                });
                return price;
            } catch (error) {
                return 0;
            }
        }

        async loadCart() {
            try {
                const cart = await this.makeRequest('/book-appointment/api/cart');
                this.state.cart = cart || {};
                this.calculateCartTotal();
                this.renderCart();
            } catch (error) {
            }
        }

        calculateCartTotal() {
            this.state.cartTotal = Object.values(this.state.cart).reduce((total, item) => {
                return total + (item.price || 0);
            }, 0);
        }

        renderCart() {
            const container = document.getElementById('cart_items');
            const checkoutBtn = document.getElementById('proceed_checkout');
            const removeAllBtn = document.getElementById('remove_all_cart');
            
            if (!container) return;

            if (Object.keys(this.state.cart).length === 0) {
                container.innerHTML = '<p class="empty_cart">Your cart is empty</p>';
                if (checkoutBtn) checkoutBtn.style.display = 'none';
                if (removeAllBtn) removeAllBtn.style.display = 'none';
            } else {
                const html = Object.entries(this.state.cart).map(([key, item]) => {
                    if (item.is_package) {
                        // Render package item
                        const packageServices = Object.values(item.package_services || {});
                        const servicesList = packageServices.map(service => 
                            `<small>• ${service.service_name} (${service.employee_name})</small>`
                        ).join('<br>');
                        
                        return `
                            <div class="cart_item package_cart_item">
                                <div class="cart_item_info">
                                    <h5 class="cart_item_name">${item.service_name || 'خدمة الباقة'}</h5>
                                    <p class="cart_item_details">
                                        <strong>تشمل الباقة:</strong><br>
                                        ${servicesList}
                                    </p>
                                    <p class="cart_item_price">${window.getSafeCurrency(item.service_id || null)}${(item.price || 0).toFixed(2)}</p>
                                </div>
                                <button type="button" class="btn btn_remove remove_cart_item" data-cart-key="${key}">
                                    <i class="fa fa-trash"></i>
                                </button>
                            </div>
                        `;
                    } else {
                        // Render single service item
                        const locationText = item.appointment_type === 'inside' 
                            ? `At Salon${item.branch_name ? ': ' + item.branch_name : ''}`
                            : `At Your Location${item.customer_address ? ': ' + item.customer_address : ''}`;
                        
                        const dateTime = item.date && item.time_slot 
                            ? `${new Date(item.date).toLocaleDateString()} at ${item.time_slot}`
                            : item.date || 'Date not selected';
                        
                        return `
                            <div class="cart_item">
                                <div class="cart_item_info">
                                    <h5 class="cart_item_name">${item.service_name || 'Service #' + item.service_id}</h5>
                                    <p class="cart_item_details">
                                        <strong>Employee:</strong> ${item.employee_name || 'Unknown'}<br>
                                        <strong>Date & Time:</strong> ${dateTime}<br>
                                        <strong>Location:</strong> ${locationText}
                                    </p>
                                    <p class="cart_item_price">${window.getSafeCurrency(item.service_id || null)}${(item.price || 0).toFixed(2)}</p>
                                </div>
                                <button type="button" class="btn btn_remove remove_cart_item" data-cart-key="${key}">
                                    <i class="fa fa-trash"></i>
                                </button>
                            </div>
                        `;
                    }
                }).join('');

                container.innerHTML = html;
                if (checkoutBtn) checkoutBtn.style.display = 'block';
                if (removeAllBtn) removeAllBtn.style.display = 'block';
                
                // Re-attach event listeners for remove buttons
                container.querySelectorAll('.remove_cart_item').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const cartKey = btn.dataset.cartKey;
                        if (cartKey) {
                            this.removeFromCart(cartKey);
                        }
                    });
                });
            }

            // Update total
            const totalElement = document.querySelector('.total_amount');
            if (totalElement) {
                totalElement.textContent = `$${this.state.cartTotal.toFixed(2)}`;
            }
        }

        async removeFromCart(cartKey) {
            try {
                const result = await this.makeRequest('/book-appointment/api/cart/remove', { cart_key: cartKey });
                if (result.success) {
                    await this.loadCart();
                } else {
                    alert('Failed to remove item from cart. Please try again.');
                }
            } catch (error) {
                alert('Error removing from cart. Please try again.');
            }
        }

        async removeAllFromCart() {
            if (Object.keys(this.state.cart).length === 0) {
                return;
            }

            // Confirm with user
            if (!confirm('Are you sure you want to remove all items from your cart?')) {
                return;
            }

            try {
                const result = await this.makeRequest('/book-appointment/api/cart/remove-all');
                if (result.success) {
                    await this.loadCart();
                } else {
                    alert('Failed to clear cart. Please try again.');
                }
            } catch (error) {
                alert('Error clearing cart. Please try again.');
            }
        }

        proceedToCheckout() {
            window.location.href = '/book-appointment/preview-invoice';
        }

        backToServices() {
            this.showSection('service_section');
            this.updateStepIndicator(1);
        }

        backToCategories() {
            // Reset selected service and category
            this.state.selectedService = null;
            this.state.selectedCategory = null;
            
            // Clear service selection UI
            document.querySelectorAll('.service_item').forEach(item => {
                item.classList.remove('selected');
            });
            document.querySelectorAll('.category_item').forEach(item => {
                item.classList.remove('selected');
            });
            
            // Show categories section
            this.showSection('category_section');
            this.updateStepIndicator(1);
        }

        resetFormAfterBooking() {
            // Reset service details
            this.state.serviceDetails = {
                appointment_type: 'inside',
                slot_ids: [],
                customer_address: ''
            };

            // Reset form fields
            const branchSelect = document.getElementById('branch_select');
            const employeeSelect = document.getElementById('employee_select');
            const customerAddress = document.getElementById('customer_address');
            const appointmentTypeRadios = document.querySelectorAll('input[name="appointment_type"]');

            if (branchSelect) branchSelect.value = '';
            if (employeeSelect) employeeSelect.value = '';
            if (customerAddress) customerAddress.value = '';
            
            // Reset appointment type to "inside"
            appointmentTypeRadios.forEach(radio => {
                radio.checked = radio.value === 'inside';
            });

            // Clear date and slot selections
            document.querySelectorAll('.date_option').forEach(option => {
                option.classList.remove('selected');
            });
            document.querySelectorAll('.slot_option').forEach(option => {
                option.classList.remove('selected');
            });

            // Clear dates and slots containers
            const dateOptions = document.getElementById('date_options');
            const slotOptions = document.getElementById('slot_options');
            if (dateOptions) dateOptions.innerHTML = '';
            if (slotOptions) slotOptions.innerHTML = '';

            // Reset address field visibility
            this.toggleAddressField();
        }

        showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.booking_section').forEach(section => {
                section.classList.remove('active');
            });

            // Show target section
            const section = document.getElementById(sectionId);
            if (section) {
                section.classList.add('active');
            }
        }

        updateStepIndicator(step) {
            this.state.currentStep = step;
            
            document.querySelectorAll('.step').forEach((stepEl, index) => {
                stepEl.classList.remove('active', 'completed');
                if (index + 1 < step) {
                    stepEl.classList.add('completed');
                } else if (index + 1 === step) {
                    stepEl.classList.add('active');
                }
            });
        }
    }

    // Initialize the booking system
    new SimpleAppointmentBooking();
    
    // Comprehensive test function
    window.testBookingAPIs = async function() {
        
        try {
            // Test 1: Categories API
            const categoriesResp = await fetch('/book-appointment/api/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const categoriesData = await categoriesResp.json();
            
            if (!categoriesData.result || categoriesData.result.length === 0) {
                return;
            }
            
            // Test 2: Services API for Hair Cut category (ID 5)
            const servicesResp = await fetch('/book-appointment/api/services', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const servicesData = await servicesResp.json();
            
            if (!servicesData.result || servicesData.result.length === 0) {
                return;
            }
            
            // Test 3: Service Plans API for service 8
            const plansResp = await fetch('/book-appointment/api/service-plans', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const plansData = await plansResp.json();
            
            if (!plansData.result || Object.keys(plansData.result).length === 0) {
                return;
            }
            
            // Get first plan and employee info
            const firstPlan = Object.values(plansData.result)[0];
            const firstEmployee = Object.values(firstPlan.employees)[0];
            const employeeId = Object.keys(firstPlan.employees)[0];
            
            
            // Test 4: Available dates API
            const datesResp = await fetch('/book-appointment/api/available-dates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                    jsonrpc: '2.0', 
                    method: 'call', 
                    params: { employee_id: parseInt(employeeId), service_id: 8 }, 
                    id: 4 
                })
            });
            const datesData = await datesResp.json();
            
            // Test 5: Slots API for today
            const today = new Date().toISOString().split('T')[0];
            const slotsResp = await fetch('/book-appointment/api/slots', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                    jsonrpc: '2.0', 
                    method: 'call', 
                    params: { 
                        service_id: 8, 
                        appointment_type: 'inside',
                    }, 
                    id: 5 
                })
            });
            const slotsData = await slotsResp.json();
            
            // Test 6: Price API
            const priceResp = await fetch('/book-appointment/api/price', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                    jsonrpc: '2.0', 
                    method: 'call', 
                    params: { 
                        service_id: 8, 
                        appointment_type: 'inside'
                    }, 
                    id: 6 
                })
            });
            const priceData = await priceResp.json();
            
            
        } catch (error) {
        }
    };

    // Custom dialog for appointment booking success
    function showAppointmentBookedDialog(time, serviceName) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        `;

        // Create modal content
        const modal = document.createElement('div');
        modal.style.cssText = `
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            text-align: center;
            max-width: 400px;
            width: 90%;
        `;

        modal.innerHTML = `
            <div style="font-size: 48px; color: #4caf50; margin-bottom: 20px;">✓</div>
            <h2 style="color: #333; margin-bottom: 10px;">Appointment Booked!</h2>
            <p style="color: #666; margin-bottom: 20px;">
                <strong>${serviceName}</strong><br>
                Time: ${time}
            </p>
            <p style="color: #666; margin-bottom: 30px;">What would you like to do next?</p>
            <div style="display: flex; gap: 15px; justify-content: center;">
                <button id="addAnother" style="
                    background: #f4e5a1;
                    color: #333;
                    border: 2px solid #c16d4b;
                    padding: 12px 20px;
                    border-radius: 8px;
                    font-weight: 600;
                ">Add Another Appointment</button>
                <button id="proceedPayment" style="
                    background: #c16d4b;
                    border: 2px solid #c16d4b;
                    padding: 12px 20px;
                    border-radius: 8px;
                    font-weight: 600;
                ">Proceed to Payment</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Add event listeners
        document.getElementById('addAnother').onclick = function() {
            document.body.removeChild(overlay);
            // Refresh calendar to show updated availability
            if (window.initializeCalendar) {
                window.initializeCalendar();
            } else {
                location.reload();
            }
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

})();