# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WalletTransaction(models.Model):
    _name = 'wallet.transaction'
    _description = 'Wallet Transaction'
    _order = 'create_date desc'
    _rec_name = 'reference'

    reference = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
        ondelete='cascade'
    )
    transaction_type = fields.Selection([
        ('credit', 'Credit (Added)'),
        ('debit', 'Debit (Used)')
    ], string='Transaction Type', required=True, index=True)

    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    # Source tracking fields
    source_type = fields.Selection([
        ('manual', 'Manual Adjustment'),
        ('refund', 'Order Refund'),
        ('cashback', 'Cashback'),
        ('topup', 'Wallet Top-up'),
        ('gift', 'Gift/Voucher'),
        ('loyalty', 'Loyalty Points Conversion'),
        ('promotion', 'Promotional Credit'),
        ('order_payment', 'Order Payment'),
        ('service_payment', 'Service Payment'),
        ('appointment_payment', 'Appointment Payment'),
        ('other', 'Other')
    ], string='Source Type', required=True, default='manual')

    source_description = fields.Char(
        string='Source Description',
        help='Description of where the funds came from or were used'
    )

    # Related records for traceability
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Related Sale Order'
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string='Related POS Order'
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Related Invoice'
    )
    payment_id = fields.Many2one(
        'account.payment',
        string='Related Payment'
    )

    # Balance tracking
    balance_before = fields.Monetary(
        string='Balance Before',
        currency_field='currency_id',
        readonly=True
    )
    balance_after = fields.Monetary(
        string='Balance After',
        currency_field='currency_id',
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='State', default='draft', required=True)

    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', _('New')) == _('New'):
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'wallet.transaction') or _('New')

            # Calculate balance before and after
            if vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                vals['balance_before'] = partner.wallet_balance

                amount = vals.get('amount', 0)
                if vals.get('transaction_type') == 'credit':
                    vals['balance_after'] = vals['balance_before'] + amount
                else:
                    vals['balance_after'] = vals['balance_before'] - amount

        return super().create(vals_list)

    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirmed'
                # Invalidate partner's wallet balance cache
                record.partner_id.invalidate_recordset(['wallet_balance'])

    def action_cancel(self):
        for record in self:
            if record.state == 'confirmed':
                # Create a reversal transaction
                reversal_type = 'debit' if record.transaction_type == 'credit' else 'credit'
                self.create({
                    'partner_id': record.partner_id.id,
                    'transaction_type': reversal_type,
                    'amount': record.amount,
                    'source_type': 'manual',
                    'source_description': f'Reversal of {record.reference}',
                    'notes': f'Automatic reversal of cancelled transaction {record.reference}',
                    'state': 'confirmed'
                })
            record.state = 'cancelled'
