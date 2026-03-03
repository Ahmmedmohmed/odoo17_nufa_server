# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta


class AppointmentManagement(models.Model):
    _inherit = 'appointment.management'
    
    website_booking = fields.Boolean(string='Website Booking', default=False)
    customer_address = fields.Text(string='Customer Address')
    sale_order_id = fields.Many2one('sale.order', string='Related Sale Order')
    order_line_id = fields.Many2one('sale.order.line', string='Related Order Line')
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True)
    cart_reservation_expiry = fields.Datetime(string='Cart Reservation Expiry')
    slot_reserved = fields.Boolean(string='Slot Reserved', default=False)
    
    # Customer location fields (for "At Your Location" services)
    customer_street = fields.Char(string='Customer Street', help="Customer's street address for at-location service")
    customer_phone = fields.Char(string='Customer Phone', help="Customer's phone number for at-location service")
    customer_city = fields.Char(string='Customer City', help="Customer's city for at-location service")
    customer_notes = fields.Text(string='Customer Notes', help="Additional notes from customer for the appointment")
    
    # Portal functionality fields
    cancel_reason = fields.Text(string='Cancellation Reason', help="Reason provided by customer for cancelling the appointment")
    employee_rating = fields.Selection([
        ('1', '⭐'),
        ('2', '⭐⭐'), 
        ('3', '⭐⭐⭐'),
        ('4', '⭐⭐⭐⭐'),
        ('5', '⭐⭐⭐⭐⭐')
    ], string='Employee Rating', help="Customer rating for the employee")
    rating_comment = fields.Text(string='Rating Comment', help="Customer comment about the service")
    
    # Computed fields for smart buttons
    has_sale_order = fields.Boolean(string='Has Sale Order', compute='_compute_has_sale_order')

    @api.depends('sale_order_id')
    def _compute_has_sale_order(self):
        for appointment in self:
            appointment.has_sale_order = bool(appointment.sale_order_id)

    @api.depends('sale_order_id', 'sale_order_id.currency_id')
    def _compute_currency_id(self):
        for appointment in self:
            if appointment.sale_order_id:
                appointment.currency_id = appointment.sale_order_id.currency_id
            else:
                appointment.currency_id = appointment.env.company.currency_id

    def action_view_sale_order(self):
        """Action to view the related sale order"""
        self.ensure_one()
        if not self.sale_order_id:
            return
            
        return {
            'name': 'Sale Order',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
            'context': self.env.context,
        }
    
    @api.model
    def create_from_cart(self, appointment_data):
        """Create appointment when adding to cart with Partial Approved state"""

        appointment_datetime = self._get_appointment_datetime(appointment_data)
        display_date = self._get_display_date(appointment_data)

        vals = {
            'partner_id': appointment_data.get('partner_id'),
            'date': appointment_datetime,
            'display_date': display_date,
            'branch_id': appointment_data.get('branch_id'),
            'company_id': appointment_data.get('company_id'),
            'product_id': appointment_data.get('product_id'),
            'employee_id': appointment_data.get('employee_id'),
            'price_unit': appointment_data.get('price_unit', 0.0),
            'state': '1',  # Partial Approved
            'appointment_type': appointment_data.get('appointment_type', 'inside'),
            'website_booking': True,
            'slot_reserved': True,
            'customer_street': appointment_data.get('customer_street'),
            'customer_phone': appointment_data.get('customer_phone'),
            'customer_city': appointment_data.get('customer_city'),
            'customer_notes': appointment_data.get('customer_notes'),
            'cart_reservation_expiry': fields.Datetime.now() + timedelta(minutes=30),  # 30 min reservation
            'notes': appointment_data.get('notes', ''),
        }
        
        # Handle slot_ids if provided
        if 'slot_ids' in appointment_data:
            vals['slot_ids'] = [(6, 0, appointment_data['slot_ids'])]

        try:
            # Log the datetime being used for debugging
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Creating appointment with datetime: {appointment_datetime} for date: {appointment_data.get('date')}")
            
            appointment = self.create(vals)
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(f"Error creating appointment: {str(e)}")
            raise
        
        # Reserve the slots using existing 'wait' state
        if appointment.slot_ids:
            appointment.slot_ids.write({
                'state': 'wait',  # Use existing wait state for reservation
                'reserved_until': appointment.cart_reservation_expiry,
                'reserved_by': appointment.id,
            })
        
        return appointment
    
    def confirm_appointment_payment(self, sale_order):
        """Confirm appointment after successful payment"""
        self.ensure_one()
        
        # Update appointment state to Approved
        self.write({
            'state': '2',  # Approved
            'sale_order_id': sale_order.id,
            'slot_reserved': False,  # No longer just reserved, now confirmed
        })
        
        # Update slots to confirmed state (done = confirmed booking)
        if self.slot_ids:
            self.slot_ids.write({
                'state': 'done',  # Use existing done state for confirmed bookings
                'reserved_until': False,
                'reserved_by': False,
            })
        
        return True
    
    def portal_cancel_appointment(self, reason):
        """Cancel appointment from portal with reason"""
        self.ensure_one()
        if self.state in ['1', '2']:  # Partial Approved or Approved
            self.write({
                'state': '4',  # Cancelled
                'cancel_reason': reason,
            })
            
            # Free up the slots
            if self.slot_ids:
                self.slot_ids.write({
                    'state': 'draft',  # Return to available state
                    'reserved_until': False,
                    'reserved_by': False,
                })
            return True
        return False
    
    def portal_submit_rating(self, rating, comment):
        """Submit rating from portal"""
        self.ensure_one()
        if self.state == '3':  # Completed
            # Map star rating (1-5) to service_rate values (0-3)
            rating_mapping = {
                '1': '0',  # 1 star = Low
                '2': '1',  # 2 stars = Medium  
                '3': '1',  # 3 stars = Medium
                '4': '2',  # 4 stars = High
                '5': '3'   # 5 stars = Very High
            }
            
            service_rate_value = rating_mapping.get(str(rating), '1')  # Default to Medium
            
            self.write({
                'employee_rating': rating,  # Keep both for compatibility
                'service_rate': service_rate_value,  # Map to backend field
                'rating_comment': comment,
            })
            return True
        return False
    
    def _get_appointment_datetime(self, appointment_data):
        date_str = appointment_data.get('date')
        if not date_str:
            return fields.Datetime.now()

        slot_ids_list = appointment_data.get('slot_ids', [])
        if slot_ids_list:
            try:
                slot_ids = self.env['appointment.employee.slot'].sudo().browse(slot_ids_list)
                if slot_ids:
                    first_slot = slot_ids[0]
                    appt_date = first_slot.date
                    time_str = first_slot.name
                    appt_time = datetime.strptime(time_str, "%H:%M").time()
                    naive_dt = datetime.combine(appt_date, appt_time)
                    return fields.Datetime.to_string(naive_dt)
            except Exception:
                pass

        appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        return fields.Datetime.to_string(datetime.combine(appointment_date, datetime.min.time()))

    def _get_display_date(self, appointment_data):
        slot_ids_list = appointment_data.get('slot_ids', [])
        if slot_ids_list:
            try:
                slot_ids = self.env['appointment.employee.slot'].sudo().browse(slot_ids_list)
                if slot_ids:
                    first_slot = slot_ids[0]
                    return f"{first_slot.date.strftime('%Y-%m-%d')} {first_slot.name}:00"
            except Exception:
                pass
        date_str = appointment_data.get('date', '')
        return date_str
    
    def cancel_reservation(self):
        """Cancel slot reservation (e.g., when cart item is removed or expires)"""
        self.ensure_one()
        
        # Free up the slots
        if self.slot_ids:
            self.slot_ids.write({
                'state': 'draft',  # Return to available (draft) state
                'reserved_until': False,
                'reserved_by': False,
            })
        
        # Cancel or delete the appointment
        self.write({'state': '4'})  # Cancelled
        
        return True
    
    @api.model
    def cleanup_expired_reservations(self):
        """Cron job to cleanup expired cart reservations"""
        expired_appointments = self.search([
            ('state', '=', '1'),  # Partial Approved
            ('slot_reserved', '=', True),
            ('cart_reservation_expiry', '<', fields.Datetime.now()),
        ])
        
        for appointment in expired_appointments:
            appointment.cancel_reservation()
        
        return len(expired_appointments)
    
    def _get_portal_return_action(self):
        """Return action for portal redirect after form submission"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/appointments/%s' % self.id,
        }


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    appointment_count = fields.Integer(
        string='Appointment Count',
        compute='_compute_appointment_count'
    )
    
    def _compute_appointment_count(self):
        """Compute number of appointments for this partner"""
        for partner in self:
            partner.appointment_count = self.env['appointment.management'].search_count([
                ('partner_id', '=', partner.id)
            ])
    
    def action_view_appointments(self):
        """Action to view partner's appointments"""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('appointment_management_system.action_appointment_management')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    # Add currency field for service-specific currency
    currency_id = fields.Many2one('res.currency', string='Service Currency', 
                                  default=lambda self: self.env.company.currency_id,
                                  help="Currency for this service pricing")
    
    def get_website_appointment_price(self, appointment_type='inside', branch_id=None, department_id=None):
        """Get appointment price for website display"""
        self.ensure_one()
        
        if not self.is_appointment_service and not self.is_appointment_package:
            return 0.0
        
        if self.is_appointment_package:
            # For packages, return the sum of all service prices
            total_price = 0.0
            for line in self.appointment_package_line_ids:
                if appointment_type == 'inside':
                    total_price += line.service_price_inside
                else:
                    total_price += line.service_price_outside
            return total_price
        
        else:
            # For services, get price from plan
            if branch_id and department_id:
                plan = self.plan_ids.filtered(
                    lambda p: p.branch_id.id == branch_id and p.department_id.id == department_id
                )
                if plan:
                    return plan.service_price_inside if appointment_type == 'inside' else plan.service_price_outside
            
            # Fallback to first available plan
            if self.plan_ids:
                plan = self.plan_ids[0]
                return plan.service_price_inside if appointment_type == 'inside' else plan.service_price_outside
                
        return 0.0
    
    def get_website_appointment_duration(self, appointment_type='inside', branch_id=None, department_id=None):
        """Get appointment duration in slots (30min each)"""
        self.ensure_one()
        
        if not self.is_appointment_service and not self.is_appointment_package:
            return 1
        
        if self.is_appointment_package:
            # For packages, return total slots needed
            total_slots = 0
            for line in self.appointment_package_line_ids:
                if appointment_type == 'inside':
                    total_slots += line.service_slot_inside
                else:
                    total_slots += line.service_slot_outside
            return total_slots
        
        else:
            # For services, get slots from plan
            if branch_id and department_id:
                plan = self.plan_ids.filtered(
                    lambda p: p.branch_id.id == branch_id and p.department_id.id == department_id
                )
                if plan:
                    return plan.service_slot_inside if appointment_type == 'inside' else plan.service_slot_outside
            
            # Fallback to first available plan
            if self.plan_ids:
                plan = self.plan_ids[0]
                return plan.service_slot_inside if appointment_type == 'inside' else plan.service_slot_outside
                
        return 1


class AppointmentEmployeeSlot(models.Model):
    _inherit = 'appointment.employee.slot'
    
    # Add reservation tracking fields to existing model
    reserved_until = fields.Datetime(string='Reserved Until')
    reserved_by = fields.Integer(string='Reserved By Appointment ID')
    
    def is_available_for_booking(self):
        """Check if slot is available for new bookings"""
        self.ensure_one()
        
        # Available if in draft state
        if self.state == 'draft':
            return True
        
        # Check if wait state reservation has expired
        if self.state == 'wait' and self.reserved_until:
            if fields.Datetime.now() > self.reserved_until:
                # Auto-cleanup expired reservation
                self.write({
                    'state': 'draft',
                    'reserved_until': False,
                    'reserved_by': False,
                })
                return True
        
        return False
    
    def reserve_slot(self, appointment_id, minutes=30):
        """Reserve slot for specific appointment using wait state"""
        self.ensure_one()
        
        if not self.is_available_for_booking():
            return False
        
        self.write({
            'state': 'wait',  # Use existing wait state for reservation
            'reserved_until': fields.Datetime.now() + timedelta(minutes=minutes),
            'reserved_by': appointment_id,
        })
        return True
    
    def confirm_booking(self):
        """Confirm the slot booking (after payment)"""
        self.ensure_one()
        
        self.write({
            'state': 'done',  # Use existing done state for confirmed bookings
            'reserved_until': False,  # No longer needed
        })
        return True


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    appointment_ids = fields.One2many(
        'appointment.management', 
        'sale_order_id',
        string='Related Appointments'
    )
    appointment_count = fields.Integer(
        compute='_compute_appointment_count',
        string='Appointment Count'
    )
    
    def _compute_appointment_count(self):
        for order in self:
            order.appointment_count = len(order.appointment_ids)
    
    def action_confirm(self):
        """Override to confirm appointments when order is confirmed"""
        res = super().action_confirm()
        
        # Confirm all related appointments
        for appointment in self.appointment_ids.filtered(lambda a: a.state == '1'):
            appointment.confirm_appointment_payment(self)
        
        return res
    
    def action_view_appointments(self):
        """Action to view related appointments"""
        self.ensure_one()
        if self.appointment_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Appointment'),
                'res_model': 'appointment.management',
                'res_id': self.appointment_ids.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Appointments'),
                'res_model': 'appointment.management',
                'domain': [('id', 'in', self.appointment_ids.ids)],
                'view_mode': 'tree,form',
                'target': 'current',
            }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    appointment_id = fields.Many2one('appointment.management', string='Related Appointment')
    
    def unlink(self):
        """Cancel appointment reservation when order line is removed"""
        appointments_to_cancel = self.mapped('appointment_id').filtered(
            lambda a: a.state == '1' and a.slot_reserved
        )
        
        for appointment in appointments_to_cancel:
            appointment.cancel_reservation()
        
        return super().unlink()


class WebsiteSale(models.Model):
    _inherit = 'website'
    
    def sale_confirm_order(self, transaction=None):
        """Override to confirm appointments after website sale confirmation"""
        order = self.sale_get_order()
        result = super().sale_confirm_order(transaction=transaction)
        
        if order and order.state in ('draft', 'sent'):
            order.action_confirm()
        
        if order and order.state in ('sale', 'done'):
            pending_appointments = order.appointment_ids.filtered(lambda a: a.state == '1')
            for appointment in pending_appointments:
                appointment.confirm_appointment_payment(order)
        
        return result


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_pending(self, state_message=None, extra_allowed_states=()):
        txs = super()._set_pending(state_message=state_message, extra_allowed_states=extra_allowed_states)
        self._confirm_appointment_orders()
        return txs

    def _set_authorized(self, state_message=None, **kwargs):
        txs = super()._set_authorized(state_message=state_message, **kwargs)
        self._confirm_appointment_orders()
        return txs

    def _set_done(self, state_message=None, extra_allowed_states=()):
        txs = super()._set_done(state_message=state_message, extra_allowed_states=extra_allowed_states)
        self._confirm_appointment_orders()
        return txs

    def _confirm_appointment_orders(self):
        for tx in self:
            for order in tx.sale_order_ids:
                if order.appointment_ids and order.state in ('draft', 'sent'):
                    order.with_context(send_email=True).action_confirm()


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    
    def action_post(self):
        """Override to confirm appointments when payment is posted"""
        res = super().action_post()
        
        # Find related sale orders through account moves/invoices
        for payment in self:
            if payment.state == 'posted':
                # Get related invoices
                related_invoices = payment.reconciled_invoice_ids
                for invoice in related_invoices:
                    # Find sale orders related to these invoices
                    sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
                    for order in sale_orders:
                        # Confirm pending appointments
                        pending_appointments = order.appointment_ids.filtered(lambda a: a.state == '1')
                        for appointment in pending_appointments:
                            appointment.confirm_appointment_payment(order)
        
        return res


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    appointment_ids = fields.One2many(
        'appointment.management', 
        compute='_compute_appointment_ids',
        string='Related Appointments'
    )
    appointment_count = fields.Integer(
        compute='_compute_appointment_ids',
        string='Appointment Count'
    )
    
    def _compute_appointment_ids(self):
        """Compute related appointments based on invoice lines"""
        for invoice in self:
            appointments = self.env['appointment.management']
            
            # Find appointments through sale order lines
            if invoice.invoice_line_ids:
                sale_lines = invoice.invoice_line_ids.mapped('sale_line_ids')
                appointment_ids = []
                
                for line in sale_lines:
                    if hasattr(line, 'appointment_id') and line.appointment_id:
                        appointment_ids.append(line.appointment_id.id)
                
                if appointment_ids:
                    appointments = self.env['appointment.management'].browse(appointment_ids)
                else:
                    # Fallback: Find appointments created around the same time for the same partner
                    # with services matching invoice lines
                    if invoice.partner_id and invoice.invoice_line_ids:
                        service_ids = invoice.invoice_line_ids.mapped('product_id').filtered(
                            lambda p: hasattr(p, 'is_appointment_service') and (p.is_appointment_service or p.is_appointment_package)
                        ).ids
                        
                        if service_ids:
                            # Look for appointments created within 1 hour of invoice
                            time_range = invoice.create_date or fields.Datetime.now()
                            appointments = self.env['appointment.management'].search([
                                ('partner_id', '=', invoice.partner_id.id),
                                ('product_id', 'in', service_ids),
                                ('create_date', '>=', time_range - timedelta(hours=1)),
                                ('create_date', '<=', time_range + timedelta(hours=1)),
                            ])
            
            invoice.appointment_ids = appointments
            invoice.appointment_count = len(appointments)
    
    def action_post(self):
        """Override to confirm appointments when invoice is posted/paid"""
        res = super().action_post()
        
        for invoice in self:
            if invoice.move_type in ('out_invoice', 'out_refund') and invoice.state == 'posted':
                # Check if invoice is paid (payment_state)
                if invoice.payment_state in ('paid', 'in_payment'):
                    # Find related sale orders and confirm appointments
                    sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
                    for order in sale_orders:
                        pending_appointments = order.appointment_ids.filtered(lambda a: a.state == '1')
                        for appointment in pending_appointments:
                            appointment.confirm_appointment_payment(order)
                            
                # Also confirm appointments directly linked to this invoice
                pending_appointments = invoice.appointment_ids.filtered(lambda a: a.state == '1')
                if invoice.payment_state in ('paid', 'in_payment'):
                    for appointment in pending_appointments:
                        # Create a dummy sale order context for the confirmation
                        if appointment.sale_order_id:
                            appointment.confirm_appointment_payment(appointment.sale_order_id)
        
        return res
    
    def _write(self, vals):
        """Override to catch payment state changes"""
        res = super()._write(vals)
        
        # Check if payment state changed to paid
        if 'payment_state' in vals and vals.get('payment_state') in ('paid', 'in_payment'):
            for invoice in self:
                if invoice.move_type in ('out_invoice', 'out_refund'):
                    # Find and confirm related appointments
                    sale_orders = invoice.invoice_line_ids.mapped('sale_line_ids').mapped('order_id')
                    for order in sale_orders:
                        pending_appointments = order.appointment_ids.filtered(lambda a: a.state == '1')
                        for appointment in pending_appointments:
                            appointment.confirm_appointment_payment(order)
                    
                    # Also check direct appointment links
                    pending_appointments = invoice.appointment_ids.filtered(lambda a: a.state == '1')
                    for appointment in pending_appointments:
                        if appointment.sale_order_id:
                            appointment.confirm_appointment_payment(appointment.sale_order_id)
        
        return res
    
    def action_view_appointments(self):
        """Action to view related appointments"""
        self.ensure_one()
        if self.appointment_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Appointment'),
                'res_model': 'appointment.management',
                'res_id': self.appointment_ids.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Appointments'),
                'res_model': 'appointment.management',
                'domain': [('id', 'in', self.appointment_ids.ids)],
                'view_mode': 'tree,form',
                'target': 'current',
            }