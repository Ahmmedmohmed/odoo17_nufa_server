# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AppointmentRefundRequest(models.Model):
    _name = 'appointment.refund.request'
    _description = 'Appointment Refund Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'sequence'

    sequence = fields.Char('Request #', default=lambda self: _('New'), required=True, readonly=True, copy=False)

    # Link to appointment
    appointment_id = fields.Many2one('appointment.management', string='Appointment', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', related='appointment_id.partner_id', store=True)

    # Refund amounts
    original_price = fields.Float('Original Price', related='appointment_id.price_unit', store=True)
    refund_amount = fields.Float('Refund Amount', required=True, help='Amount to be refunded to customer')

    # Refund method
    refund_method = fields.Selection([
        ('wallet', 'E-Wallet (Automatic)'),
        ('same_card', 'Same Card Used for Payment'),
        ('bank_transfer', 'Bank Transfer (Manual)')
    ], string='Refund Method', required=True, default='wallet')

    # Bank details for manual refund
    bank_name = fields.Char('Bank Name')
    account_holder_name = fields.Char('Account Holder Name')
    account_number = fields.Char('Account Number / IBAN')
    swift_code = fields.Char('SWIFT/BIC Code')

    # Card info reference (for same card refund)
    card_last_four = fields.Char('Card Last 4 Digits', help='Last 4 digits of the card used for payment')
    card_type = fields.Char('Card Type', help='e.g., Visa, Mastercard')
    transaction_reference = fields.Char('Original Transaction Reference')

    # Request details
    reason = fields.Text('Customer Reason', help='Reason provided by customer for refund request')

    # Status
    state = fields.Selection([
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('declined', 'Declined')
    ], string='Status', default='pending', required=True, tracking=True)

    # Admin response
    admin_notes = fields.Text('Admin Notes', help='Internal notes from admin')
    decline_reason = fields.Text('Decline Reason', help='Reason for declining the refund request')

    # Timestamps
    requested_at = fields.Datetime('Requested At', default=fields.Datetime.now, readonly=True)
    reviewed_at = fields.Datetime('Reviewed At', readonly=True)
    completed_at = fields.Datetime('Completed At', readonly=True)

    # Reviewed by
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('appointment.refund.request.sequence') or _('New')
        return super(AppointmentRefundRequest, self).create(vals)

    def action_approve(self):
        """Approve the refund request."""
        for request in self:
            if request.state != 'pending':
                raise UserError(_('Only pending requests can be approved.'))

            request.write({
                'state': 'approved',
                'reviewed_at': datetime.now(),
                'reviewed_by': self.env.uid,
            })

            # For wallet refunds, process automatically
            if request.refund_method == 'wallet':
                request.action_process_wallet_refund()

    def action_process_wallet_refund(self):
        """Process wallet refund automatically."""
        for request in self:
            if request.refund_method != 'wallet':
                raise UserError(_('This action is only for wallet refunds.'))

            if request.refund_amount > 0 and request.partner_id:
                request.partner_id.sudo().add_wallet_credit(
                    amount=request.refund_amount,
                    source_type='refund',
                    source_description='Refund for appointment %s' % request.appointment_id.sequence,
                    notes='Refund request %s approved' % request.sequence,
                )

                request.write({
                    'state': 'completed',
                    'completed_at': datetime.now(),
                })

                _logger.info("Wallet refund processed: %s for partner %s, amount: %.2f",
                            request.sequence, request.partner_id.id, request.refund_amount)

    def action_mark_processing(self):
        """Mark as processing (for bank transfer / card refunds)."""
        for request in self:
            if request.state != 'approved':
                raise UserError(_('Only approved requests can be marked as processing.'))

            request.write({
                'state': 'processing',
            })

    def action_mark_completed(self):
        """Mark refund as completed after manual processing."""
        for request in self:
            if request.state not in ('approved', 'processing'):
                raise UserError(_('Only approved or processing requests can be marked as completed.'))

            request.write({
                'state': 'completed',
                'completed_at': datetime.now(),
            })

    def action_decline(self):
        """Decline the refund request - opens wizard for reason."""
        return {
            'name': _('Decline Refund Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'appointment.refund.decline.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_refund_request_id': self.id},
        }

    def action_decline_with_reason(self, reason):
        """Actually decline with the provided reason."""
        for request in self:
            if request.state != 'pending':
                raise UserError(_('Only pending requests can be declined.'))

            request.write({
                'state': 'declined',
                'decline_reason': reason,
                'reviewed_at': datetime.now(),
                'reviewed_by': self.env.uid,
            })


class AppointmentRefundDeclineWizard(models.TransientModel):
    _name = 'appointment.refund.decline.wizard'
    _description = 'Decline Refund Request Wizard'

    refund_request_id = fields.Many2one('appointment.refund.request', string='Refund Request', required=True)
    decline_reason = fields.Text('Reason for Declining', required=True)

    def action_confirm_decline(self):
        """Confirm the decline with reason."""
        self.refund_request_id.action_decline_with_reason(self.decline_reason)
        return {'type': 'ir.actions.act_window_close'}
