# -*- coding: utf-8 -*-
from odoo import api, models, fields, Command


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

    @api.model
    def _hyperpay_setup_companies(self, companies):
        """Make sure each company in `companies` has a HyperPay provider.

        New providers are created *disabled*: the admin must fill the
        credentials of that company's HyperPay account, then enable it.
        Payment methods / icons are copied from an existing HyperPay provider.
        """
        redirect_form = self.env.ref(
            'hyperpay_api_integration.redirect_form', raise_if_not_found=False)
        icons = self.env['payment.icon'].search([
            '|', '|',
            ('name', 'ilike', 'visa'),
            ('name', 'ilike', 'master'),
            ('name', 'ilike', 'mada'),
        ])
        for company in companies:
            provider = self.search([
                ('code', '=', 'hyperpay'),
                ('company_id', '=', company.id),
            ], limit=1)
            if provider:
                continue
            template = self.search([
                ('code', '=', 'hyperpay'),
                ('company_id', '!=', company.id),
            ], limit=1)
            vals = {
                'name': 'HyperPay',
                'code': 'hyperpay',
                'state': 'disabled',
                'company_id': company.id,
            }
            if 'is_published' in self._fields:
                vals['is_published'] = True
            provider = self.create(vals)
            if redirect_form:
                provider.redirect_form_view_id = redirect_form.id
            provider.payment_icon_ids = [Command.set(icons.ids)]
            if template and template.payment_method_ids:
                provider.payment_method_ids = [Command.set(template.payment_method_ids.ids)]


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