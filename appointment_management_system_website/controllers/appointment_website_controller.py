# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, date, timedelta

_logger = logging.getLogger(__name__)
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class AppointmentPortalController(CustomerPortal):
    
    def _prepare_portal_layout_values(self):
        """Override to add appointment count to portal layout"""
        values = super()._prepare_portal_layout_values()
        # Always include appointment count for portal home display
        appointment_count = request.env['appointment.management'].search_count([
            ('partner_id', '=', request.env.user.partner_id.id)
        ]) if request.env['appointment.management'].check_access_rights('read', raise_exception=False) else 0
        values['appointment_count'] = appointment_count
        return values
    
    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_appointments(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """Display user's appointments in portal"""
        values = self._prepare_portal_layout_values()
        AppointmentMgmt = request.env['appointment.management']
        
        domain = [('partner_id', '=', request.env.user.partner_id.id)]
        
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'date desc'},
            'name': {'label': _('Reference'), 'order': 'sequence desc'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        
        # Count for pager
        appointment_count = AppointmentMgmt.search_count(domain)
        
        # Pager
        pager = request.website.pager(
            url="/my/appointments",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=appointment_count,
            page=page,
            step=self._items_per_page
        )
        
        # Get appointments
        appointments = AppointmentMgmt.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'appointments': appointments,
            'page_name': 'appointment',
            'pager': pager,
            'default_url': '/my/appointments',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        
        return request.render("appointment_management_system_website.portal_appointments", values)

    @http.route(['/my/appointments/<int:appointment_id>'], type='http', auth="user", website=True)
    def portal_appointment_detail(self, appointment_id, access_token=None, **kw):
        """Display appointment detail page"""
        try:
            appointment_sudo = self._document_check_access('appointment.management', appointment_id, access_token)
        except:
            return request.redirect('/my')
            
        values = {
            'appointment': appointment_sudo,
            'page_name': 'appointment',
        }
        return request.render("appointment_management_system_website.portal_appointment_detail", values)

    @http.route('/my/appointments/<int:appointment_id>/cancel', type='http', auth="user", methods=['POST'], website=True, csrf=False)
    def portal_cancel_appointment(self, appointment_id, cancel_reason=None, **kw):
        """Cancel appointment from portal"""
        try:
            appointment_sudo = self._document_check_access('appointment.management', appointment_id)
            if cancel_reason:
                success = appointment_sudo.portal_cancel_appointment(cancel_reason)
                if success:
                    return request.render("appointment_management_system_website.appointment_cancelled", {
                        'appointment': appointment_sudo,
                        'message': _('Your appointment has been cancelled successfully.')
                    })
            return request.redirect(f'/my/appointments/{appointment_id}?error=cancel_failed')
        except:
            return request.redirect('/my/appointments')

    @http.route('/my/appointments/<int:appointment_id>/rate', type='http', auth="user", methods=['POST'], website=True, csrf=False)
    def portal_rate_appointment(self, appointment_id, rating=None, comment=None, **kw):
        """Submit rating for completed appointment"""
        try:
            appointment_sudo = self._document_check_access('appointment.management', appointment_id)
            if rating:
                success = appointment_sudo.portal_submit_rating(rating, comment or '')
                if success:
                    return request.render("appointment_management_system_website.rating_submitted", {
                        'appointment': appointment_sudo,
                        'message': _('Thank you for your feedback!')
                    })
            return request.redirect(f'/my/appointments/{appointment_id}?error=rating_failed')
        except:
            return request.redirect('/my/appointments')


class AppointmentWebsiteController(http.Controller):
    

    @http.route('/appointment/booking', type='http', auth='public', website=True)
    def booking_home(self, **kwargs):
        """Category selection page"""
        # Check if user is authenticated
        if request.env.user._is_public():
            return request.render('appointment_management_system_website.authentication_required_template')
        
        categories = request.env['pos.category'].sudo().search([
            ('is_appointment_category', '=', True)
        ])
        
        values = {
            'categories': categories,
            'page_title': _('Select Service Category'),
        }
        return request.render('appointment_management_system_website.category_selection', values)

    @http.route('/appointment/booking/services/<int:category_id>', type='http', auth='public', website=True)
    def booking_services(self, category_id, **kwargs):
        """Service selection page"""
        # Check if user is authenticated
        if request.env.user._is_public():
            return request.render('appointment_management_system_website.authentication_required_template')
        
        # Get services for category
        all_products = request.env['product.product'].sudo().search([
            ('pos_categ_ids', 'in', [category_id])
        ])
        
        # Filter for appointment products only
        appointment_products = all_products.filtered(
            lambda p: hasattr(p, 'is_appointment_service') and (p.is_appointment_service or p.is_appointment_package)
        )
        
        # Filter to only show services with plans
        services = self._filter_services_with_plans(appointment_products)
        
        values = {
            'services': services,
            'category_id': category_id,
            'page_title': _('Select Your Service'),
        }
        return request.render('appointment_management_system_website.service_selection', values)


    @http.route('/appointment/booking/calendar', type='http', auth='public', website=True)
    def booking_calendar(self, category_id=None, **kwargs):
        """Enhanced calendar booking page with cart integration"""
        # Check if user is authenticated
        if request.env.user._is_public():
            return request.render('appointment_management_system_website.authentication_required_template')
        
        # Get services for selected category
        services = []
        if category_id:
            try:
                category_id = int(category_id)
                all_products = request.env['product.product'].sudo().search([('pos_categ_ids', 'in', [category_id])])
                appointment_products = all_products.filtered(
                    lambda p: hasattr(p, 'is_appointment_service') and (p.is_appointment_service or p.is_appointment_package)
                )
                
                # Filter to only show appointment products with plans (using same logic as working all-services endpoint)
                filtered_services = []
                for product in appointment_products:
                    has_plans = False
                    
                    if product.is_appointment_service:
                        # For regular services, check if they have plan_ids
                        has_plans = len(product.plan_ids) > 0
                    elif getattr(product, 'is_appointment_package', False):
                        # For packages, check if they have package lines
                        has_plans = len(product.appointment_package_line_ids) > 0
                    
                    if has_plans:
                        filtered_services.append(product)
                
                # Create recordset from filtered products
                if filtered_services:
                    services = filtered_services[0]
                    for product in filtered_services[1:]:
                        services += product
                else:
                    services = request.env['product.product'].sudo().search([('pos_categ_ids', 'in', [category_id])])

            except (ValueError, TypeError):
                pass
        
        # if not services:
        #     # Get all appointment services as fallback
        #     all_appointment_services = request.env['product.product'].sudo().search([
        #         '|',
        #         ('is_appointment_service', '=', True),
        #         ('is_appointment_package', '=', True)
        #     ])
        #
        #     # Filter to only show services with plans (using same logic as working all-services endpoint)
        #     filtered_services = []
        #     for service in all_appointment_services:
        #         has_plans = False
        #
        #         if service.is_appointment_service:
        #             # For regular services, check if they have plan_ids
        #             has_plans = len(service.plan_ids) > 0
        #         elif getattr(service, 'is_appointment_package', False):
        #             # For packages, check if they have package lines
        #             has_plans = len(service.appointment_package_line_ids) > 0
        #
        #         if has_plans:
        #             filtered_services.append(service)
        #
        #     # Create recordset from filtered services
        #     if filtered_services:
        #         services = filtered_services[0]
        #         for service in filtered_services[1:]:
        #             services += service
        #     else:
        #         services = request.env['product.product']
        
        values = {
            'page_title': _('Select Service and Time'),
            'services': services,
            'category_id': category_id,
            'company_currency': request.website.company_id.currency_id.symbol,
            'service_currencies': {service.id: service.currency_id.symbol for service in services},
        }
        return request.render('appointment_management_system_website.booking_calendar', values)
    
    @http.route('/book-appointment/api/package-services', type='json', auth='public', website=True, csrf=False)
    def get_package_services(self, package_id, **kwargs):
        """Get services included in a package"""
        try:
            package = request.env['product.product'].sudo().browse(int(package_id))
            if not package.exists() or not package.is_appointment_package:
                return {'error': 'Package not found'}
            
            # Get package lines (services included in the package)
            services = []
            if hasattr(package, 'appointment_package_line_ids'):
                for line in package.appointment_package_line_ids:
                    services.append({
                        'id': line.service_id.id,
                        'name': line.service_id.name,
                        'description': line.service_id.description_sale or '',
                        'image': line.service_id.image_1920,
                        'quantity': line.quantity,
                    })
            
            return services
            
        except Exception as e:
            return {'error': str(e)}

    @http.route('/appointment/cart/add', type='json', auth='public', website=True, csrf=False)
    def add_appointment_to_cart(self, **kwargs):
        """Add appointment service or package to Odoo eCommerce cart and create draft appointments"""
        try:
            # For JSON-RPC format with type='json', appointment_data comes directly in kwargs
            appointment_data = kwargs.get('appointment_data', {})

            # Check if this is a package booking
            is_package = appointment_data.get('is_package', False)
            service_id = appointment_data.get('service_id')
            
            if not service_id:
                return {'error': 'Service ID is required'}
            
            product = request.env['product.product'].sudo().browse(int(service_id))
            if not product.exists():
                return {'error': 'Service/Package not found'}
            
            # Handle package booking
            if is_package and 'package_services' in appointment_data:
                return self._handle_package_cart_addition(product, appointment_data)
            
            # Handle single service booking (existing logic)
            return self._handle_single_service_cart_addition(product, appointment_data)
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/appointment/confirm/<int:appointment_id>', type='json', auth='user', website=True, csrf=False)
    def confirm_appointment_manual(self, appointment_id):
        """Manual appointment confirmation endpoint for testing"""
        try:
            appointment = request.env['appointment.management'].sudo().browse(appointment_id)
            
            if not appointment.exists():
                return {'error': 'Appointment not found'}
            
            if appointment.state != '1':
                return {'error': f'Appointment is not in Partial Approved state (current: {appointment.state})'}
            
            # Confirm the appointment
            if appointment.sale_order_id:
                appointment.confirm_appointment_payment(appointment.sale_order_id)
                return {
                    'success': True,
                    'message': f'Appointment {appointment.sequence} confirmed successfully',
                    'new_state': appointment.state,
                    'slot_states': [{'id': slot.id, 'state': slot.state} for slot in appointment.slot_ids]
                }
            else:
                return {'error': 'No sale order linked to appointment'}
                
        except Exception as e:
            return {'error': str(e)}
    
    @http.route('/appointment/status/<int:appointment_id>', type='json', auth='public', website=True, csrf=False)
    def get_appointment_status(self, appointment_id):
        """Get appointment and slot status for debugging"""
        try:
            appointment = request.env['appointment.management'].sudo().browse(appointment_id)
            
            if not appointment.exists():
                return {'error': 'Appointment not found'}
            
            slot_info = []
            for slot in appointment.slot_ids:
                slot_info.append({
                    'id': slot.id,
                    'state': slot.state,
                    'time': slot.time,
                    'date': str(slot.date),
                    'reserved_until': str(slot.reserved_until) if slot.reserved_until else None,
                    'reserved_by': slot.reserved_by,
                })
            
            return {
                'appointment_id': appointment.id,
                'sequence': appointment.sequence,
                'state': appointment.state,
                'sale_order_id': appointment.sale_order_id.id if appointment.sale_order_id else None,
                'slot_reserved': appointment.slot_reserved,
                'slots': slot_info,
                'partner': appointment.partner_id.name,
                'service': appointment.product_id.name,
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _handle_single_service_cart_addition(self, product, appointment_data):
        """Handle adding a single service to cart"""
        try:
            # Get service ID from appointment data or product
            service_id = appointment_data.get('service_id') or product.id
            
            # Get actual user and employee details
            employee_id = int(appointment_data.get('employee_id', 2))  # Use test employee as fallback
            partner_id = request.env.user.partner_id.id  # Use actual logged-in user
            company_id = request.website.company_id.id  # Use website's company
            
            # Calculate price based on plan_ids, employee department, and location
            branch_id = appointment_data.get('branch_id', 1)
            appointment_type = appointment_data.get('appointment_type', 'inside')

            try:
                plan_price = product.action_get_appointment_service_price(branch_id, employee_id, appointment_type, False)
                price = float(plan_price) if plan_price and plan_price > 0 else 0.0
            except Exception as e:
                price = 0.0
            
            slot_ids = appointment_data.get('slot_ids', [])
            if isinstance(slot_ids, list):
                slot_ids = [sid for sid in slot_ids if sid is not None]
            
            # If no slot IDs provided, try to find the slot based on employee, date, and time
            if not slot_ids and appointment_data.get('time'):
                try:
                    # Convert time string to float (e.g., "08:00" -> 8.0)
                    time_str = appointment_data.get('time', '')
                    if ':' in time_str:
                        hour, minute = time_str.split(':')
                        db_time = float(hour) + float(minute) / 60
                        
                        # Find available slot in database (check availability)
                        slot = request.env['appointment.employee.slot'].sudo().search([
                            ('employee_id', '=', employee_id),
                            ('date', '=', appointment_data.get('date')),
                            ('time', '=', db_time),
                        ], limit=1)
                        
                        if slot and slot.is_available_for_booking():
                            slot_ids = [slot.id]
                        else:
                            return {'success': False, 'error': 'Selected time slot is not available or already reserved. Please select a different time.'}
                except Exception as e:
                    return {'success': False, 'error': f'Error checking slot availability: {str(e)}'}
            
            if not slot_ids:
                return {'success': False, 'error': 'Selected time slot is not available. Please select a different time.'}
            
            # Validate slots are available for booking
            available_slots = request.env['appointment.employee.slot'].sudo().browse(slot_ids).filtered(
                lambda s: s.is_available_for_booking()
            )
            
            if not available_slots:
                return {'success': False, 'error': 'Selected time slots are no longer available. Please select different time slots.'}
            
            # Prepare appointment data for creation with reservation
            appointment_creation_data = {
                'partner_id': partner_id,
                'product_id': int(service_id),
                'employee_id': employee_id,
                'date': appointment_data.get('date'),
                'appointment_type': appointment_type,
                'branch_id': branch_id,
                'company_id': company_id,
                'price_unit': price,
                'slot_ids': available_slots.ids,
                'notes': f"Website booking - {appointment_data.get('appointment_type', 'at branch')}",
                'customer_street': appointment_data.get('customer_street'),
                'customer_phone': appointment_data.get('customer_phone'),
                'customer_city': appointment_data.get('customer_city'),
                'customer_notes': appointment_data.get('customer_notes'),
            }
            
            # Create appointment with slot reservation (Partial Approved state)
            appointment = request.env['appointment.management'].sudo().create_from_cart(appointment_creation_data)
            
            # Try to add to cart (with proper error handling)
            try:
                # Get or create website sale order
                website = request.env['website'].get_current_website()
                sale_company = website.company_id
                partner = request.env.user.partner_id
                if partner.company_id and partner.company_id != sale_company:
                    partner.sudo().write({'company_id': False})
                order = website.sale_get_order(force_create=True)
                
                # Create order line directly to avoid parameter conflicts
                order_line_vals = {
                    'order_id': order.id,
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'price_unit': price,
                    'is_appointment_custom_price': True,
                    'name': f"{product.name} - Appointment {appointment_data.get('date')} at {appointment_data.get('time')}",
                }

                order_line = request.env['sale.order.line'].sudo().create(order_line_vals)
                
                # Link appointment to sale order and order line
                appointment.write({
                    'sale_order_id': order.id,
                    'order_line_id': order_line.id,
                })
                    
                return {
                    'success': True,
                    'appointment_id': appointment.id,
                    'order_id': order.id,
                    'order_line_id': order_line.id,
                    'cart_quantity': len(order.order_line),
                    'message': f'Appointment created and added to cart for {appointment_data.get("date")} at {appointment_data.get("time")}',
                    'cart_url': '/shop/cart'
                }
                
            except Exception as cart_error:
                # If cart fails, still return success for appointment creation
                return {
                    'success': True,
                    'appointment_id': appointment.id,
                    'message': f'Appointment created for {appointment_data.get("date")} at {appointment_data.get("time")}',
                    'cart_error': str(cart_error),
                    'note': 'Appointment created successfully, but cart integration failed'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _handle_package_cart_addition(self, package_product, appointment_data):
        """Handle adding a complete package to cart as a single line"""
        try:
            package_services = appointment_data.get('package_services', {})
            if not package_services:
                return {'success': False, 'error': 'No package services data provided'}
            
            # First, check for slot conflicts across all package services
            used_slots = set()
            for service_id_str, service_data in package_services.items():
                employee_id = int(service_data.get('employee_id', 2))
                date = service_data.get('date')
                time = service_data.get('time')
                
                if date and time:
                    slot_key = f"{employee_id}-{date}-{time}"
                    if slot_key in used_slots:
                        return {
                            'success': False, 
                            'error': f'Slot conflict detected: {time} on {date} is selected for multiple services. Please choose different times.'
                        }
                    used_slots.add(slot_key)
            
            # Calculate total package price
            total_price = 0
            appointment_ids = []
            detailed_description_parts = []
            
            # Create appointments for each service in the package
            for service_id_str, service_data in package_services.items():
                service_id = int(service_id_str)
                service_product = request.env['product.product'].sudo().browse(service_id)
                
                if not service_product.exists():
                    continue
                
                # Use provided data or defaults
                employee_id = int(service_data.get('employee_id', 2))
                partner_id = request.env.user.partner_id.id  # Use actual logged-in user
                company_id = request.website.company_id.id  # Use website's company
                
                # Calculate price for this service in package context
                branch_id = service_data.get('branch_id', 1)
                appointment_type = service_data.get('appointment_type', 'inside')
                try:
                    plan_price = service_product.action_get_appointment_service_price(
                        branch_id, employee_id, appointment_type, package_product.id
                    )
                    price = plan_price if plan_price else 0.0
                    total_price += price
                except:
                    price = 0.0
                
                # Handle slot_ids
                slot_ids = service_data.get('slot_ids', [])
                if isinstance(slot_ids, list):
                    slot_ids = [sid for sid in slot_ids if sid is not None]
                
                # Find slot by time if no slot IDs provided
                if not slot_ids and service_data.get('time'):
                    try:
                        time_str = service_data.get('time', '')
                        if ':' in time_str:
                            hour, minute = time_str.split(':')
                            db_time = float(hour) + float(minute) / 60
                            
                            # Find available slot
                            slot = request.env['appointment.employee.slot'].sudo().search([
                                ('employee_id', '=', employee_id),
                                ('date', '=', service_data.get('date')),
                                ('time', '=', db_time),
                            ], limit=1)
                            
                            if slot and slot.is_available_for_booking():
                                slot_ids = [slot.id]
                    except Exception as e:
                        # Log error for debugging
                        import logging
                        _logger = logging.getLogger(__name__)
                        _logger.error(f"Error finding slot for package service: {str(e)}")
                        pass
                
                if slot_ids:
                    # Validate slots are available for booking
                    available_slots = request.env['appointment.employee.slot'].sudo().browse(slot_ids).filtered(
                        lambda s: s.is_available_for_booking()
                    )
                    
                    if available_slots:
                        # Prepare appointment data for creation with reservation
                        appointment_creation_data = {
                            'partner_id': partner_id,
                            'product_id': service_id,
                            'employee_id': employee_id,
                            'date': service_data.get('date'),
                            'appointment_type': appointment_type,
                            'branch_id': branch_id,
                            'company_id': company_id,
                            'price_unit': price,
                            'slot_ids': available_slots.ids,
                            'notes': f"Package booking ({package_product.name}) - {appointment_type}",
                            'customer_street': service_data.get('customer_street'),
                            'customer_phone': service_data.get('customer_phone'),
                            'customer_city': service_data.get('customer_city'),
                            'customer_notes': service_data.get('customer_notes'),
                        }
                        
                        # Create appointment with slot reservation (Partial Approved state)
                        appointment = request.env['appointment.management'].sudo().create_from_cart(appointment_creation_data)
                        appointment_ids.append(appointment.id)
                        
                        # Build detailed description for order line
                        employee = request.env['hr.employee'].sudo().browse(employee_id)
                        detailed_description_parts.append(
                            f"• {service_product.name} - {service_data.get('date')} at {service_data.get('time')} "
                            f"with {employee.name if employee.exists() else 'Staff'} ({appointment_type})"
                        )
            
            if not appointment_ids:
                return {'success': False, 'error': 'No valid appointments could be created for package'}
            
            # Add package to cart as single line
            try:
                website = request.env['website'].get_current_website()
                sale_company = website.company_id
                partner = request.env.user.partner_id
                if partner.company_id and partner.company_id != sale_company:
                    partner.sudo().write({'company_id': False})
                order = website.sale_get_order(force_create=True)
                
                # Create detailed package description
                package_description = f"{package_product.name} - Complete Package\n"
                package_description += "\n".join(detailed_description_parts)
                
                # Create single order line for the package
                order_line_vals = {
                    'order_id': order.id,
                    'product_id': package_product.id,
                    'product_uom_qty': 1,
                    'price_unit': total_price,
                    'is_appointment_custom_price': True,
                    'name': package_description,
                }
                
                order_line = request.env['sale.order.line'].sudo().create(order_line_vals)
                
                # Link all appointments to sale order and order line
                appointments = request.env['appointment.management'].sudo().browse(appointment_ids)
                appointments.write({
                    'sale_order_id': order.id,
                    'order_line_id': order_line.id,
                })
                
                return {
                    'success': True,
                    'appointment_ids': appointment_ids,
                    'order_id': order.id,
                    'order_line_id': order_line.id,
                    'cart_quantity': len(order.order_line),
                    'message': f'Package "{package_product.name}" with {len(appointment_ids)} services added to cart successfully',
                    'cart_url': '/shop/cart'
                }
                
            except Exception as cart_error:
                return {
                    'success': True,
                    'appointment_ids': appointment_ids,
                    'message': f'Package appointments created, but cart integration failed: {str(cart_error)}',
                    'note': 'Appointments created successfully, but cart integration failed'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/appointment/proceed-to-checkout', type='http', auth='public', website=True)
    def proceed_to_checkout(self, **post):
        """Proceed to Odoo eCommerce checkout"""
        return request.redirect('/shop/checkout')


    # Legacy route for backward compatibility
    @http.route('/book-appointment', type='http', auth='public', website=True)
    def book_appointment_page(self, **kwargs):
        """Legacy main booking page - redirect to calendar"""
        # Check if user is authenticated
        if request.env.user._is_public():
            return request.render('appointment_management_system_website.authentication_required_template')
        
        return request.redirect('/appointment/booking/calendar')

    @http.route('/book-appointment/api/categories', type='json', auth='public', website=True)
    def get_categories(self):
        """API endpoint to get appointment categories"""
        categories = request.env['pos.category'].sudo().search([
            ('is_appointment_category', '=', True)
        ])
        
        result = []
        for category in categories:
            # Check if category has image field (both custom and standard)
            image_url = False
            if hasattr(category, 'image') and category.image:
                # Use custom image field from appointment module
                image_url = f'/web/image/pos.category/{category.id}/image?unique={category.write_date}'
            elif hasattr(category, 'image_128') and category.image_128:
                # Fallback to standard POS category image
                image_url = f'/web/image/pos.category/{category.id}/image_128?unique={category.write_date}'
                
            result.append({
                'id': category.id,
                'name': category.name,
                'image': image_url,
                'has_image': bool(image_url),
            })
        return result

    @http.route('/book-appointment/api/package-services/<int:package_id>', type='json', auth='public', website=True)
    def get_package_services(self, package_id):
        """Get services included in a package"""
        package = request.env['product.product'].sudo().browse(package_id)
        if not package.exists() or not package.is_appointment_package:
            return []
        
        result = []
        for package_line in package.appointment_package_line_ids:
            service = package_line.product_id
            result.append({
                'id': service.id,
                'name': service.name,
                'description': service.description_sale or '',
                'package_line_id': package_line.id,
                'branch_id': package_line.branch_id.id,
                'branch_name': package_line.branch_id.name,
                'department_id': package_line.department_id.id,
                'department_name': package_line.department_id.name,
                'image': f'/web/image/product.product/{service.id}/image_1920' if service.image_1920 else False,
            })
        return result

    @http.route('/book-appointment/api/services', type='json', auth='public', website=True)
    def get_services_by_category(self, category_id=None):
        """Get services for a specific category"""
        try:
            # First, let's get all appointment products
            all_appointment_products = request.env['product.product'].sudo().search([
                '|', 
                ('is_appointment_service', '=', True),
                ('is_appointment_package', '=', True)
            ])
            
            # Filter by category if specified
            if category_id:
                category_products = all_appointment_products.filtered(
                    lambda p: category_id in p.pos_categ_ids.ids
                )
            else:
                category_products = all_appointment_products

            
            result = []
            for product in category_products:
                # Only include services that have plans
                has_plans = False
                
                if product.is_appointment_service:
                    # For regular services, check if they have plan_ids
                    has_plans = len(product.plan_ids) > 0
                elif getattr(product, 'is_appointment_package', False):
                    # For packages, check if they have package lines
                    has_plans = len(product.appointment_package_line_ids) > 0
                
                # Only add to result if service has plans
                if has_plans:
                    result.append({
                        'id': product.id,
                        'name': product.name,
                        'description': product.description_sale or '',
                        'is_service': product.is_appointment_service,
                        'is_package': product.is_appointment_package,
                        'image': f'/web/image/product.product/{product.id}/image_1920' if product.image_1920 else False,
                    })
            
            return result
        except Exception as e:
            return []

    @http.route('/book-appointment/api/test-plans', type='json', auth='public', website=True)
    def test_plan_counts(self, service_id=None):
        """Test endpoint to check exact plan counts"""
        try:
            service = request.env['product.product'].sudo().browse(int(service_id))
            if service.exists():
                return {
                    'service_id': service_id,
                    'service_name': service.name,
                    'is_appointment_service': service.is_appointment_service,
                    'plan_ids_count': len(service.plan_ids),
                    'plan_ids': [{'id': p.id, 'department': p.department_id.name} for p in service.plan_ids],
                    'would_be_filtered': len(service.plan_ids) == 0
                }
            return {'error': 'Service not found'}
        except Exception as e:
            return {'error': str(e)}

    @http.route('/book-appointment/api/debug-services', type='json', auth='public', website=True)
    def debug_services(self, category_id=None):
        """Debug endpoint to check service loading"""
        try:
            # Get all products
            all_products = request.env['product.product'].sudo().search([])
            
            # Check appointment fields
            appointment_products = []
            for product in all_products:
                if hasattr(product, 'is_appointment_service') and product.is_appointment_service:
                    appointment_products.append({
                        'id': product.id,
                        'name': product.name,
                        'is_appointment_service': product.is_appointment_service,
                        'is_appointment_package': getattr(product, 'is_appointment_package', False),
                        'pos_categ_ids': product.pos_categ_ids.ids if hasattr(product, 'pos_categ_ids') else []
                    })
            
            return {
                'total_products': len(all_products),
                'appointment_products': appointment_products,
                'category_filter': category_id
            }
        except Exception as e:
            return {'error': str(e)}

    @http.route('/book-appointment/api/all-services', type='json', auth='public', website=True)
    def get_all_appointment_services(self):
        """Get all appointment services from database - only show services with plans"""
        try:
            # Get all appointment services
            appointment_services = request.env['product.product'].sudo().search([
                '|',
                ('is_appointment_service', '=', True),
                ('is_appointment_package', '=', True)
            ])
            
            result = []
            total_services = len(appointment_services)
            
            for service in appointment_services:
                # Only include services that have plans
                has_plans = False
                
                if service.is_appointment_service:
                    # For regular services, check if they have plan_ids
                    has_plans = len(service.plan_ids) > 0
                elif getattr(service, 'is_appointment_package', False):
                    # For packages, check if they have package lines
                    has_plans = len(service.appointment_package_line_ids) > 0
                
                # Log service analysis
                plan_count = len(service.plan_ids) if service.is_appointment_service else 0
                package_count = len(service.appointment_package_line_ids) if getattr(service, 'is_appointment_package', False) else 0

                # Only add to result if service has plans
                if has_plans:
                    result.append({
                        'id': service.id,
                        'name': service.name,
                        'description': service.description_sale or '',
                        'is_service': service.is_appointment_service,
                        'is_package': getattr(service, 'is_appointment_package', False),
                        'image': f'/web/image/product.product/{service.id}/image_1920' if service.image_1920 else False,
                    })

            return result

        except Exception as e:
            return []

    @http.route('/book-appointment/api/all-employees', type='json', auth='public', website=True)
    def get_all_appointment_employees(self):
        """Get all appointment employees from database"""
        try:
            # Get all appointment employees
            employees = request.env['hr.employee'].sudo().search([
                ('is_appointment_employee', '=', True)
            ])
            
            result = {}
            for emp in employees:
                image_url = False
                if emp.image_1920:
                    image_url = f'/web/image/hr.employee/{emp.id}/image_1920?unique={emp.write_date}'
                
                result[str(emp.id)] = {
                    'name': emp.name,
                    'image': image_url,
                    'has_image': bool(emp.image_1920),
                    'branch_name': emp.company_id.name if emp.company_id else 'Main Branch',
                    'department_name': emp.department_id.name if emp.department_id else 'General',
                    'department_id': emp.department_id.id if emp.department_id else None
                }
            
            return result
        except Exception as e:
            return {}

    @http.route('/book-appointment/api/service-plans', type='json', auth='public', website=True)
    def get_service_plans(self, service_id=None):
        """Get service plans with departments, slots, pricing, and availability"""
        if not service_id:
            return {}
            
        service = request.env['product.product'].sudo().browse(service_id)
        if not service.exists() or not (service.is_appointment_service or service.is_appointment_package):
            return {}
        
        plans_data = {}
        for plan in service.plan_ids:
            # Get employees for this department
            employees = request.env['hr.employee'].sudo().search([
                ('department_id', '=', plan.department_id.id),
                ('is_appointment_employee', '=', True)
            ])
            
            employee_data = {}
            for emp in employees:
                image_url = False
                if emp.image_1920:
                    image_url = f'/web/image/hr.employee/{emp.id}/image_1920?unique={emp.write_date}'
                
                employee_data[str(emp.id)] = {
                    'name': emp.name,
                    'image': image_url,
                    'has_image': bool(emp.image_1920),
                    'branch_name': plan.branch_id.name if plan.branch_id else 'Main Branch'
                }
            
            plans_data[str(plan.id)] = {
                'id': plan.id,
                'branch_name': plan.branch_id.name if plan.branch_id else 'Main Branch',
                'department_id': plan.department_id.id,
                'department_name': plan.department_id.name,
                'slots_inside': plan.service_slot_inside,
                'slots_outside': plan.service_slot_outside,
                'price_inside': plan.service_price_inside,
                'price_outside': plan.service_price_outside,
                'duration': getattr(service, 'appointment_duration', 60),  # Service duration in minutes
                'employees': employee_data
            }
        
        return plans_data

    @http.route('/book-appointment/api/branches', type='json', auth='public', website=True)
    def get_service_branches(self, service_id=None, package_id=False):
        """Get available branches for a service"""
        service = request.env['product.product'].sudo().browse(service_id)
        if service_id:
            service = request.env['product.product'].sudo().browse(service_id)
            if not service.exists() or not (service.is_appointment_service or service.is_appointment_package):
                return {}
            branches = service.action_get_appointment_branch(package_id)
            return branches
        else:
            # Return all branches for general use
            departments = request.env['hr.department'].sudo().search([('is_appointment_department', '=', True)])
            return {dept.id: dept.name for dept in departments}

    @http.route('/book-appointment/api/employees', type='json', auth='public', website=True)
    def get_service_employees(self, service_id=None, branch_id=None, package_id=False):
        """Get available employees for a service and branch with photos"""
        if service_id and branch_id:
            service = request.env['product.product'].sudo().browse(service_id)
            employee_dict = service.action_get_appointment_employee(branch_id, package_id)
        elif branch_id:
            # Get all employees for branch
            employees = request.env['hr.employee'].sudo().search([('department_id', '=', branch_id), ('is_appointment_employee', '=', True)])
            employee_dict = {str(emp.id): emp.name for emp in employees}
        else:
            return {}
        
        # Enhance with employee photos
        result = {}
        for emp_id, emp_name in employee_dict.items():
            employee = request.env['hr.employee'].sudo().browse(int(emp_id))
            image_url = False
            if employee.image_1920:
                image_url = f'/web/image/hr.employee/{employee.id}/image_1920?unique={employee.write_date}'
            
            result[emp_id] = {
                'name': emp_name,
                'image': image_url,
                'has_image': bool(employee.image_1920),
                'department_id': employee.department_id.id if employee.department_id else None,
                'department_name': employee.department_id.name if employee.department_id else None
            }
        
        return result

    @http.route('/book-appointment/api/available-dates', type='json', auth='public', website=True)
    def get_available_dates(self, employee_id=None, service_id=None, package_id=False):
        """Get available dates for booking"""
        if service_id and employee_id:
            service = request.env['product.product'].sudo().browse(service_id)
            dates = service.action_get_appointment_date(employee_id, package_id)
            return dates
        elif employee_id:
            # Generate next 30 days as available dates
            dates = []
            import pytz
            user_tz = request.env.user.tz or 'UTC'
            tz = pytz.timezone(user_tz)
            today = datetime.now(tz).date()
            for i in range(30):
                date_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
                dates.append(date_str)
            return dates
        else:
            return []

    @http.route('/book-appointment/api/slots', type='json', auth='public', website=True)
    def get_employee_slots(self, service_id=None, employee_id=None, date=None, appointment_type=None, branch_id=None, package_id=False):
        if not service_id or not employee_id or not date:
            return {}
        try:
            service = request.env['product.product'].sudo().browse(service_id)
            slots = service.action_get_appointment_employee_slot(
                employee_id, date, appointment_type or 'inside', branch_id, package_id
            )
            if slots:
                return slots
            return service.get_all_available_slot_groups_records(int(employee_id), date if not isinstance(date, str) else datetime.strptime(date, '%Y-%m-%d').date(), 1)
        except Exception:
            return {}
    
    def _get_slot_price(self, service_id, employee_id, appointment_type, branch_id):
        """Helper to get slot price"""
        try:
            if service_id:
                service = request.env['product.product'].sudo().browse(service_id)
                
                # Check if this service is part of a package
                package_line = self._get_package_line_for_service(service_id)
                if package_line:
                    # Use package line pricing
                    if appointment_type == 'outside':
                        return package_line.service_price_outside
                    else:
                        return package_line.service_price_inside
                
                # Use regular service pricing
                return service.action_get_appointment_service_price(
                    branch_id, employee_id, appointment_type, False
                )
        except:
            pass
        return False
    
    def _get_package_line_for_service(self, service_id):
        """Helper to get package line for a service if it exists"""
        try:
            package_line = request.env['appointment.package.line'].sudo().search([
                ('product_id', '=', int(service_id))
            ], limit=1)
            return package_line if package_line.exists() else None
        except:
            return None
    
    def _get_service_duration(self, service_id, appointment_type):
        """Helper to get service duration from package line or plan"""
        try:
            # Check if this service is part of a package
            package_line = self._get_package_line_for_service(service_id)
            if package_line:
                # Use package line slot duration
                if appointment_type == 'outside':
                    return package_line.service_slot_outside * 30  # Convert slots to minutes
                else:
                    return package_line.service_slot_inside * 30
            
            # Use regular service duration (default 60 minutes)
            return 60
        except:
            return 60
    
    def _calculate_end_time(self, start_time_float, duration_minutes):
        """Helper to calculate end time"""
        end_time_float = start_time_float + (duration_minutes / 60.0)
        return f"{int(end_time_float):02d}:{int((end_time_float % 1) * 60):02d}"

    @http.route('/book-appointment/api/price-dynamic', type='http', auth='public', website=True, csrf=False, methods=['POST'])
    def get_service_price(self, service_id=None, branch_id=None, employee_id=None, appointment_type=None, package_id=False):
        """Get service price based on selection - dynamic pricing from plan_ids only"""
        import json
        try:
            # Handle JSON body for POST requests
            data = json.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            service_id = data.get('service_id', service_id)
            branch_id = data.get('branch_id', branch_id)
            employee_id = data.get('employee_id', employee_id)
            appointment_type = data.get('appointment_type', appointment_type)
            
            if not service_id or not employee_id or not branch_id:
                response = {'error': 'Missing required parameters'}
                return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])
                
            service = request.env['product.product'].sudo().browse(int(service_id))
            if not service.exists():
                response = {'error': 'Service not found'}
                return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])
                
            employee = request.env['hr.employee'].sudo().browse(int(employee_id))
            if not employee.exists():
                response = {'error': 'Employee not found'}
                return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])
                
            if not employee.department_id:
                response = {'error': 'Employee has no department'}
                return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])
            
            # Find plan for this service, branch, and employee's department
            plan = service.plan_ids.filtered(
                lambda r: r.branch_id.id == int(branch_id) and 
                         r.department_id.id == employee.department_id.id
            )
            
            price = 0.0
            if plan:
                if appointment_type == 'inside':
                    price = float(plan[0].service_price_inside)
                elif appointment_type == 'outside':
                    price = float(plan[0].service_price_outside)
                    
            response = {
                'result': price,
                'service_id': service_id,
                'employee_id': employee_id,
                'employee_dept': employee.department_id.id,
                'branch_id': branch_id,
                'plan_count': len(plan)
            }
            return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])
                
        except Exception as e:
            response = {'error': str(e)}
            return request.make_response(json.dumps(response), headers=[('Content-Type', 'application/json')])

    @http.route('/book-appointment/api/summary-price', type='json', auth='public', website=True, csrf=False)
    def get_summary_price(self, service_id, branch_id, employee_id, appointment_type):
        """Get appointment service price for summary display - uses same logic as working cart"""
        try:
            service = request.env['product.product'].sudo().browse(int(service_id))
            if not service.exists():
                return False
            
            # Check if this service is part of a package
            package_line = self._get_package_line_for_service(service_id)
            if package_line:
                # Use package line pricing
                if appointment_type == 'outside':
                    price = package_line.service_price_outside
                else:
                    price = package_line.service_price_inside
            else:
                # Use the same exact logic as the working cart session
                price = service.action_get_appointment_service_price(
                    branch_id,
                    employee_id,
                    appointment_type,
                    False
                )
            return price
            
        except Exception as e:
            return False

    @http.route('/book-appointment/api/employee-name', type='json', auth='public', website=True)
    def get_employee_name(self, employee_id):
        """Get employee name by ID"""
        employee = request.env['hr.employee'].sudo().browse(int(employee_id))
        return employee.name if employee.exists() else 'Unknown Employee'

    @http.route('/book-appointment/api/cart/add', type='json', auth='public', website=True)
    def add_to_cart(self, service_data):
        """Add service to cart session and reserve slots"""
        import time
        cart = request.session.get('appointment_cart', {})
        
        # Validate required fields
        if not service_data.get('service_id'):
            return {'success': False, 'error': 'Service ID is required'}
        
        if not service_data.get('employee_id'):
            return {'success': False, 'error': 'Employee selection is required'}
        
        if not service_data.get('slot_ids'):
            return {'success': False, 'error': 'Time slot selection is required'}
        
        # Create unique cart key to allow multiple services/appointments
        timestamp = str(int(time.time() * 1000))  # milliseconds for uniqueness
        employee_id = service_data.get('employee_id', 'unknown')
        date = service_data.get('date', 'unknown')
        cart_key = f"{service_data['service_id']}_{employee_id}_{date}_{timestamp}"
        
        try:
            # Get service and employee details for cart display
            service = request.env['product.product'].sudo().browse(service_data['service_id'])
            employee = request.env['hr.employee'].sudo().browse(service_data['employee_id'])
            
            if not service.exists():
                return {'success': False, 'error': 'Invalid service selected'}
            
            if not employee.exists():
                return {'success': False, 'error': 'Invalid employee selected'}
            
            # Handle package services
            if service_data.get('is_package') and 'package_services' in service_data:
                # For packages, use package ID in cart key
                cart_key = f"package_{service_data['service_id']}_{timestamp}"
                all_slot_ids = []
                # Collect all slot IDs from package services
                for service_id, details in service_data['package_services'].items():
                    if 'slot_ids' in details and details['slot_ids']:
                        all_slot_ids.extend(details['slot_ids'])
                
                if all_slot_ids:
                    slots = request.env['appointment.employee.slot'].sudo().browse(all_slot_ids)
                    # Only proceed if all slots are in draft state
                    if all(slot.state == 'draft' for slot in slots):
                        slots.write({'state': 'wait'})
                        
                        # Calculate package total price
                        total_package_price = 0.0
                        for service_id, details in service_data['package_services'].items():
                            try:
                                service_product = request.env['product.product'].sudo().browse(int(service_id))
                                service_price = service_product.action_get_appointment_service_price(
                                    branch_id=details.get('branch_id'),
                                    employee_id=details.get('employee_id'),
                                    appointment_type=details.get('appointment_type', 'inside'),
                                    package_id=service_data['service_id']  # Pass package ID
                                )
                                if service_price and service_price > 0:
                                    total_package_price += float(service_price)
                                    details['price'] = float(service_price)  # Store individual service price
                                else:
                                    details['price'] = 0.0
                            except Exception as e:
                                details['price'] = 0.0
                        
                        # Enhance service data for cart display
                        service_data['service_name'] = service.name
                        service_data['timestamp'] = timestamp
                        service_data['price'] = total_package_price
                        service_data['total_package_price'] = total_package_price

                        cart[cart_key] = service_data
                        request.session['appointment_cart'] = cart
                        return {'success': True, 'cart_count': len(cart), 'cart_key': cart_key}
                    else:
                        return {'success': False, 'error': 'Some slots are no longer available. Please select different time slots.'}
            
            # Handle single service
            elif 'slot_ids' in service_data and service_data['slot_ids']:
                slot_ids = service_data['slot_ids']
                slots = request.env['appointment.employee.slot'].sudo().browse(slot_ids)
                
                # Only proceed if all slots are in draft state
                if all(slot.state == 'draft' for slot in slots):
                    # Get slot details for time display
                    first_slot = slots[0] if slots else None
                    time_slot = first_slot.name if first_slot else 'Unknown time'
                    
                    # Get and validate price
                    price = service_data.get('price', 0)

                    # Always calculate price to ensure accuracy
                    try:
                        calculated_price = service.action_get_appointment_service_price(
                            branch_id=service_data.get('branch_id'),
                            employee_id=service_data.get('employee_id'),
                            appointment_type=service_data.get('appointment_type', 'inside'),
                            package_id=False
                        )

                        # Use calculated price if it's valid, otherwise use frontend price
                        if calculated_price and calculated_price > 0:
                            price = float(calculated_price)
                        elif price:
                            price = float(price)
                        else:
                            price = 0.0
                            
                    except Exception as e:
                        # Fallback to frontend price or 0.0
                        price = float(price) if price else 0.0
                    
                    # Reserve slots
                    slots.write({'state': 'wait'})
                    
                    # Enhance service data for cart display
                    enhanced_service_data = {
                        **service_data,
                        'service_name': service.name,
                        'employee_name': employee.name,
                        'time_slot': time_slot,
                        'price': price,
                        'timestamp': timestamp,
                        'branch_name': service_data.get('branch_name', ''),
                    }
                    
                    cart[cart_key] = enhanced_service_data
                    request.session['appointment_cart'] = cart
                    return {'success': True, 'cart_count': len(cart), 'cart_key': cart_key}
                else:
                    return {'success': False, 'error': 'Some slots are no longer available. Please select different time slots.'}
            
            # Fallback for services without slots (should not happen)
            return {'success': False, 'error': 'No time slots provided for booking'}
            
        except Exception as e:
            return {'success': False, 'error': 'An error occurred while adding to cart. Please try again.'}

    @http.route('/book-appointment/api/cart/remove', type='json', auth='user', website=True)
    def remove_from_cart(self, cart_key):
        """Remove service from cart and release slots"""
        cart = request.session.get('appointment_cart', {})
        if cart_key in cart:
            service_data = cart[cart_key]
            
            # Handle package services
            if service_data.get('is_package') and 'package_services' in service_data:
                all_slot_ids = []
                # Collect all slot IDs from package services
                for service_id, details in service_data['package_services'].items():
                    if 'slot_ids' in details and details['slot_ids']:
                        all_slot_ids.extend(details['slot_ids'])
                
                if all_slot_ids:
                    slots = request.env['appointment.employee.slot'].sudo().browse(all_slot_ids)
                    # Only release slots that are in 'wait' state (reserved by this user)
                    wait_slots = slots.filtered(lambda s: s.state == 'wait')
                    wait_slots.write({'state': 'draft'})
            
            # Handle single service
            elif 'slot_ids' in service_data and service_data['slot_ids']:
                slot_ids = service_data['slot_ids']
                slots = request.env['appointment.employee.slot'].sudo().browse(slot_ids)
                # Only release slots that are in 'wait' state (reserved by this user)
                wait_slots = slots.filtered(lambda s: s.state == 'wait')
                wait_slots.write({'state': 'draft'})
            
            del cart[cart_key]
        request.session['appointment_cart'] = cart
        return {'success': True, 'cart_count': len(cart)}

    @http.route('/book-appointment/api/cart/remove-all', type='json', auth='user', website=True)
    def remove_all_from_cart(self):
        """Remove all services from cart and release all slots"""
        cart = request.session.get('appointment_cart', {})
        
        # Release all slots before clearing cart
        for cart_key, service_data in cart.items():
            # Handle package services
            if service_data.get('is_package') and 'package_services' in service_data:
                all_slot_ids = []
                # Collect all slot IDs from package services
                for service_id, details in service_data['package_services'].items():
                    if 'slot_ids' in details and details['slot_ids']:
                        all_slot_ids.extend(details['slot_ids'])
                
                if all_slot_ids:
                    slots = request.env['appointment.employee.slot'].sudo().browse(all_slot_ids)
                    # Only release slots that are in 'wait' state
                    wait_slots = slots.filtered(lambda s: s.state == 'wait')
                    wait_slots.write({'state': 'draft'})
            
            # Handle single service
            elif 'slot_ids' in service_data and service_data['slot_ids']:
                slot_ids = service_data['slot_ids']
                slots = request.env['appointment.employee.slot'].sudo().browse(slot_ids)
                # Only release slots that are in 'wait' state
                wait_slots = slots.filtered(lambda s: s.state == 'wait')
                wait_slots.write({'state': 'draft'})
        
        # Clear the entire cart
        request.session['appointment_cart'] = {}
        return {'success': True, 'cart_count': 0}

    @http.route('/book-appointment/api/cart', type='json', auth='user', website=True)
    def get_cart(self):
        """Get current cart contents"""
        cart = request.session.get('appointment_cart', {})
        return cart

    @http.route('/book-appointment/preview-invoice', type='http', auth='user', website=True)
    def preview_invoice(self, **kwargs):
        """Step 2: Preview invoice before payment"""
        cart = request.session.get('appointment_cart', {})
        if not cart:
            return request.redirect('/book-appointment')

        # Calculate totals and prepare invoice data
        total_amount = 0
        invoice_lines = []
        
        for cart_key, service_data in cart.items():
            service = request.env['product.product'].sudo().browse(service_data['service_id'])
            price = service_data.get('price', 0)
            total_amount += price
            
            invoice_lines.append({
                'product': service,
                'price': price,
                'service_data': service_data
            })

        values = {
            'cart': cart,
            'invoice_lines': invoice_lines,
            'total_amount': total_amount,
            'partner': request.env.user.partner_id,
            'page_title': _('Invoice Preview'),
        }
        return request.render('appointment_management_system_website.invoice_preview', values)

    @http.route('/book-appointment/confirm-booking', type='http', auth='user', website=True, methods=['POST'])
    def confirm_booking(self, **kwargs):
        """Step 3: Create appointments and invoice, redirect to payment"""
        cart = request.session.get('appointment_cart', {})
        if not cart:
            return request.redirect('/book-appointment')

        partner = request.env.user.partner_id
        
        # Create invoice
        invoice_vals = {
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'state': 'draft',
            'invoice_line_ids': []
        }

        # Create appointments and invoice lines
        appointment_ids = []
        for cart_key, service_data in cart.items():
            service = request.env['product.product'].sudo().browse(service_data['service_id'])
            
            # Create appointment using existing method
            appointment_details = {
                'service_id': service_data.get('package_id', False),
                'isSelectedServicePack': bool(service_data.get('package_id')),
                'services': {
                    str(service.id): {
                        'branch_id': service_data['branch_id'],
                        'employee_id': service_data['employee_id'],
                        'appointment_type': service_data['appointment_type'],
                        'date': service_data['date'],
                        'slot_ids': service_data['slot_ids'],
                    }
                }
            }
            
            appointments = service.action_create_appointments(partner.id, appointment_details)
            appointment_ids.extend([data['appointment_id'] for data in appointments['services'].values()])
            
            # Add invoice line
            price = service_data.get('price', 0)
            invoice_vals['invoice_line_ids'].append((0, 0, {
                'product_id': service.id,
                'name': service.name,
                'quantity': 1,
                'price_unit': price,
            }))

        # Create invoice
        invoice = request.env['account.move'].sudo().create(invoice_vals)
        
        # Clear cart
        request.session['appointment_cart'] = {}
        
        # Store appointment IDs for later update after payment
        request.session['pending_appointments'] = appointment_ids
        request.session['payment_invoice_id'] = invoice.id
        
        # Redirect to payment
        return request.redirect(f'/my/invoices/{invoice.id}')

    @http.route('/book-appointment/payment-success', type='http', auth='user', website=True)
    def payment_success(self, **kwargs):
        """Handle successful payment"""
        appointment_ids = request.session.get('pending_appointments', [])
        
        if appointment_ids:
            # Update appointment status to approved
            appointments = request.env['appointment.management'].sudo().browse(appointment_ids)
            appointments.write({'state': '2'})  # Approved
            
            # Set all associated slots to 'done'
            for appointment in appointments:
                if appointment.slot_ids:
                    appointment.slot_ids.sudo().write({'state': 'done'})
            
            # Clear session data
            request.session.pop('pending_appointments', None)
            request.session.pop('payment_invoice_id', None)
        
        return request.render('appointment_management_system_website.payment_success', {
            'appointment_ids': appointment_ids,
            'page_title': _('Booking Confirmed'),
        })


    def _prepare_home_portal_values(self, counters):
        """Add appointment count to portal home"""
        values = super()._prepare_home_portal_values(counters)
        if 'appointment_count' in counters:
            appointment_count = request.env['appointment.management'].search_count([
                ('partner_id', '=', request.env.user.partner_id.id)
            ]) if request.env['appointment.management'].check_access_rights('read', raise_exception=False) else 0
            values['appointment_count'] = appointment_count
        return values