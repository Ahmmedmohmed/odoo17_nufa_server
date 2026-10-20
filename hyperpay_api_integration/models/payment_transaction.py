# -*- coding: utf-8 -*-
from odoo import models, fields


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('hyperpay', 'HyperPay')],
        ondelete={'hyperpay': 'set default'}
    )

    hyperpay_access_token = fields.Char(
        string="Access Token",
        groups='base.group_system'
    )
    hyperpay_entity_id_visa = fields.Char(string="Entity ID (Visa/Master)")
    hyperpay_entity_id_mada = fields.Char(string="Entity ID (Mada)")
    hyperpay_entity_id_applepay = fields.Char(string="Entity ID (Apple Pay)")


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    checkout_id = fields.Char(
        string='HyperPay Checkout ID',
        readonly=True
    )
    hyperpay_payment_method = fields.Char(
        string='HyperPay Method (Visa/Mada/ApplePay)'
    )

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find transaction from HyperPay webhook/redirect data"""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'hyperpay' or len(tx) == 1:
            return tx

        reference = notification_data.get('merchantTransactionId')
        if reference:
            tx = self.search([
                ('reference', '=', reference),
                ('provider_code', '=', 'hyperpay')
            ])
        return tx