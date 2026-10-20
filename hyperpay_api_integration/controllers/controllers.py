# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import json
import logging
import uuid
import jwt
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)

# =================================================================
# --- TEST CREDENTIALS (بيانات التست - كتعليق للرجوع إليها مستقبلاً) ---
# HYPERPAY_BASE_URL = "https://eu-test.oppwa.com"
# ACCESS_TOKEN = "OGFjN2E0Yzg5MTRhYTY5ZTAxOTE0YWFlYThlNDAwMGV8Snp3c1p0WWd3ajdkbnlYbg=="
# ENTITY_ID_VISA = "8ac7a4c8914aa69e01914aaf64770012"
# ENTITY_ID_MADA = "8ac7a4c8914aa69e01914aaff3430016"
# ENTITY_ID_APPLEPAY = "8ac7a4c79acb07ad019ad42a476d0590"
# =================================================================

# --- LIVE CREDENTIALS (بيانات اللايف بناءً على الإيميل) ---
HYPERPAY_BASE_URL = "https://eu-prod.oppwa.com"
ACCESS_TOKEN = "OGFjOWE0ZGE5ZDk2NTY0YzAxOWRhNTIzYWRiODExODB8OUw3Yj9VK0BRRG82TVF5ek0lRmQ="

# حسب الإيميل: Entity ID (Visa, MasterCard, MADA) متوحدين في نفس الكود
ENTITY_ID_VISA = "8ac9a4ce9d965529019da52d8b8c32f2"
ENTITY_ID_MADA = "8ac9a4ce9d965529019da52d8b8c32f2"

# 🚀 تم تحديث الـ Entity ID الخاص بـ Apple Pay للحساب الحقيقي (LIVE)
ENTITY_ID_APPLEPAY = "8ac9a4ce9d965529019da52d8b8c32f2"

META_TOKEN = "EAFuId4IjxeEBQSFeQD7RJdJFRUFuv6BT6XWDvbCgTORukY4OZCuDmquZChtRlC6N2EFmBQKvzG84fHsbqvaa657a85gfAHoLkKqvzQrEBDHMZC8PMZC5ISPQ9bdoDFkOmENXbLzecsYZBkaAkXezEPFFlQrNJiB8877i9Jfoe6ZAE5zZAnVZAIHkbYNcy3z6wdVOhwZDZD"
PHONE_NUMBER_ID = "926541170542819"
META_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"


def _partner_from_token():
    auth_header = request.httprequest.headers.get('Authorization')
    if not auth_header:
        return None, "Missing Authorization token"
    token = auth_header.split(" ")[-1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        partner_id = payload.get("partner_id")
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return None, "Partner not found"
        return partner, None
    except Exception as e:
        return None, str(e)


class HyperPayAPIController(http.Controller):

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

            # 🔥 [تطبيق الولاء وترجمة رسائل الخطأ من أساس أودو]
            import re
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
                # 🚀 التعديل هنا: التراجع عن المعاملة لتجنب كسر قاعدة البيانات
                request.env.cr.rollback()

                error_msg = str(e)
                if 'A minimum of' in error_msg:
                    match = re.search(r'A minimum of ([\d\.]+) (.*?) should be purchased', error_msg)
                    if match and is_ar:
                        error_msg = f"يجب أن يكون إجمالي الطلب {match.group(1)} {match.group(2)} على الأقل لتطبيق الخصم"
                else:
                    error_msg = f"خطأ في تطبيق الخصم: {error_msg}" if is_ar else error_msg

                return request.make_response(json.dumps({'status': 'error', 'message': error_msg}), headers=headers,
                                             status=400)

            # ... [باقي الكود الخاص بالـ HyperPay كما هو بدون تغيير] ...
            if method_req == 'MADA':
                entity_id = ENTITY_ID_MADA
            elif method_req in ('APPLEPAY', 'APPLE_PAY'):
                entity_id = ENTITY_ID_APPLEPAY
            else:
                entity_id = ENTITY_ID_VISA

            merchant_txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
            full_name = partner.name or 'Customer'
            name_parts = full_name.split(' ', 1)
            given_name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else 'Surname'

            payload = {
                'entityId': entity_id,
                'amount': f"{order.amount_total:.2f}",
                'currency': 'SAR',
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

            hp_headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
            import requests
            response = requests.post(f"{HYPERPAY_BASE_URL}/v1/checkouts", data=payload, headers=hp_headers)
            res_json = response.json()

            if response.status_code != 200 or not res_json.get('id'):
                msg = 'فشل في تهيئة الدفع' if is_ar else 'HyperPay Init Failed'
                return request.make_response(json.dumps({'status': 'error', 'message': msg, 'details': res_json}),
                                             headers=headers, status=400)

            provider = request.env['payment.provider'].sudo().search([('code', '=', 'hyperpay')], limit=1)
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

        except Exception as e:
            # 🚀 التعديل هنا: التراجع عن المعاملة لتجنب كسر قاعدة البيانات
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
        _logger.info("🌐 EXACT URL HIT: %s", request.httprequest.url)
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

            # --- تحديد الـ Entity ID بناءً على الطريقة أو المسار ---
            method_code = (tx.payment_method_code or 'VISA').upper()
            _logger.info("DEBUG: Method Code is %s | Path is %s", method_code, resource_path)

            if 'applepay' in resource_path.lower() or method_code == 'APPLEPAY':
                entity_id = ENTITY_ID_APPLEPAY
            elif 'mada' in resource_path.lower() or method_code == 'MADA':
                entity_id = ENTITY_ID_MADA
            else:
                entity_id = ENTITY_ID_VISA

            # 4. استعلام التحقق من HyperPay API
            verify_url = f"{HYPERPAY_BASE_URL}{resource_path}?entityId={entity_id}"
            hp_headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}

            _logger.info("🔗 Sending VERIFY request to HyperPay: %s", verify_url)

            response = requests.get(verify_url, headers=hp_headers)
            res_json = response.json()

            _logger.info("📥 HYPERPAY VERIFY RESPONSE: %s", res_json)

            # 5. تحليل النتيجة
            result_code = res_json.get('result', {}).get('code', '')
            description = res_json.get('result', {}).get('description', '')

            success = result_code.startswith(('000.000.', '000.100.')) or result_code in ['000.000.000', '000.100.110']

            if success:
                _logger.info("✅ Payment Successful. Proceeding with Odoo validation for TX: %s", tx.reference)
                if tx.state != 'done':
                    tx._set_done()

                order = tx.sale_order_ids[0]
                order_company = order.company_id
                order_sudo = order.sudo().with_company(order_company)

                if order_sudo.state in ['draft', 'sent']:
                    order_sudo.action_confirm()

                if order_sudo.invoice_status != 'invoiced':
                    order_sudo.with_context(default_company_id=order_company.id)._create_invoices()

                invoice = order_sudo.invoice_ids.filtered(lambda i: i.state != 'cancel')[:1]
                if invoice and invoice.state == 'draft':
                    invoice.with_company(order_company).action_post()

                if invoice and invoice.state == 'posted':
                    journal = request.env['account.journal'].sudo().search([
                        ('type', '=', 'bank'), ('company_id', '=', order_company.id)
                    ], limit=1)
                    if journal:
                        payment = request.env['account.payment'].sudo().with_company(order_company).create({
                            'payment_type': 'inbound',
                            'partner_type': 'customer',
                            'partner_id': order_sudo.partner_id.id,
                            'amount': invoice.amount_total,
                            'journal_id': journal.id,
                            'ref': tx.reference,
                        })
                        payment.action_post()
                        (invoice + payment.move_id).line_ids.filtered(
                            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                        ).reconcile()

                appointment = request.env['appointment.management'].sudo().search([
                    ('partner_id', '=', order_sudo.partner_id.id),
                    ('state', '=', '1')
                ], limit=1)
                if appointment:
                    appointment.write({'state': '2'})

                self._send_payment_whatsapp_message(
                    name=order_sudo.partner_id.name,
                    phone=order_sudo.partner_id.mobile or order_sudo.partner_id.phone,
                    order_id=order.id,
                    amount=str(invoice.amount_total if invoice else order_sudo.amount_total)
                )

                raw_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
                base_url = raw_url.strip('/')
                invoice_url = f"{base_url}/appointment/pos-user/invoice/{order.id}"

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
                if order:
                    reward_lines = order.sudo().order_line.filtered(lambda l: l.is_reward_line or l.reward_id)
                    if reward_lines:
                        reward_lines.unlink()  # مسح سطور المكافأة
                        order.sudo()._update_programs_and_rewards()  # إعادة حساب إجمالي الفاتورة
                        _logger.info("♻️ Loyalty rewards removed from order %s due to payment failure.", order.id)

                if tx.state != 'error':
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

    # --- بداية دوال الموقع (مستقلة وبدون تشفيت) ---

    def _get_hyperpay_entity_id(self, method, resource_path=""):
        method = (method or 'VISA').upper()
        if 'mada' in resource_path.lower() or method == 'MADA':
            return ENTITY_ID_MADA
        return ENTITY_ID_VISA

    @http.route('/shop/payment/hyperpay/pay/<int:order_id>', type='http', auth='public', csrf=False, multilang=False)
    def hyperpay_web_pay(self, order_id, **kwargs):
        try:
            order = request.env['sale.order'].sudo().browse(order_id)
            if not order.exists():
                return request.redirect('/shop')

            merchant_txn_id = f"WEB-{uuid.uuid4().hex[:12].upper()}"
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url').strip('/')

            partner = order.partner_id
            full_name = partner.name or 'Customer'
            name_parts = full_name.split(' ', 1)
            given_name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else 'Surname'

            payload = {
                'entityId': ENTITY_ID_VISA,
                'amount': f"{order.amount_total:.2f}",
                'currency': 'SAR',
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

            headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
            response = requests.post(f"{HYPERPAY_BASE_URL}/v1/checkouts", data=payload, headers=headers)
            res_json = response.json()

            if response.status_code != 200 or not res_json.get('id'):
                _logger.error("HyperPay API Error: %s", res_json)
                return request.make_response(f"API ERROR: {res_json}", headers=[('Content-Type', 'text/plain')])

            checkout_id = res_json['id']

            provider = request.env['payment.provider'].sudo().search([('code', '=', 'hyperpay')], limit=1)
            pm = request.env['payment.method'].sudo().search([('code', '=', 'visa')], limit=1) or provider.payment_method_ids[:1]

            tx = request.env['payment.transaction'].sudo().create({
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

            script_url = f"{HYPERPAY_BASE_URL}/v1/paymentWidgets.js?checkoutId={checkout_id}"
            html = f"""
                    <!DOCTYPE html>
                    <html>
                        <head><meta charset="utf-8"><script src="{script_url}"></script></head>
                        <body style="text-align:center; padding-top:100px; font-family: sans-serif; background: #f9f9f9;">
                            <h3>جاري تحميل صفحة الدفع للطلب {order.name}...</h3>
                            <div style="max-width: 500px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                                <form action="{base_url}/api/hyperpay/verify_web" class="paymentWidgets" data-brands="VISA MASTER MADA"></form>
                            </div>
                        </body>
                    </html>"""

            return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

        except Exception as e:
            _logger.exception("HyperPay Critical Pay Error: %s", e)
            return request.make_response(f"Critical System Error: {str(e)}", headers=[('Content-Type', 'text/plain')])

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

            # --- التعديل الجوهري لمنع خلط السيرفرات في الويب ---
            method_code = getattr(tx, 'payment_method_code', 'VISA') or 'VISA'
            if method_code.upper() == 'MADA':
                entity_id = ENTITY_ID_MADA
            elif method_code.upper() in ('APPLEPAY', 'APPLE_PAY'):
                entity_id = ENTITY_ID_APPLEPAY
            else:
                entity_id = ENTITY_ID_VISA

            # الاعتماد الكلي على روابط اللايف والتوكن الموحد أعلى الملف
            verify_url = f"{HYPERPAY_BASE_URL}{resource_path}?entityId={entity_id}"
            _logger.info("HYPERPAY verify_web: calling url=%s entity_id=%s", verify_url, entity_id)

            res = requests.get(verify_url, headers={'Authorization': f'Bearer {ACCESS_TOKEN}'}).json()

            _logger.info("HYPERPAY FULL VERIFY RESPONSE: %s", res)

            result_code = res.get('result', {}).get('code', '')
            description = res.get('result', {}).get('description', '')
            _logger.info("HYPERPAY CODE: %s | DESC: %s", result_code, description)

            success = result_code.startswith(('000.000.', '000.100.')) or result_code in ['000.000.000', '000.100.110']

            if success:
                if tx.state != 'done':
                    tx._set_done()

                order = tx.sale_order_ids[0]
                order_company = order.company_id
                order_sudo = order.sudo().with_company(order_company)

                if order_sudo.state in ['draft', 'sent']:
                    order_sudo.action_confirm()

                if order_sudo.invoice_status != 'invoiced':
                    order_sudo.with_context(default_company_id=order_company.id)._create_invoices()

                invoice = order_sudo.invoice_ids.filtered(lambda i: i.state != 'cancel')[:1]
                if invoice and invoice.state == 'draft':
                    invoice.with_company(order_company).action_post()

                if invoice and invoice.state == 'posted':
                    journal = request.env['account.journal'].sudo().search([
                        ('type', '=', 'bank'), ('company_id', '=', order_company.id)
                    ], limit=1)
                    if journal:
                        payment = request.env['account.payment'].sudo().with_company(order_company).create({
                            'payment_type': 'inbound',
                            'partner_type': 'customer',
                            'partner_id': order_sudo.partner_id.id,
                            'amount': invoice.amount_total,
                            'journal_id': journal.id,
                            'ref': tx.reference,
                        })
                        payment.action_post()
                        (invoice + payment.move_id).line_ids.filtered(
                            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                        ).reconcile()

                appointment = request.env['appointment.management'].sudo().search([
                    ('partner_id', '=', order_sudo.partner_id.id),
                    ('state', '=', '1')
                ], limit=1)
                if appointment:
                    appointment.write({'state': '2'})

                self._send_payment_whatsapp_message(
                    name=order_sudo.partner_id.name,
                    phone=order_sudo.partner_id.mobile or order_sudo.partner_id.phone,
                    order_id=order.id,
                    amount=str(invoice.amount_total if invoice else order_sudo.amount_total)
                )

                request.env.cr.commit()
                return request.redirect('/shop/confirmation')

            else:
                if tx.state != 'error':
                    tx._set_error(description)
                request.env.cr.commit()

                # 🚀 التعديل الجديد: شاشة عرض الخطأ للعميل بدلاً من التوجيه الصامت
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
                            <div class="error-msg">{description}</div>
                            <p>برجاء المحاولة مرة أخرى باستخدام بطاقة مختلفة، أو التواصل مع خدمة العملاء.</p>
                            <a href="/shop/cart" class="btn">العودة للسلة</a>
                        </div>
                    </body>
                    </html>
                    """
                return request.make_response(error_html, headers=[('Content-Type', 'text/html; charset=utf-8')])

        except Exception as e:
            _logger.exception("HYPERPAY verify_web critical error: %s", e)
            # عرض شاشة خطأ في حالة حدوث مشكلة برمجية
            error_html = f"""
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

            if not order_id:
                _logger.error("HyperPay Redirect: No order ID found in request or session.")
                return request.redirect('/shop')

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url').strip('/')
            redirect_url = f"{base_url}/shop/payment/hyperpay/pay/{order_id}"

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
        if not phone: return False
        try:
            phone = ''.join(filter(str.isdigit, str(phone)))
            if not phone.startswith('966'): phone = '966' + phone.lstrip('0')
            payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "template",
                "template": {
                    "name": "order_sucess",
                    "language": {"code": "en_US"},
                    "components": [{"type": "body", "parameters": [
                        {"type": "text", "text": name},
                        {"type": "text", "text": str(order_id)},
                        {"type": "text", "text": amount}
                    ]}]
                }
            }
            requests.post(META_URL, json=payload, headers={"Authorization": f"Bearer {META_TOKEN}"})
            return True
        except Exception as e:
            _logger.error("WhatsApp Error: %s", e)
            return False