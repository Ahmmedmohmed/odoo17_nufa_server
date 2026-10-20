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
        """تجهيز وتفعيل بوابة هايبر باي تلقائياً لجميع الفروع ببيانات الربط الموحدة"""
        redirect_form = self.env.ref(
            'hyperpay_api_integration.redirect_form', raise_if_not_found=False)

        # 🚀 بيانات الربط الموحدة لجميع الفروع
        hyperpay_credentials = {
            'state': 'test',  # اجعلها 'enabled' عندما ترغب في تشغيل الدفع الحقيقي
            'hyperpay_access_token': 'OGFjOWE0ZGE5ZDk2NTY0YzAxOWRhNTIzYWRiODExODB8OUw3Yj9VK0BRRG82TVF5ek0lRmQ=',
            'hyperpay_entity_id_visa': '8ac9a4ce9d965529019da52d8b8c32f2',
            'hyperpay_entity_id_mada': '8ac9a4ce9d965529019da52d8b8c32f2',
            'hyperpay_entity_id_applepay': '8ac9a4ce9d965529019da52d8b8c32f2',
        }

        for company in companies:
            provider = self.search([
                ('code', '=', 'hyperpay'),
                ('company_id', '=', company.id),
            ], limit=1)

            if provider:
                # تحديث وتفعيل البوابة للفروع الموجودة مسبقاً إذا تم استدعاء الدالة
                provider.write(hyperpay_credentials)
                if 'is_published' in self._fields:
                    provider.write({'is_published': True})
                continue

            template = self.search([
                ('code', '=', 'hyperpay'),
                ('company_id', '!=', company.id),
            ], limit=1)

            vals = {
                'name': 'HyperPay',
                'code': 'hyperpay',
                'company_id': company.id,
            }
            vals.update(hyperpay_credentials)  # دمج البيانات

            if 'is_published' in self._fields:
                vals['is_published'] = True

            new_provider = self.create(vals)
            if redirect_form:
                new_provider.redirect_form_view_id = redirect_form.id

            # تم حذف كود payment.icon لأنه غير مدعوم في أودو 17

            if template and template.payment_method_ids:
                new_provider.payment_method_ids = [Command.set(template.payment_method_ids.ids)]


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