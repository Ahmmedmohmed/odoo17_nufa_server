# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class WalletTransferRequest(models.Model):
    _name = 'wallet.transfer.request'
    _description = 'Wallet to Bank Transfer Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'sequence'

    sequence = fields.Char('Request #', default=lambda self: _('New'), required=True, readonly=True, copy=False)

    # Customer info
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, ondelete='cascade', index=True)

    # Transfer amounts
    transfer_amount = fields.Float('Transfer Amount', required=True, help='Amount to transfer from wallet to bank')
    wallet_balance_at_request = fields.Float('Wallet Balance (At Request)',
                                             help='Customer wallet balance when request was made')

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    # Bank details
    bank_name = fields.Char('Bank Name', required=True)
    account_holder_name = fields.Char('Account Holder Name', required=True)
    account_number = fields.Char('Account Number / IBAN', required=True)
    swift_code = fields.Char('SWIFT/BIC Code')

    # Request details
    reason = fields.Text('Customer Notes', help='Any notes provided by customer')

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
    decline_reason = fields.Text('Decline Reason', help='Reason for declining the transfer request')

    # Transaction reference after transfer is done
    bank_transfer_reference = fields.Char('Bank Transfer Reference',
                                          help='Reference number from bank after transfer is completed')

    # Timestamps
    requested_at = fields.Datetime('Requested At', default=fields.Datetime.now, readonly=True)
    reviewed_at = fields.Datetime('Reviewed At', readonly=True)
    completed_at = fields.Datetime('Completed At', readonly=True)

    # Reviewed by
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', readonly=True)

    # Related transactions
    wallet_transaction_id = fields.Many2one('wallet.transaction', string='Wallet Transaction', readonly=True)

    # حقل جديد لربط القيد المحاسبي بالطلب
    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, copy=False)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('wallet.transfer.request.sequence') or _('New')

        # Store wallet balance at time of request
        if vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            vals['wallet_balance_at_request'] = partner.wallet_balance

        return super(WalletTransferRequest, self).create(vals)

    def action_approve(self):
        """Approve the transfer request and deduct from wallet."""
        for request in self:
            if request.state != 'pending':
                raise UserError(_('Only pending requests can be approved.'))

            # Check current wallet balance
            current_balance = request.partner_id.wallet_balance
            if current_balance < request.transfer_amount:
                raise UserError(_(
                    'Insufficient wallet balance. Customer has %.2f but requested %.2f transfer.'
                ) % (current_balance, request.transfer_amount))

            # Deduct from wallet
            transaction = request.partner_id.sudo().deduct_wallet_balance(
                amount=request.transfer_amount,
                source_type='other',
                source_description='Bank transfer request %s' % request.sequence,
                notes='Transfer to bank account: %s' % request.account_number[-4:] if request.account_number else '',
            )

            request.write({
                'state': 'approved',
                'reviewed_at': datetime.now(),
                'reviewed_by': self.env.uid,
                'wallet_transaction_id': transaction.id if transaction else False,
            })

            _logger.info("Wallet transfer approved: %s for partner %s, amount: %.2f",
                         request.sequence, request.partner_id.id, request.transfer_amount)

    def action_mark_processing(self):
        """Mark as processing (admin is processing bank transfer)."""
        for request in self:
            if request.state != 'approved':
                raise UserError(_('Only approved requests can be marked as processing.'))

            request.write({
                'state': 'processing',
            })

    def action_mark_completed(self):
        """Mark transfer as completed after bank transfer is done."""
        return {
            'name': _('Complete Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'wallet.transfer.complete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transfer_request_id': self.id},
        }

    def action_complete_with_reference(self, bank_reference, journal_id, wallet_account_id):
        """Actually complete with the bank transfer reference and generate Journal Entry."""
        for request in self:
            if request.state not in ('approved', 'processing'):
                raise UserError(_('Only approved or processing requests can be marked as completed.'))

            # --- التوجيه المحاسبي (Accounting Entry) ---
            if not journal_id.default_account_id:
                raise UserError(_('The selected Bank Journal does not have a default account configured.'))

            move_vals = {
                'journal_id': journal_id.id,
                'date': fields.Date.context_today(self),
                'ref': f"{request.sequence} - {bank_reference}",
                'move_type': 'entry',
                'line_ids': [
                    # الطرف المدين: تقليل التزام المحفظة
                    (0, 0, {
                        'name': _('Wallet Transfer Deduction: %s') % request.sequence,
                        'partner_id': request.partner_id.id,
                        'account_id': wallet_account_id.id,
                        'debit': request.transfer_amount,
                        'credit': 0.0,
                    }),
                    # الطرف الدائن: خروج النقدية من البنك
                    (0, 0, {
                        'name': _('Bank Transfer to Customer: %s') % request.sequence,
                        'partner_id': request.partner_id.id,
                        'account_id': journal_id.default_account_id.id,
                        'debit': 0.0,
                        'credit': request.transfer_amount,
                    }),
                ]
            }

            # إنشاء واعتماد القيد المحاسبي
            move = self.env['account.move'].sudo().create(move_vals)
            move.action_post()

            request.write({
                'state': 'completed',
                'completed_at': datetime.now(),
                'bank_transfer_reference': bank_reference,
                'move_id': move.id,  # ربط القيد بالطلب لسهولة الوصول إليه من الشاشة
            })

            _logger.info("Wallet transfer completed: %s, bank ref: %s, Journal Entry: %s",
                         request.sequence, bank_reference, move.name)

    def action_decline(self):
        """Decline the transfer request - opens wizard for reason."""
        return {
            'name': _('Decline Transfer Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'wallet.transfer.decline.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_transfer_request_id': self.id},
        }

    def action_decline_with_reason(self, reason):
        """Actually decline with the provided reason. Refund wallet if already deducted."""
        for request in self:
            if request.state in ('completed', 'declined'):
                raise UserError(_('Cannot decline completed or already declined requests.'))

            if request.state in ('pending', 'approved', 'processing'):
                if request.transfer_amount > 0:
                    request.partner_id.sudo().add_wallet_credit(
                        amount=request.transfer_amount,
                        source_type='refund',
                        source_description=_('Refund for declined transfer request %s') % request.sequence,
                        notes=_('Reason: %s') % (reason if reason else _('No reason provided')),
                    )
                    _logger.info("Wallet refunded for declined transfer: %s, amount: %.2f",
                                 request.sequence, request.transfer_amount)

            request.write({
                'state': 'declined',
                'decline_reason': reason,
                'completed_at': datetime.now(),
                'reviewed_by': self.env.uid,
            })
        return True


class WalletTransferDeclineWizard(models.TransientModel):
    _name = 'wallet.transfer.decline.wizard'
    _description = 'Decline Transfer Request Wizard'

    transfer_request_id = fields.Many2one('wallet.transfer.request', string='Transfer Request', required=True)
    decline_reason = fields.Text('Reason for Declining', required=True)
    will_refund = fields.Boolean('Will Refund Wallet', compute='_compute_will_refund')

    @api.depends('transfer_request_id')
    def _compute_will_refund(self):
        for wizard in self:
            wizard.will_refund = wizard.transfer_request_id.state in ('approved', 'processing')

    def action_confirm_decline(self):
        """Confirm the decline with reason."""
        self.transfer_request_id.action_decline_with_reason(self.decline_reason)
        return {'type': 'ir.actions.act_window_close'}


class WalletTransferCompleteWizard(models.TransientModel):
    _name = 'wallet.transfer.complete.wizard'
    _description = 'Complete Transfer Request Wizard'

    transfer_request_id = fields.Many2one('wallet.transfer.request', string='Transfer Request', required=True)
    bank_transfer_reference = fields.Char('Bank Transfer Reference', required=True,
                                          help='Enter the reference number from the bank transfer')

    # الحقول المحاسبية الجديدة
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        domain=[('type', 'in', ('bank', 'cash'))],
        required=True,
        help="The bank/cash journal used to transfer the money to the customer."
    )
    wallet_account_id = fields.Many2one(
        'account.account',
        string='Wallet Liability Account',
        required=True,
        help="The account representing the company's liability for customer wallets (Debit)."
    )

    def action_confirm_complete(self):
        """Confirm completion with bank reference and generate accounting entry."""
        self.transfer_request_id.action_complete_with_reference(
            self.bank_transfer_reference,
            self.journal_id,
            self.wallet_account_id
        )
        return {'type': 'ir.actions.act_window_close'}