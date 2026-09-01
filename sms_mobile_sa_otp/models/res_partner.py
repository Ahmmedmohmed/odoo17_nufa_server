from odoo import models, fields, api, _
import random
from datetime import datetime, timedelta
import logging

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    password = fields.Char()
    otp_code = fields.Char(string="OTP Code")
    otp_expiration = fields.Datetime(string="OTP Expiration")
    otp_sent = fields.Boolean(string="OTP Sent", default=False)
    fcm_token = fields.Char()
    long = fields.Char()
    late = fields.Char()

    refresh_token = fields.Char(string="Refresh Token")
    refresh_token_expiration = fields.Datetime(string="Refresh Token Expiration")

    birthday = fields.Date(string="Birthday")
    marriage_date = fields.Date(string="Marriage Date")
    verify = fields.Boolean(string="Verified", default=False, help="True when the user verifies OTP successfully.")
    exist = fields.Boolean(default=False)

    # Wallet fields
    wallet_balance = fields.Monetary(
        string='Wallet Balance',
        compute='_compute_wallet_balance',
        currency_field='currency_id',
        store=False,
        help='Current wallet balance computed from confirmed transactions'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Link to loyalty card for default Odoo eWallet UI
    ewallet_card_id = fields.Many2one(
        'loyalty.card',
        string='eWallet Card',
        help='Link to the loyalty card used for eWallet balance display in Odoo UI'
    )

    @api.depends_context('force_company')
    def _compute_wallet_balance(self):
        """Compute wallet balance from confirmed wallet transactions."""
        for partner in self:
            try:
                # Check if wallet.transaction model/table exists
                if 'wallet.transaction' not in self.env:
                    partner.wallet_balance = 0.0
                    continue

                WalletTransaction = self.env['wallet.transaction'].sudo()

                # Use SQL to check if table exists and get balance in one query
                self.env.cr.execute("""
                    SELECT
                        COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) -
                        COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as balance
                    FROM wallet_transaction
                    WHERE partner_id = %s AND state = 'confirmed'
                """, (partner.id,))
                result = self.env.cr.fetchone()
                partner.wallet_balance = result[0] if result else 0.0
            except Exception:
                # Table doesn't exist yet (before module upgrade)
                partner.wallet_balance = 0.0

    def _get_or_create_ewallet_card(self):
        """
        Get or create the loyalty card (eWallet) for this partner.
        This enables the wallet balance to appear in Odoo's default eWallet UI.
        """
        self.ensure_one()
        if self.ewallet_card_id:
            return self.ewallet_card_id

        # Get the eWallet program
        program = self.env.ref('sms_mobile_sa_otp.customer_ewallet_program', raise_if_not_found=False)
        if not program:
            _logger.warning('eWallet program not found. Please install/upgrade the module.')
            return False

        # Create loyalty card for this partner
        card = self.env['loyalty.card'].sudo().create({
            'program_id': program.id,
            'partner_id': self.id,
            'points': self.wallet_balance,  # Initialize with current balance
        })
        self.ewallet_card_id = card
        _logger.info(f'Created eWallet card {card.code} for partner {self.name} with balance {self.wallet_balance}')
        return card

    def _sync_ewallet_card_balance(self, amount, transaction_type):
        """
        Sync the loyalty card balance with the wallet transaction.
        This keeps the Odoo default eWallet UI in sync.
        """
        self.ensure_one()
        card = self._get_or_create_ewallet_card()
        if not card:
            return

        if transaction_type == 'credit':
            card.sudo().write({'points': card.points + amount})
        else:  # debit
            card.sudo().write({'points': max(0, card.points - amount)})

    def add_wallet_credit(self, amount, source_type='manual', source_description=None,
                          sale_order_id=None, pos_order_id=None, invoice_id=None, notes=None):
        """
        Add credit (money) to partner's wallet.
        Returns the created wallet transaction.
        Also syncs with the loyalty.card for Odoo default eWallet UI.
        """
        self.ensure_one()
        WalletTransaction = self.env['wallet.transaction'].sudo()
        transaction = WalletTransaction.create({
            'partner_id': self.id,
            'transaction_type': 'credit',
            'amount': amount,
            'source_type': source_type,
            'source_description': source_description or f'Credit added: {source_type}',
            'sale_order_id': sale_order_id,
            'pos_order_id': pos_order_id,
            'invoice_id': invoice_id,
            'notes': notes,
            'state': 'confirmed'
        })

        # Sync with loyalty card for Odoo default eWallet UI
        self._sync_ewallet_card_balance(amount, 'credit')

        return transaction

    def deduct_wallet_balance(self, amount, source_type='order_payment', source_description=None,
                              sale_order_id=None, pos_order_id=None, invoice_id=None, notes=None):
        """
        Deduct amount from partner's wallet for payment.
        Returns the created wallet transaction or raises error if insufficient balance.
        Also syncs with the loyalty.card for Odoo default eWallet UI.
        """
        self.ensure_one()
        if self.wallet_balance < amount:
            raise ValidationError(_('Insufficient wallet balance. Available: %s, Required: %s') % (
                self.wallet_balance, amount
            ))

        WalletTransaction = self.env['wallet.transaction'].sudo()
        transaction = WalletTransaction.create({
            'partner_id': self.id,
            'transaction_type': 'debit',
            'amount': amount,
            'source_type': source_type,
            'source_description': source_description or f'Payment: {source_type}',
            'sale_order_id': sale_order_id,
            'pos_order_id': pos_order_id,
            'invoice_id': invoice_id,
            'notes': notes,
            'state': 'confirmed'
        })

        # Sync with loyalty card for Odoo default eWallet UI
        self._sync_ewallet_card_balance(amount, 'debit')

        return transaction

    @api.constrains('phone', 'mobile', 'country_id')
    def _check_phone_length_by_country(self):
        for partner in self:
            country = partner.country_id
            if not country or not country.phone_length:
                continue

            for field_name, label in [('phone', _('Phone')), ('mobile', _('Mobile'))]:
                number = partner[field_name]
                if not number:
                    continue

                digits = ''.join(ch for ch in number if ch.isdigit())

                if len(digits) != country.phone_length:
                    raise ValidationError(_(
                        "%(field)s number must contain %(length)s digits for country %(country)s.",
                    ) % {
                                              'field': label,
                                              'length': country.phone_length,
                                              'country': country.name,
                                          })


class ResCountry(models.Model):
    _inherit = 'res.country'

    phone_length = fields.Integer(
        string='Phone Number Length',
        help='Required phone/mobile digits length for partners in this country.')
