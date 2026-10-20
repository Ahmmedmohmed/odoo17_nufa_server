# -*- coding: utf-8 -*-
import json
import logging
import re
import uuid

import jwt
import requests
from markupsafe import escape

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# =================================================================
# لا توجد أي بيانات حساسة في الكود بعد الآن:
#   * بيانات HyperPay (Access Token / Entity IDs) -> من الـ payment.provider
#     الخاص بشركة الأوردر (Invoicing > Configuration > Payment Providers).
#   * بيانات واتساب (Meta) و JWT -> من System Parameters:
#       hyperpay_api_integration.meta_token
#       hyperpay_api_integration.meta_phone_number_id
#       hyperpay_api_integration.jwt_secret        (+ jwt_algorithm، الافتراضي HS256)
# =================================================================

HP_URL_PROD = "https://eu-prod.oppwa.com"
HP_URL_TEST = "https://eu-test.oppwa.com"
PARAM = 'hyperpay_api_integration.'
HTTP_TIMEOUT = 60


class HyperPayConfigError(Exception):
    """Provider missing / credentials not configured for the order's company."""


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _hp_get_provider(company):
    """HyperPay provider of THIS company (never another company's one)."""
    return request.env['payment.provider'].sudo().search([
        ('code', '=', 'hyperpay'),
        ('company_id', '=', company.id),
        ('state', '!=', 'disabled'),
    ], limit=1)


def _hp_config(provider, method='VISA', resource_path=''):
    """Return (base_url, access_token, entity_id) taken from the provider."""
    if not provider:
        raise HyperPayConfigError("No enabled HyperPay provider for this company")

    method = (method or 'VISA').upper()
    path = (resource_path or '').lower()
    if method in ('APPLEPAY', 'APPLE_PAY') or 'applepay' in path:
        entity_id = provider.hyperpay_entity_id_applepay
    elif method == 'MADA' or 'mada' in path:
        entity_id = provider.hyperpay_entity_id_mada
    else:
        entity_id = None
    entity_id = entity_id or provider.hyperpay_entity_id_visa  # fallback

    token = provider.hyperpay_access_token
    if not token or not entity_id:
        raise HyperPayConfigError(
            "HyperPay credentials are not configured for company '%s'" % provider.company_id.name)

    base_url = HP_URL_TEST if provider.state == 'test' else HP_URL_PROD
    return base_url, token, entity_id


def _hp_site_url(order=None):
    """Public URL of the website the order belongs to (multi-website safe).
    Falls back to web.base.url."""
    url = ''
    if order and 'website_id' in order._fields and order.website_id:
        url = order.website_id.get_base_url()
    if not url:
        url = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    return url.rstrip('/')


def _partner_from_token():
    auth_header = request.httprequest.headers.get('Authorization')
    if not auth_header:
        return None, "Missing Authorization token"
    token = auth_header.split(" ")[-1]
    icp = request.env['ir.config_parameter'].sudo()
    secret = icp.get_param(PARAM + 'jwt_secret')
    try:
        if secret:
            algorithm = icp.get_param(PARAM + 'jwt_algorithm') or 'HS256'
            payload = jwt.decode(token, secret, algorithms=[algorithm])
        else:
            _logger.warning(
                "HyperPay: JWT signature is NOT verified. Set the system parameter "
                "'%sjwt_secret' to enable verification.", PARAM)
            payload = jwt.decode(token, options={"verify_signature": False})
        partner_id = payload.get("partner_id")
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return None, "Partner not found"
        return partner, None
    except Exception as e:
        return None, str(e)


class HyperPayAPIController(http.Controller):

    # ------------------------------------------------------------
    # Shared logic
    # ------------------------------------------------------------
    @staticmethod
    def _hp_partner_owns_order(partner, order):
        return order.partner_id.commercial_partner_id == partner.commercial_partner_id

    @staticmethod
    def _hp_web_can_pay(order):
        """The visitor must be the owner of this cart / order."""
        if order.id in (request.session.get('sale_order_id'),
                        request.session.get('sale_last_order_id')):
            return True
        user = request.env.user
        return (not user._is_public()
                and order.partner_id.commercial_partner_id == user.partner_id.commercial_partner_id)

    def _hp_check_payment(self, tx, resource_path):
        """Ask HyperPay for the payment status. Returns (success, code, description)."""
        method = tx.hyperpay_payment_method or tx.payment_method_code or 'VISA'
        base_url, token, entity_id = _hp_config(tx.provider_id, method, resource_path)

        verify_url = f"{base_url}{resource_path}?entityId={entity_id}"
        _logger.info("HYPERPAY verify: GET %s (provider company: %s)", verify_url, tx.provider_id.company_id.name)
        response = requests.get(verify_url, headers={'Authorization': f'Bearer {token}'}, timeout=HTTP_TIMEOUT)
        res_json = response.json()
        _logger.info("HYPERPAY verify response: %s", res_json)

        result = res_json.get('result', {})
        result_code = result.get('code', '')
        description = result.get('description', '')
        success = result_code.startswith(('000.000.', '000.100.'))

        if success:
            # الدفع لازم يطابق مبلغ وعملة المعاملة
            try:
                paid_amount = float(res_json.get('amount', tx.amount))
            except (TypeError, ValueError):
                paid_amount = tx.amount
            paid_currency = res_json.get('currency') or tx.currency_id.name
            if abs(paid_amount - tx.amount) > 0.005 or paid_currency != tx.currency_id.name:
                _logger.error(
                    "HYPERPAY amount/currency mismatch on TX %s: paid %s %s, expected %s %s. MANUAL REVIEW NEEDED.",
                    tx.reference, paid_amount, paid_currency, tx.amount, tx.currency_id.name)
                return False, 'AMOUNT_MISMATCH', 'Paid amount/currency does not match the order'
        return success, result_code, description

    def _hp_finalize_order(self, tx, notify=True):
        """Confirm order, invoice, register payment. Every step is idempotent
        (safe if the customer refreshes the return page)."""
        order = tx.sale_order_ids[0]
        order_company = order.company_id
        order_sudo = order.sudo().with_company(order_company)

        if order_sudo.state in ('draft', 'sent'):
            order_sudo.action_confirm()

        if order_sudo.invoice_status != 'invoiced':
            order_sudo.with_context(default_company_id=order_company.id)._create_invoices()

        invoice = order_sudo.invoice_ids.filtered(lambda i: i.state != 'cancel')[:1]
        if invoice and invoice.state == 'draft':
            invoice.with_company(order_company).action_post()

        if invoice and invoice.state == 'posted' and invoice.payment_state not in ('paid', 'in_payment'):
            provider = tx.provider_id.sudo()
            journal = provider.journal_id if 'journal_id' in provider._fields else False
            if not journal:
                journal = request.env['account.journal'].sudo().search([
                    ('type', '=', 'bank'), ('company_id', '=', order_company.id)
                ], limit=1)
            if journal:
                payment = request.env['account.payment'].sudo().with_company(order_company).create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': order_sudo.partner_id.id,
                    'amount': invoice.amount_total,
                    'currency_id': invoice.currency_id.id,
                    'journal_id': journal.id,
                    'ref': tx.reference,
                })
                payment.action_post()
                (invoice + payment.move_id).line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                ).reconcile()
            else:
                _logger.warning(
                    "HyperPay: no bank journal for company %s, payment NOT registered for invoice %s",
                    order_company.name, invoice.name)

        # الموديول ده اختياري (مش في depends)
        if 'appointment.management' in request.env:
            Appointment = request.env['appointment.management'].sudo()
            domain = [('partner_id', '=', order_sudo.partner_id.id), ('state', '=', '1')]
            if 'company_id' in Appointment._fields:
                domain.append(('company_id', '=', order_company.id))
            appointment = Appointment.search(domain, limit=1)
            if appointment:
                appointment.write({'state': '2'})

        if notify:
            self._send_payment_whatsapp_message(
                name=order_sudo.partner_id.name,
                phone=order_sudo.partner_id.mobile or order_sudo.partner_id.phone,
                order_id=order.id,
                amount=str(invoice.amount_total if invoice else order_sudo.amount_total)
            )
        return invoice

    # ------------------------------------------------------------
    # Mobile API
    # ------------------------------------------------------------
    @http.route(['/api/hyperpay/init', '/api/hyperpay/init/'], type='http', auth='public',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def init_payment(self, **kw):
        method = request.httprequest.method

        # 🚀 قراءة اللغة من الموبايل لترجمة الأخطاء
        is_ar = request.httprequest.headers.get('lang', 'en').lower() in ['ar', 'ar_001']

        _logger.info("🚀 === [HYPERPAY INIT] INCOMING REQUEST FROM MOBILE ===")

        headers = [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*'),
                   ('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')]

        if method == 'OPTIONS':
            return request.make_response("", headers=headers, status=200)
        if method == 'GET':
            msg = 'غير مسموح بطلب GET. يرجى استخدام POST.' if is_ar else 'Method GET not allowed. Please use POST.'
            return request.make_response(json.dumps({'status': 'error', 'message': msg}), headers=headers, status=405)

        raw_data = request.httprequest.data
        try:
            partner, err = _partner_from_token()
            if err:
                return request.make_response(json.dumps({'status': 'error', 'message': err}), headers=headers,
                                             status=401)

            try:
                data = json.loads(raw_data.decode('utf-8') or '{}')
            except Exception:
                data = kw

            order_id = data.get('order_id')
            method_req = (data.get('payment_method') or 'VISA').upper()
            loyalty_code = data.get('code') or data.get('coupon_code')
            reward_id = data.get('reward_id')

            if not order_id:
                msg = 'رقم الطلب مفقود' if is_ar else 'Missing required field: order_id'
                return request.make_response(json.dumps({'status': 'error', 'message': msg}), headers=headers,
                                             status=400)

            order = request.env['sale.order'].sudo().browse(int(order_id))
            if not order.exists():
                msg = 'الطلب غير موجود' if is_ar else 'Order not found'
                return request.make_response(json.dumps({'status': 'error', 'message': msg}), headers=headers,
                                             status=404)

            # 🔒 العميل لازم يكون صاحب الأوردر
            if not self._hp_partner_owns_order(partner, order):
                msg = 'غير مصرح لك بالدفع لهذا الطلب' if is_ar else 'You are not allowed to pay for this order'
                return request.make_response(json.dumps({'status': 'error', 'message': msg}), headers=headers,
                                             status=403)

            # 🏢 provider + credentials الخاصين بشركة الأوردر (قبل ما نعدل أي حاجة في الأوردر)
            provider = _hp_get_provider(order.company_id)
            base_url, access_token, entity_id = _hp_config(provider, method_req)

            # 🔥 [تطبيق الولاء وترجمة رسائل الخطأ من أساس أودو]
            try:
                order.sudo()._update_programs_and_rewards()

                if loyalty_code:
                    status = order.sudo()._try_apply_code(loyalty_code)
                    if isinstance(status, dict) and (status.get('error') or status.get('not_found')):
                        error_msg = status.get('error', 'الكود غير صالح أو منتهي' if is_ar else 'Invalid code')

                        # 🚀 ترجمة رسالة الحد الأدنى بذكاء
                        if 'A minimum of' in error_msg:
                            match = re.search(r'A minimum of ([\d\.]+) (.*?) should be purchased', error_msg)
                            if match and is_ar:
                                error_msg = f"يجب أن يكون إجمالي الطلب {match.group(1)} {match.group(2)} على الأقل لتطبيق الخصم"

                        return request.make_response(json.dumps({'status': 'error', 'message': error_msg}),
                                                     headers=headers, status=400)

                    order.sudo()._update_programs_and_rewards()
                    claimable_rewards = order.sudo()._get_claimable_rewards()
                    for coupon, rewards in claimable_rewards.items():
                        valid_codes = [c for c in [coupon.code] + coupon.program_id.rule_ids.mapped('code') if c]
                        if loyalty_code in valid_codes:
                            for reward in rewards:
                                order.sudo()._apply_program_reward(reward, coupon)

                if reward_id:
                    reward = request.env['loyalty.reward'].sudo().browse(int(reward_id))
                    if reward.exists():
                        order.sudo()._apply_program_reward(reward, reward.program_id)
                    else:
                        msg = 'المكافأة غير موجودة' if is_ar else 'Reward ID not found'
                        return request.make_response(json.dumps({'status': 'error', 'message': msg}), headers=headers,
                                                     status=400)

                order.sudo()._update_programs_and_rewards()

            except Exception as e:
                # 🚀 التراجع عن المعاملة لتجنب كسر قاعدة البيانات
                request.env.cr.rollback()

                error_msg = str(e)
                if 'A minimum of' in error_msg:
                    match = re.search(r'A minimum of ([\d\.]+) (.*?) should be purchased', error_msg)
                    if match and is_ar:
                        error_msg = f"يجب أن يكون إجمالي الطلب {match.group(1)} {match.group(2)} على الأقل لتطبيق الخصم"
                else:
                    error_msg = f"خطأ في تطبيق الخصم: {error_msg}" if is_ar else error_msg

                return request.make_response(json.dumps({'status': 'error', 'message': error_msg}),
                                             headers=headers, status=400)

            merchant_txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
            full_name = partner.name or 'Customer'
            name_parts = full_name.split(' ', 1)
            given_name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else 'Surname'

            payload = {
                'entityId': entity_id,
                'amount': f"{order.amount_total:.2f}",
                'currency': order.currency_id.name,  # عملة الأوردر (مش SAR ثابتة)
                'paymentType': 'DB',
                'merchantTransactionId': merchant_txn_id,
                'customer.email': partner.email or '',
                'customer.givenName': given_name,
                'customer.surname': surname,
                'billing.street1': partner.street or 'Street Address',
                'billing.city': partner.city or 'City',
                'billing.state': partner.state_id.name or (partner.state_id.code or 'State'),
                'billing.country': partner.country_id.code or 'SA',
                'billing.postcode': partner.zip or '12345',
                'integrity': 'true',
            }

            hp_headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.post(f"{base_url}/v1/checkouts", data=payload, headers=hp_headers,
                                     timeout=HTTP_TIMEOUT)
            res_json = response.json()

            if response.status_code != 200 or not res_json.get('id'):
                msg = 'فشل في تهيئة الدفع' if is_ar else 'HyperPay Init Failed'
                return request.make_response(json.dumps({'status': 'error', 'message': msg, 'details': res_json}),
                                             headers=headers, status=400)

            method_code = 'mastercard' if method_req.lower() == 'master' else method_req.lower()
            payment_method_rec = request.env['payment.method'].sudo().search([('code', '=', method_code)], limit=1)
            if not payment_method_rec:
                payment_method_rec = provider.payment_method_ids[:1]

            tx = request.env['payment.transaction'].sudo().create({
                'amount': order.amount_total,
                'currency_id': order.currency_id.id,
                'provider_id': provider.id,
                'payment_method_id': payment_method_rec.id,
                'partner_id': partner.id,
                'reference': merchant_txn_id,
                'checkout_id': res_json.get('id'),
                'payment_method_code': method_req,
                'hyperpay_payment_method': method_req,
                'sale_order_ids': [(4, order.id)],
            })

            brands_list = res_json.get('brands', [method_req])
            return request.make_response(json.dumps({
                'status': 'success',
                'checkout_id': res_json['id'],
                'transaction_id': tx.id,
                'payment_brand': method_req,
                'brands': brands_list
            }), headers=headers, status=200)

        except HyperPayConfigError as e:
            _logger.error("❌ HyperPay config error in Init Payment: %s", e)
            return request.make_response(json.dumps({'status': 'error', 'message': str(e)}),
                                         headers=headers, status=500)
        except Exception as e:
            # 🚀 التراجع عن المعاملة لتجنب كسر قاعدة البيانات
            request.env.cr.rollback()

            _logger.exception("❌ CRITICAL EXCEPTION in Init Payment: %s", e)
            msg = 'حدث خطأ داخلي في الخادم' if is_ar else 'Internal Server Error'
            return request.make_response(json.dumps({'status': 'error', 'message': msg, 'details': str(e)}),
                                         headers=headers, status=500)

    @http.route(['/api/hyperpay/verify', '/api/hyperpay/verify/'], type='http', auth='public',
                methods=['GET', 'POST', 'OPTIONS'], csrf=False)
    def verify_payment(self, **kw):
        method = request.httprequest.method
        headers = [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*'),
                   ('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')]

        _logger.info("🚀 === [HYPERPAY VERIFY] INCOMING REQUEST ===")
        _logger.info("🛠 HTTP METHOD: %s", method)

        if method == 'OPTIONS':
            return request.make_response("", headers=headers, status=200)

        raw_data = request.httprequest.data
        _logger.info("📦 RAW DATA: %s | KW: %s", raw_data, kw)

        try:
            # 1. استخراج البيانات من الطلب
            if raw_data:
                try:
                    data = json.loads(raw_data.decode('utf-8'))
                except Exception:
                    data = kw
            else:
                data = kw

            resource_path = data.get('resourcePath') or data.get('resource_path')

            if not resource_path:
                _logger.error("❌ Missing resourcePath in payload. Payload received: %s", data)
                return request.make_response(json.dumps({'status': 'error', 'message': 'Missing resourcePath'}),
                                             headers=headers, status=400)

            # 2. استخراج الـ Checkout ID
            checkout_id = resource_path.split('/checkouts/')[-1].split('/payment')[0]
            tx = request.env['payment.transaction'].sudo().search([('checkout_id', '=', checkout_id)], limit=1)

            if not tx:
                _logger.error("❌ Transaction not found in Odoo for checkout_id: %s", checkout_id)
                return request.make_response(json.dumps({'status': 'error', 'message': 'Transaction not found'}),
                                             headers=headers, status=404)

            # 3. استعلام HyperPay (بـ credentials الـ provider الخاص بالمعاملة)
            success, result_code, description = self._hp_check_payment(tx, resource_path)

            if success:
                _logger.info("✅ Payment Successful. Proceeding with Odoo validation for TX: %s", tx.reference)
                first_time = tx.state != 'done'
                if first_time:
                    tx._set_done()

                invoice = self._hp_finalize_order(tx, notify=first_time)
                order = tx.sale_order_ids[0]

                invoice_url = f"{_hp_site_url(order)}/appointment/pos-user/invoice/{order.id}"

                return request.make_response(json.dumps({
                    'status': 'success',
                    'order_id': order.id,
                    'invoice_url': invoice_url
                }), headers=headers, status=200)

            else:
                _logger.warning("❌ HyperPay Payment Rejected! TX %s | Desc: %s | Code: %s", tx.reference, description,
                                result_code)

                # 🔥 [تعديل الولاء]: لو الدفع فشل، نمسح سطور الخصم عشان العميل ما يخسرش الكوبون
                order = tx.sale_order_ids[0] if tx.sale_order_ids else False
                if order and tx.state != 'done':
                    reward_lines = order.sudo().order_line.filtered(lambda l: l.is_reward_line or l.reward_id)
                    if reward_lines:
                        reward_lines.unlink()  # مسح سطور المكافأة
                        order.sudo()._update_programs_and_rewards()  # إعادة حساب إجمالي الفاتورة
                        _logger.info("♻️ Loyalty rewards removed from order %s due to payment failure.", order.id)

                if tx.state not in ('error', 'done'):
                    tx._set_error(description)

                return request.make_response(json.dumps({
                    'status': 'fail',
                    'message': description,
                    'result_code': result_code
                }), headers=headers, status=400)

        except Exception as e:
            _logger.exception("❌ CRITICAL Error in verify_payment: %s", e)
            return request.make_response(json.dumps({'status': 'error', 'message': str(e)}), headers=headers,
                                         status=500)

    # --- دوال الموقع ---

    @http.route('/shop/payment/hyperpay/pay/<int:order_id>', type='http', auth='public', csrf=False, multilang=False)
    def hyperpay_web_pay(self, order_id, **kwargs):
        try:
            order = request.env['sale.order'].sudo().browse(order_id)
            if not order.exists():
                return request.redirect('/shop')

            # 🔒 الزائر لازم يكون صاحب الأوردر (الكارت اللي في الـ session أو العميل المسجل)
            if not self._hp_web_can_pay(order):
                _logger.warning("HyperPay web pay: access denied to order %s", order_id)
                return request.redirect('/shop/cart')

            # 🏢 provider + credentials شركة الأوردر
            provider = _hp_get_provider(order.company_id)
            base_url, access_token, entity_id = _hp_config(provider, 'VISA')

            merchant_txn_id = f"WEB-{uuid.uuid4().hex[:12].upper()}"
            site_url = _hp_site_url(order)

            partner = order.partner_id
            full_name = partner.name or 'Customer'
            name_parts = full_name.split(' ', 1)
            given_name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else 'Surname'

            payload = {
                'entityId': entity_id,
                'amount': f"{order.amount_total:.2f}",
                'currency': order.currency_id.name,  # عملة الأوردر (مش SAR ثابتة)
                'paymentType': 'DB',
                'merchantTransactionId': merchant_txn_id,
                'customer.email': partner.email or 'customer@noufbeauty.net',
                'customer.givenName': given_name,
                'customer.surname': surname,
                'billing.street1': partner.street or 'Street Address',
                'billing.city': partner.city or 'Riyadh',
                'billing.state': partner.state_id.name or (partner.state_id.code or 'Riyadh'),
                'billing.country': partner.country_id.code or 'SA',
                'billing.postcode': partner.zip or '12345',
                'integrity': 'true',
            }

            response = requests.post(f"{base_url}/v1/checkouts", data=payload,
                                     headers={'Authorization': f'Bearer {access_token}'}, timeout=HTTP_TIMEOUT)
            res_json = response.json()

            if response.status_code != 200 or not res_json.get('id'):
                _logger.error("HyperPay API Error: %s", res_json)
                return request.make_response("Payment initialization failed. Please contact support.",
                                             headers=[('Content-Type', 'text/plain')])

            checkout_id = res_json['id']

            pm = request.env['payment.method'].sudo().search([('code', '=', 'visa')], limit=1) \
                or provider.payment_method_ids[:1]

            request.env['payment.transaction'].sudo().create({
                'amount': order.amount_total,
                'currency_id': order.currency_id.id,
                'provider_id': provider.id,
                'payment_method_id': pm.id if pm else False,
                'partner_id': order.partner_id.id,
                'reference': merchant_txn_id,
                'checkout_id': checkout_id,
                'sale_order_ids': [(4, order.id)],
                'state': 'draft',
                'operation': 'online_direct',
            })
            request.env.cr.commit()

            script_url = f"{base_url}/v1/paymentWidgets.js?checkoutId={checkout_id}"
            html = f"""
                    <!DOCTYPE html>
                    <html>
                        <head><meta charset="utf-8"><script src="{script_url}"></script></head>
                        <body style="text-align:center; padding-top:100px; font-family: sans-serif; background: #f9f9f9;">
                            <h3>جاري تحميل صفحة الدفع للطلب {escape(order.name)}...</h3>
                            <div style="max-width: 500px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                                <form action="{site_url}/api/hyperpay/verify_web" class="paymentWidgets" data-brands="VISA MASTER MADA"></form>
                            </div>
                        </body>
                    </html>"""

            return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

        except HyperPayConfigError as e:
            _logger.error("HyperPay config error (web pay): %s", e)
            return request.make_response(
                "HyperPay is not configured for this company. Please contact support.",
                headers=[('Content-Type', 'text/plain')])
        except Exception as e:
            _logger.exception("HyperPay Critical Pay Error: %s", e)
            return request.make_response("Critical System Error. Please contact support.",
                                         headers=[('Content-Type', 'text/plain')])

    @http.route('/api/hyperpay/verify_web', type='http', auth='public', methods=['GET', 'POST'], csrf=False,
                multilang=False)
    def verify_payment_web(self, **kw):
        try:
            resource_path = kw.get('resourcePath') or kw.get('resource_path')
            if not resource_path:
                _logger.error("HYPERPAY verify_web: missing resourcePath, params=%s", kw)
                return request.redirect('/shop?payment=failed')

            checkout_id = resource_path.split('/checkouts/')[-1].split('/payment')[0]
            _logger.info("HYPERPAY verify_web: checkout_id=%s", checkout_id)

            tx = request.env['payment.transaction'].sudo().search([('checkout_id', '=', checkout_id)], limit=1)

            if not tx:
                _logger.error("HYPERPAY verify_web: TX not found for checkout_id=%s", checkout_id)
                return request.redirect('/shop?payment=failed')

            success, result_code, description = self._hp_check_payment(tx, resource_path)
            _logger.info("HYPERPAY CODE: %s | DESC: %s", result_code, description)

            if success:
                first_time = tx.state != 'done'
                if first_time:
                    tx._set_done()

                self._hp_finalize_order(tx, notify=first_time)

                request.env.cr.commit()
                return request.redirect('/shop/confirmation')

            else:
                if tx.state not in ('error', 'done'):
                    tx._set_error(description)
                request.env.cr.commit()

                # 🚀 شاشة عرض الخطأ للعميل بدلاً من التوجيه الصامت
                error_html = f"""
                    <!DOCTYPE html>
                    <html lang="ar" dir="rtl">
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <title>فشل عملية الدفع</title>
                        <style>
                            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 10% 20px; background: #f4f7f6; }}
                            .container {{ max-width: 450px; margin: auto; background: white; padding: 40px 30px; border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.08); border-top: 6px solid #e74c3c; }}
                            h2 {{ color: #e74c3c; margin-bottom: 10px; }}
                            .icon {{ font-size: 50px; margin-bottom: 15px; }}
                            p {{ font-size: 16px; color: #555; line-height: 1.5; }}
                            .error-msg {{ background: #fdeded; color: #e74c3c; padding: 10px; border-radius: 6px; font-weight: bold; margin: 20px 0; font-size: 14px; direction: ltr; }}
                            .btn {{ display: inline-block; margin-top: 15px; padding: 12px 25px; background: #2c3e50; color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold; transition: 0.3s; }}
                            .btn:hover {{ background: #1a252f; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="icon">❌</div>
                            <h2>عذراً، فشلت عملية الدفع</h2>
                            <p>لم نتمكن من إتمام عملية الدفع الخاصة بك. يرجى مراجعة السبب أدناه:</p>
                            <div class="error-msg">{escape(description)}</div>
                            <p>برجاء المحاولة مرة أخرى باستخدام بطاقة مختلفة، أو التواصل مع خدمة العملاء.</p>
                            <a href="/shop/cart" class="btn">العودة للسلة</a>
                        </div>
                    </body>
                    </html>
                    """
                return request.make_response(error_html, headers=[('Content-Type', 'text/html; charset=utf-8')])

        except Exception as e:
            _logger.exception("HYPERPAY verify_web critical error: %s", e)
            error_html = """
                <!DOCTYPE html>
                <html lang="ar" dir="rtl">
                <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>خطأ بالنظام</title></head>
                <body style="text-align: center; padding: 50px; font-family: sans-serif;">
                    <h2 style="color: #e74c3c;">❌ حدث خطأ غير متوقع</h2>
                    <p>برجاء المحاولة لاحقاً أو التواصل مع الدعم الفني.</p>
                    <a href="/shop/cart" style="padding: 10px 20px; background: #333; color: #fff; text-decoration: none; border-radius: 5px;">العودة للمتجر</a>
                </body>
                </html>
                """
            return request.make_response(error_html, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/payment/hyperpay/redirect', type='http', auth='public', website=True, csrf=False)
    def hyperpay_redirect(self, **kw):
        try:
            order_id = kw.get('order_id') or kw.get('sale_order_id')
            if not order_id:
                order_id = request.session.get('sale_last_order_id')

            try:
                order_id = int(order_id)
            except (TypeError, ValueError):
                _logger.error("HyperPay Redirect: No valid order ID found in request or session.")
                return request.redirect('/shop')

            order = request.env['sale.order'].sudo().browse(order_id)
            redirect_url = f"{_hp_site_url(order if order.exists() else None)}/shop/payment/hyperpay/pay/{order_id}"

            _logger.info("HyperPay Redirecting Order %s to %s", order_id, redirect_url)

            return f"""
                    <!DOCTYPE html>
                    <html>
                        <head>
                            <title>Redirecting to Payment...</title>
                        </head>
                        <body onload="document.getElementById('o_payment_redirect_form').submit()">
                            <div style="text-align: center; margin-top: 50px;">
                                <h2>جاري تحويلك لصفحة الدفع، برجاء الانتظار...</h2>
                            </div>
                            <form id="o_payment_redirect_form" action="{redirect_url}" method="GET">
                            </form>
                        </body>
                    </html>
                """
        except Exception as e:
            _logger.error("HyperPay Redirect Error: %s", str(e))
            return request.redirect('/shop')

    def _send_payment_whatsapp_message(self, name, phone, order_id, amount):
        if not phone:
            return False
        try:
            icp = request.env['ir.config_parameter'].sudo()
            meta_token = icp.get_param(PARAM + 'meta_token')
            phone_number_id = icp.get_param(PARAM + 'meta_phone_number_id')
            if not meta_token or not phone_number_id:
                _logger.warning("HyperPay WhatsApp: system parameters '%smeta_token' / '%smeta_phone_number_id' "
                                "are not set, message skipped.", PARAM, PARAM)
                return False

            phone = ''.join(filter(str.isdigit, str(phone)))
            if not phone.startswith('966'):
                phone = '966' + phone.lstrip('0')

            # 🚀 تم إضافة الـ Button Component هنا لإرسال رابط الفاتورة
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "template",
                "template": {
                    "name": "order_sucess",
                    "language": {"code": "en_US"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": name},
                                {"type": "text", "text": str(order_id)},
                                {"type": "text", "text": amount}
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0",
                            "parameters": [
                                {"type": "text", "text": str(order_id)}
                            ]
                        }
                    ]
                }
            }
            meta_url = f"https://graph.facebook.com/v24.0/{phone_number_id}/messages"
            res = requests.post(meta_url, json=payload, headers={"Authorization": f"Bearer {meta_token}"},
                                timeout=30)
            if res.status_code >= 400:
                _logger.error("WhatsApp API error %s: %s", res.status_code, res.text)
                return False
            return True
        except Exception as e:
            _logger.error("WhatsApp Error: %s", e)
            return False