# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
import jwt
import logging
import json
import requests
from odoo.tools.translate import _
from datetime import datetime

SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"
_logger = logging.getLogger(__name__)

# WhatsApp Meta API Configuration
META_TOKEN = "EAFuId4IjxeEBQSFeQD7RJdJFRUFuv6BT6XWDvbCgTORukY4OZCuDmquZChtRlC6N2EFmBQKvzG84fHsbqvaa657a85gfAHoLkKqvzQrEBDHMZC8PMZC5ISPQ9bdoDFkOmENXbLzecsYZBkaAkXezEPFFlQrNJiB8877i9Jfoe6ZAE5zZAnVZAIHkbYNcy3z6wdVOhwZDZD"
PHONE_NUMBER_ID = "926541170542819"
META_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"


def _json_ok(message="OK", data=None, status=200):
    return Response(json.dumps({
        "status": "success", "message": message, "data": data or {}
    }), status=status, content_type="application/json")


def _json_err(message, status=400, data=None, error_code=None):
    payload = {"status": "failed", "message": message, "data": data or {}}
    if error_code:
        payload["error_code"] = error_code
    return Response(json.dumps(payload), status=status, content_type="application/json")


def _partner_from_token():
    """Authenticate user from JWT Bearer token."""
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err("Authorization Bearer token is required", status=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner_id = payload.get("partner_id")
        if not partner_id:
            return None, _json_err("Invalid token payload", status=401)

        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("Partner not found", status=404)

        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json_err("Token has expired", status=401)
    except jwt.InvalidTokenError:
        return None, _json_err("Invalid token", status=401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err(str(e), status=400)


def _parse_body():
    raw = request.httprequest.data or b"{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise


def _check_wallet_table_exists():
    """Check if wallet_transaction table exists in database."""
    try:
        request.env.cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'wallet_transaction'
            )
        """)
        result = request.env.cr.fetchone()
        return result[0] if result else False
    except Exception:
        return False


def _send_payment_whatsapp_message(name, phone, order_id, amount):
    """Send WhatsApp message via Meta API after successful payment."""
    try:
        # Clean phone number (remove spaces, plus signs)
        phone = ''.join(filter(str.isdigit, str(phone)))

        headers = {
            "Authorization": f"Bearer {META_TOKEN}",
            "Content-Type": "application/json"
        }

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
                            {
                                "type": "text",
                                "text": str(order_id)
                            }
                        ]
                    }
                ],
            }
        }
        response = requests.post(META_URL, json=payload, headers=headers)
        _logger.info("WhatsApp Sent: %s", response.text)
        return response.json()
    except Exception as e:
        _logger.error("Failed to send WhatsApp: %s", str(e))
        return False


class WalletApiController(http.Controller):

    @http.route("/api/wallet/balance", type="http", auth="public", methods=["GET"], csrf=False)
    def get_wallet_balance(self, **kwargs):
        """
        Get customer's wallet balance.

        Headers:
            Authorization: Bearer <access_token>

        Response:
            {
                "status": "success",
                "message": "Wallet balance retrieved successfully",
                "data": {
                    "wallet_balance": 500.00,
                    "currency": "SAR",
                    "currency_symbol": "ر.س",
                    "partner_id": 123,
                    "partner_name": "John Doe"
                }
            }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # Check if wallet table exists
            if not _check_wallet_table_exists():
                return _json_err(
                    "Wallet module not fully installed. Please upgrade the module in Odoo.",
                    status=503,
                    error_code="MODULE_NOT_READY"
                )

            currency = partner.currency_id or request.env.company.currency_id

            return _json_ok(
                "Wallet balance retrieved successfully",
                data={
                    "wallet_balance": partner.wallet_balance,
                    "currency": currency.name,
                    "currency_symbol": currency.symbol,
                    "partner_id": partner.id,
                    "partner_name": partner.name
                }
            )

        except Exception as e:
            _logger.exception("Error fetching wallet balance: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/wallet/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_wallet_history(self, **kwargs):
        """
        Get customer's wallet transaction history with details of where funds were used/received.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # --- 1. استخراج اللغة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            odoo_lang = lang_map.get(raw_lang, 'en_US')

            # 🌐 تحديد إذا كانت اللغة عربية لترجمة النصوص الثابتة
            is_ar = raw_lang in ['ar', 'ar_001']

            # Check if wallet table exists
            if not _check_wallet_table_exists():
                return _json_err(
                    "تطبيق المحفظة غير مثبت بالكامل. يرجى تحديث التطبيق في أودو." if is_ar else "Wallet module not fully installed. Please upgrade the module in Odoo.",
                    status=503,
                    error_code="MODULE_NOT_READY"
                )

            # Parse query parameters
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))
            transaction_type = kwargs.get("transaction_type", "all")
            date_from = kwargs.get("date_from")
            date_to = kwargs.get("date_to")

            # Validate limit
            if limit > 100:
                limit = 100
            if limit < 1:
                limit = 50

            # Build domain
            domain = [
                ("partner_id", "=", partner.id),
                ("state", "=", "confirmed")
            ]

            if transaction_type in ["credit", "debit"]:
                domain.append(("transaction_type", "=", transaction_type))

            if date_from:
                domain.append(("create_date", ">=", date_from + " 00:00:00"))
            if date_to:
                domain.append(("create_date", "<=", date_to + " 23:59:59"))

            # --- 2. تمرير اللغة للموديل ---
            WalletTransaction = request.env["wallet.transaction"].sudo().with_context(lang=odoo_lang)

            # Get total count
            total_count = WalletTransaction.search_count(domain)

            # Get transactions with pagination
            transactions = WalletTransaction.search(
                domain,
                order="create_date desc",
                limit=limit,
                offset=offset
            )

            currency = partner.currency_id or request.env.company.currency_id

            # --- 3. استخراج القيم المترجمة لحقل source_type ---
            # استخدام fields_get يضمن تطبيق الترجمة بناءً على odoo_lang
            source_type_selection = dict(WalletTransaction.fields_get(['source_type'])['source_type']['selection'])

            # Build transaction list
            transaction_list = []
            for txn in transactions:
                # Build related order info
                related_order = None
                if txn.sale_order_id:
                    related_order = {
                        "id": txn.sale_order_id.id,
                        "name": txn.sale_order_id.name,
                        "type": "sale_order",
                        "amount_total": txn.sale_order_id.amount_total,
                        "state": txn.sale_order_id.state
                    }
                elif txn.pos_order_id:
                    related_order = {
                        "id": txn.pos_order_id.id,
                        "name": txn.pos_order_id.name or txn.pos_order_id.pos_reference,
                        "type": "pos_order",
                        "amount_total": txn.pos_order_id.amount_total,
                        "state": txn.pos_order_id.state
                    }
                elif txn.invoice_id:
                    related_order = {
                        "id": txn.invoice_id.id,
                        "name": txn.invoice_id.name,
                        "type": "invoice",
                        "amount_total": txn.invoice_id.amount_total,
                        "state": txn.invoice_id.state
                    }
                elif txn.payment_id:
                    related_order = {
                        "id": txn.payment_id.id,
                        "name": txn.payment_id.name,
                        "type": "payment",
                        "amount": txn.payment_id.amount,
                        "state": txn.payment_id.state
                    }

                # جلب النص المترجم للـ source_type
                source_type_display = source_type_selection.get(txn.source_type, txn.source_type)

                # 🚀 ترجمة نوع الحركة يدوياً لضمان قراءتها مع الـ API
                if txn.transaction_type == "credit":
                    type_display = "إيداع (إضافة)" if is_ar else "Credit (Added)"
                else:
                    type_display = "سحب (استخدام)" if is_ar else "Debit (Used)"

                transaction_list.append({
                    "id": txn.id,
                    "reference": txn.reference,
                    "transaction_type": txn.transaction_type,
                    "transaction_type_display": type_display,
                    "amount": txn.amount,
                    "currency": currency.name,
                    "source_type": txn.source_type,
                    "source_type_display": source_type_display,
                    "source_description": txn.source_description or "",
                    "balance_before": txn.balance_before,
                    "balance_after": txn.balance_after,
                    "date": str(txn.create_date)[:19] if txn.create_date else "",
                    "related_order": related_order,
                    "notes": txn.notes or ""
                })

            return _json_ok(
                "تم جلب سجل المحفظة بنجاح" if is_ar else "Wallet history retrieved successfully",
                data={
                    "current_balance": partner.wallet_balance,
                    "currency": currency.name,
                    "currency_symbol": currency.symbol,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "transactions": transaction_list
                }
            )

        except Exception as e:
            _logger.exception("Error fetching wallet history: %s", e)
            return _json_err(f"حدث خطأ أثناء جلب سجل المحفظة: {str(e)}" if is_ar else str(e), status=500)
    @http.route("/api/wallet/can-pay", type="http", auth="public", methods=["GET"], csrf=False)
    def check_wallet_payment(self, **kwargs):
        """
        Check if wallet balance is sufficient for a given order amount.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            if not _check_wallet_table_exists():
                return _json_err(
                    "Wallet module not fully installed. Please upgrade the module in Odoo.",
                    status=503,
                    error_code="MODULE_NOT_READY"
                )

            order_amount = kwargs.get("order_amount")
            order_id = kwargs.get("order_id")

            if order_id:
                sale_order = request.env["sale.order"].sudo().browse(int(order_id))
                if not sale_order.exists():
                    return _json_err("Sale order not found", status=404)
                if sale_order.partner_id.id != partner.id:
                    return _json_err("Order does not belong to this customer", status=403)

                # -----------------------------------------------------------
                # تحديث السعر هنا احتياطياً بالدالة الصحيحة لـ sale.order
                # -----------------------------------------------------------
                if hasattr(request.env, 'flush_all'):
                    request.env.flush_all()
                else:
                    request.env.cr.flush()

                if hasattr(sale_order, 'invalidate_recordset'):
                    sale_order.invalidate_recordset()
                else:
                    sale_order.invalidate_cache()

                fresh_order = request.env["sale.order"].sudo().browse(int(order_id))
                if hasattr(fresh_order, '_amount_all'):
                    fresh_order._amount_all()

                order_amount = fresh_order.amount_total
                # -----------------------------------------------------------

            elif order_amount:
                order_amount = float(order_amount)
            else:
                return _json_err("order_amount or order_id is required", status=400)

            wallet_balance = partner.wallet_balance
            can_pay = wallet_balance >= order_amount
            remaining_balance = wallet_balance - order_amount if can_pay else 0

            currency = partner.currency_id or request.env.company.currency_id

            return _json_ok(
                "Wallet payment check completed",
                data={
                    "can_pay_with_wallet": can_pay,
                    "wallet_balance": wallet_balance,
                    "order_amount": order_amount,
                    "remaining_balance": remaining_balance,
                    "amount_to_pay_from_wallet": min(wallet_balance, order_amount),
                    "amount_remaining_to_pay": max(0, order_amount - wallet_balance),
                    "currency": currency.name,
                    "currency_symbol": currency.symbol
                }
            )

        except ValueError:
            return _json_err("Invalid order_amount value", status=400)
        except Exception as e:
            _logger.exception("Error checking wallet payment: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/wallet/pay", type="http", auth="public", methods=["POST"], csrf=False)
    def pay_with_wallet(self, **kwargs):
        """
        Pay for an order using wallet balance with strict DB Savepoint for accurate amounts.
        """
        # --- استخراج لغة التطبيق للترجمة ---
        lang = request.httprequest.headers.get('lang', 'en').lower()
        is_ar = 'ar' in lang

        partner, err = _partner_from_token()
        if err:
            return err

        # 🚀 التريكة السحرية: استخراج بيئة Admin كاملة لكل الأوبجكتس
        sudo_env = request.env['res.partner'].sudo().env
        partner_sudo = partner.sudo()

        try:
            body = _parse_body()
        except json.JSONDecodeError:
            msg = "بيانات JSON غير صالحة" if is_ar else "Invalid JSON payload"
            return _json_err(msg, status=400)

        try:
            if not getattr(self, '_check_wallet_table_exists', lambda: True)():
                msg = "نظام المحفظة غير مثبت بالكامل." if is_ar else "Wallet module not fully installed."
                return _json_err(msg, status=503, error_code="MODULE_NOT_READY")

            order_id = body.get("order_id")
            confirm_order = body.get("confirm_order", True)

            loyalty_code = body.get("code") or body.get("coupon_code")
            reward_id = body.get("reward_id")

            if not order_id:
                msg = "رقم الطلب (order_id) مطلوب" if is_ar else "order_id is required"
                return _json_err(msg, status=400)

            # 🚀 جلب الأوردر بصلاحيات كاملة من الداتابيز
            sale_order = sudo_env["sale.order"].browse(int(order_id))

            if not sale_order.exists():
                msg = "الطلب غير موجود" if is_ar else "Order not found"
                return _json_err(msg, status=404)

            # 💡 حل مشكلة الـ 403: مقارنة الحساب الرئيسي بدل الفرعي
            if sale_order.partner_id.id != partner.id and sale_order.partner_id.commercial_partner_id.id != partner.commercial_partner_id.id:
                _logger.error(
                    f"Wallet API: Partner mismatch. Order Partner ID: {sale_order.partner_id.id}, Token Partner ID: {partner.id}")
                msg = "الطلب لا يخص حسابك أو ليس لديك صلاحية" if is_ar else "Order does not belong to your account or access denied"
                return _json_err(msg, status=403)

            # -------------------------------------------------------------------
            # 1. تطبيق الكوبونات وبرامج الولاء مبدئياً
            # -------------------------------------------------------------------
            sale_order._update_programs_and_rewards()

            if loyalty_code:
                try:
                    status = sale_order._try_apply_code(loyalty_code)
                    if isinstance(status, dict) and (status.get('error') or status.get('not_found')):
                        return _json_err(status.get('error', 'الكود غير صالح' if is_ar else 'Invalid code'), status=400)

                    sale_order._update_programs_and_rewards()
                    claimable = sale_order._get_claimable_rewards()
                    for coupon, rewards in claimable.items():
                        valid_codes = [c for c in [coupon.code] + coupon.program_id.rule_ids.mapped('code') if c]
                        if loyalty_code in valid_codes:
                            for reward in rewards:
                                sale_order._apply_program_reward(reward, coupon)
                except Exception as e:
                    msg = f"خطأ في الكوبون: {str(e)}" if is_ar else f"Coupon error: {str(e)}"
                    return _json_err(msg, status=400)

            if reward_id:
                reward = sudo_env['loyalty.reward'].browse(int(reward_id))
                if reward.exists():
                    if reward.reward_type == 'product' and reward.gift_product_id:
                        existing_line = sale_order.order_line.filtered(
                            lambda l: l.product_id.id == reward.gift_product_id.id and not getattr(l, 'is_reward_line',
                                                                                                   False)
                        )
                        if not existing_line:
                            sudo_env['sale.order.line'].create({
                                'order_id': sale_order.id,
                                'product_id': reward.gift_product_id.id,
                                'product_uom_qty': getattr(reward, 'gift_qty', 1.0),
                            })

                    sale_order._update_programs_and_rewards()
                    claimable = sale_order._get_claimable_rewards()
                    reward_applied = False
                    for coupon, rewards in claimable.items():
                        if reward.id in rewards.ids:
                            sale_order._apply_program_reward(reward, coupon)
                            reward_applied = True
                            break

                    if not reward_applied:
                        card = sudo_env['loyalty.card'].search([
                            ('partner_id', 'in', [partner.id, partner.commercial_partner_id.id]),
                            ('program_id', '=', reward.program_id.id)
                        ], limit=1)
                        if card:
                            sale_order._apply_program_reward(reward, card)

            # -------------------------------------------------------------------
            # 🚀 2. إنشاء نقطة حفظ (Savepoint) في الداتا بيز
            # -------------------------------------------------------------------
            sudo_env.cr.execute('SAVEPOINT wallet_tx')

            order_company = sale_order.company_id
            order_sudo = sale_order.with_company(order_company)

            # منع تعارض الشركات للمنتجات
            for line in order_sudo.order_line:
                if line.product_id.company_id and line.product_id.company_id != order_company:
                    line.product_id.write({'company_id': False})

            # -------------------------------------------------------------------
            # 🔄 3. تأكيد الأوردر وإنشاء الفاتورة (للحصول على السعر النهائي الإجباري)
            # -------------------------------------------------------------------
            if confirm_order and order_sudo.state in ['draft', 'sent']:
                order_sudo.action_confirm()

            invoice = None
            if order_sudo.invoice_status != 'invoiced':
                order_sudo.with_context(default_company_id=order_company.id)._create_invoices()

            invoice = order_sudo.invoice_ids.filtered(lambda i: i.state != 'cancel')[:1]

            # السعر النهائي القاطع لا مجال للخطأ فيه
            final_payment_amount = invoice.amount_total if invoice else order_sudo.amount_total

            # -------------------------------------------------------------------
            # 💰 4. فحص رصيد المحفظة مقابل السعر الحقيقي
            # -------------------------------------------------------------------
            wallet_balance_before = partner_sudo.wallet_balance
            if wallet_balance_before < final_payment_amount:
                sudo_env.cr.execute('ROLLBACK TO SAVEPOINT wallet_tx')
                msg = "رصيد المحفظة غير كافٍ" if is_ar else "Insufficient wallet balance"
                return _json_err(
                    msg,
                    status=400,
                    data={
                        "wallet_balance": wallet_balance_before,
                        "required_amount": final_payment_amount,
                        "shortfall": final_payment_amount - wallet_balance_before
                    },
                    error_code="INSUFFICIENT_BALANCE"
                )

            # -------------------------------------------------------------------
            # 5. الخصم من المحفظة والدفع (بما إن الرصيد يكفي)
            # -------------------------------------------------------------------
            transaction = partner_sudo.deduct_wallet_balance(
                amount=final_payment_amount,
                source_type='order_payment',
                source_description=f'Payment for order {order_sudo.name}',
                notes=f'Wallet payment for sale order {order_sudo.name}'
            )

            # نربط المعاملة بالأوردر يدوياً بصلاحيات الأدمن
            if transaction and hasattr(transaction, 'sale_order_id'):
                transaction.write({'sale_order_id': order_sudo.id})

            if invoice and invoice.state == 'draft':
                invoice.with_company(order_company).action_post()

            if invoice and invoice.state == 'posted':
                journal = sudo_env['account.journal'].search([
                    ('type', '=', 'bank'),
                    ('company_id', '=', order_company.id)
                ], limit=1)

                if journal:
                    payment_method_line = journal.inbound_payment_method_line_ids[:1]
                    payment_vals = {
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'partner_id': order_sudo.partner_id.id,
                        'amount': invoice.amount_total,
                        'journal_id': journal.id,
                        'payment_method_line_id': payment_method_line.id if payment_method_line else False,
                        'ref': transaction.reference if hasattr(transaction, 'reference') else 'Wallet Payment',
                        'company_id': order_company.id,
                    }
                    payment = sudo_env['account.payment'].with_company(order_company).create(payment_vals)
                    payment.action_post()

                    lines = (invoice + payment.move_id).line_ids.filtered(
                        lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                    )
                    if len(lines) > 1:
                        lines.reconcile()

            # المواعيد والواتساب
            Appointment = sudo_env['appointment.management'].with_company(order_company)
            price_value = invoice.invoice_line_ids[0].price_unit if invoice and invoice.invoice_line_ids else 0

            appointment = Appointment.search([
                ('partner_id', 'in', [order_sudo.partner_id.id, order_sudo.partner_id.commercial_partner_id.id]),
                ('state', '=', '1'),
                ('price_unit', '=', price_value),
            ], limit=1)

            if appointment:
                appointment.write({'state': '2'})

            base_url = sudo_env['ir.config_parameter'].get_param('web.base.url')
            invoice_url = f"{base_url.rstrip('/')}/appointment/pos-user/invoice/{order_sudo.id}" if base_url else ""

            customer_phone = order_sudo.partner_id.mobile or order_sudo.partner_id.phone
            wa_response = {}
            if customer_phone:
                try:
                    wa_response = getattr(self, '_send_payment_whatsapp_message', lambda **kw: {})(
                        name=order_sudo.partner_id.name,
                        phone=customer_phone,
                        order_id=order_sudo.id,
                        amount=str(final_payment_amount)
                    )
                except Exception as wa_e:
                    _logger.warning("WhatsApp message failed but payment succeeded: %s", wa_e)

            currency = partner_sudo.currency_id or sudo_env.company.currency_id

            # 🔥 الضربة القاضية: إجبار أودو إنه يعتمد كل الحسابات (Flush) كـ Admin قبل ما نرد على الموبايل
            sudo_env.flush_all()

            msg = "تم دفع الطلب بنجاح باستخدام المحفظة" if is_ar else "Order paid successfully with wallet"
            return _json_ok(
                msg,
                data={
                    "transaction_id": transaction.id if transaction else None,
                    "transaction_reference": transaction.reference if transaction and hasattr(transaction,
                                                                                              'reference') else None,
                    "amount_paid": final_payment_amount,
                    "wallet_balance_before": wallet_balance_before,
                    "wallet_balance_after": partner_sudo.wallet_balance,
                    "currency": currency.name if currency else '',
                    "order": {
                        "id": order_sudo.id,
                        "name": order_sudo.name,
                        "amount_total": order_sudo.amount_total,
                        "state": order_sudo.state
                    },
                    "invoice_url": invoice_url,
                    "whatsapp_response": wa_response
                }
            )

        except Exception as e:
            try:
                sudo_env.cr.execute('ROLLBACK TO SAVEPOINT wallet_tx')
            except:
                pass
            _logger.exception("Error processing wallet payment: %s", e)

            # 🔥 تنظيف رسالة الخطأ عشان التطبيق يقدر يقرأها لو كانت من Odoo Validation
            error_msg = str(e)
            if hasattr(e, 'name'):
                error_msg = e.name
            elif hasattr(e, 'args') and e.args:
                error_msg = e.args[0]

            final_msg = f"حدث خطأ أثناء الدفع: {error_msg}" if is_ar else f"Payment error: {error_msg}"
            return _json_err(final_msg, status=500)
    @http.route("/api/wallet/add-credit", type="http", auth="public", methods=["POST"], csrf=False)
    def add_wallet_credit(self, **kwargs):
        """
        Add credit to wallet (typically called after successful top-up payment).

        Headers:
            Authorization: Bearer <access_token>

        Request Body:
            {
                "amount": 100.00,
                "source_type": "topup",      // topup, refund, cashback, gift, promotion, etc.
                "source_description": "Wallet top-up via credit card",
                "payment_reference": "PAY-12345"  // Optional external payment reference
            }

        Response:
            {
                "status": "success",
                "message": "Wallet credited successfully",
                "data": {
                    "transaction_id": 789,
                    "transaction_reference": "WTX/2025/0456",
                    "amount_credited": 100.00,
                    "wallet_balance_before": 500.00,
                    "wallet_balance_after": 600.00,
                    "currency": "SAR"
                }
            }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)

        try:
            # Check if wallet table exists
            if not _check_wallet_table_exists():
                return _json_err(
                    "Wallet module not fully installed. Please upgrade the module in Odoo.",
                    status=503,
                    error_code="MODULE_NOT_READY"
                )

            amount = body.get("amount")
            source_type = body.get("source_type", "topup")
            source_description = body.get("source_description")
            payment_reference = body.get("payment_reference")

            if not amount:
                return _json_err("amount is required", status=400)

            amount = float(amount)
            if amount <= 0:
                return _json_err("Amount must be positive", status=400)

            # Validate source_type
            valid_source_types = ['topup', 'refund', 'cashback', 'gift', 'loyalty', 'promotion', 'manual', 'other']
            if source_type not in valid_source_types:
                return _json_err(f"Invalid source_type. Must be one of: {', '.join(valid_source_types)}", status=400)

            wallet_balance_before = partner.wallet_balance

            # Add credit to wallet
            notes = None
            if payment_reference:
                notes = f"Payment reference: {payment_reference}"

            transaction = partner.add_wallet_credit(
                amount=amount,
                source_type=source_type,
                source_description=source_description or f'Wallet {source_type}',
                notes=notes
            )

            currency = partner.currency_id or request.env.company.currency_id

            return _json_ok(
                "Wallet credited successfully",
                data={
                    "transaction_id": transaction.id,
                    "transaction_reference": transaction.reference,
                    "amount_credited": amount,
                    "wallet_balance_before": wallet_balance_before,
                    "wallet_balance_after": partner.wallet_balance,
                    "currency": currency.name,
                    "currency_symbol": currency.symbol
                }
            )

        except Exception as e:
            _logger.exception("Error adding wallet credit: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/wallet/summary", type="http", auth="public", methods=["GET"], csrf=False)
    def get_wallet_summary(self, **kwargs):
        """
        Get wallet summary with statistics.

        Headers:
            Authorization: Bearer <access_token>

        Response:
            {
                "status": "success",
                "message": "Wallet summary retrieved successfully",
                "data": {
                    "current_balance": 500.00,
                    "currency": "SAR",
                    "total_credits": 1000.00,
                    "total_debits": 500.00,
                    "total_transactions": 15,
                    "credits_count": 8,
                    "debits_count": 7,
                    "by_source": {
                        "topup": { "count": 5, "amount": 500.00 },
                        "refund": { "count": 3, "amount": 500.00 },
                        "order_payment": { "count": 7, "amount": 500.00 }
                    },
                    "recent_transactions": [...]
                }
            }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # Check if wallet table exists
            if not _check_wallet_table_exists():
                return _json_err(
                    "Wallet module not fully installed. Please upgrade the module in Odoo.",
                    status=503,
                    error_code="MODULE_NOT_READY"
                )

            WalletTransaction = request.env["wallet.transaction"].sudo()

            # Get all confirmed transactions
            transactions = WalletTransaction.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "confirmed")
            ])

            # Calculate totals
            credits = transactions.filtered(lambda t: t.transaction_type == 'credit')
            debits = transactions.filtered(lambda t: t.transaction_type == 'debit')

            total_credits = sum(t.amount for t in credits)
            total_debits = sum(t.amount for t in debits)

            # Calculate by source
            by_source = {}
            for txn in transactions:
                source = txn.source_type
                if source not in by_source:
                    by_source[source] = {"count": 0, "amount": 0.0, "type": txn.transaction_type}
                by_source[source]["count"] += 1
                by_source[source]["amount"] += txn.amount

            # Get recent transactions
            recent = WalletTransaction.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "confirmed")
            ], order="create_date desc", limit=5)

            recent_list = []
            for txn in recent:
                recent_list.append({
                    "id": txn.id,
                    "reference": txn.reference,
                    "transaction_type": txn.transaction_type,
                    "amount": txn.amount,
                    "source_type": txn.source_type,
                    "date": str(txn.create_date)[:19] if txn.create_date else ""
                })

            currency = partner.currency_id or request.env.company.currency_id

            return _json_ok(
                "Wallet summary retrieved successfully",
                data={
                    "current_balance": partner.wallet_balance,
                    "currency": currency.name,
                    "currency_symbol": currency.symbol,
                    "total_credits": total_credits,
                    "total_debits": total_debits,
                    "total_transactions": len(transactions),
                    "credits_count": len(credits),
                    "debits_count": len(debits),
                    "by_source": by_source,
                    "recent_transactions": recent_list
                }
            )

        except Exception as e:
            _logger.exception("Error fetching wallet summary: %s", e)
            return _json_err(str(e), status=500)

    # ═══════════════════════════════════════════════════════════════════════════
    # WALLET TRANSFER REQUEST API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════════

    @http.route("/api/wallet/transfer/request", type="http", auth="public", methods=["POST"], csrf=False)
    def create_transfer_request(self, **kwargs):
        """
        إنشاء طلب تحويل مع خصم الرصيد فوراً (حجز) لمنع العميل من استخدام نفس الرصيد مرة أخرى.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        # 🚀 قراءة اللغة من الهيدر لترجمة رسائل الـ API
        header_lang = request.httprequest.headers.get('lang') or request.httprequest.headers.get('Accept-Language')
        is_ar = (header_lang or 'en').lower().startswith('ar')

        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("بيانات غير صالحة (JSON غير صحيح)" if is_ar else "Invalid JSON payload", status=400)

        try:
            amount = float(body.get("amount", 0))
            bank_name = body.get("bank_name")
            account_number = body.get("account_number")

            if amount <= 0 or not bank_name or not account_number:
                msg = "بيانات البنك ناقصة أو المبلغ غير صالح" if is_ar else "Missing bank details or invalid amount"
                return _json_err(msg, status=400)

            # 1. التحقق من الرصيد المتاح (المتبقي بعد أي سحوبات سابقة)
            wallet_balance = partner.wallet_balance
            if wallet_balance < amount:
                msg = "رصيد المحفظة غير كافٍ" if is_ar else "Insufficient wallet balance"
                return _json_err(
                    msg,
                    status=400,
                    data={"wallet_balance": wallet_balance, "requested_amount": amount}
                )

            # 2. إنشاء طلب التحويل (بشكل sudo لضمان التنفيذ)
            transfer_request = request.env["wallet.transfer.request"].sudo().create({
                "partner_id": partner.id,
                "transfer_amount": amount,
                "bank_name": bank_name,
                "account_holder_name": body.get("account_holder_name", partner.name),
                "account_number": account_number,
                "swift_code": body.get("swift_code", ""),
                "reason": body.get("reason", ""),
                "state": "pending",  # الحالة الافتراضية
            })

            # 3. الخصم الفوري من المحفظة (حجز المبلغ)
            # 🚀 التعديل هنا: استخدمنا 'other' بدل 'transfer_request' عشان أودو يقبلها
            transaction = partner.deduct_wallet_balance(
                amount=amount,
                source_type='other',
                source_description=f'Transfer request {transfer_request.sequence} - Pending Approval',
                notes=f'Bank Transfer to {bank_name} - Acc: {account_number}'
            )

            # 4. ربط المعاملة بطلب السحب (اختياري لكن مفيد جداً للـ Tracking)
            if transaction:
                transfer_request.write({'wallet_transaction_id': transaction.id})

            _logger.info("Transfer request %s: Amount %.2f deducted from partner %s wallet",
                         transfer_request.sequence, amount, partner.id)

            msg_success = "تم تقديم طلب التحويل وحجز المبلغ بنجاح" if is_ar else "Transfer request submitted and balance reserved."
            return _json_ok(msg_success, {
                "transfer_request_id": transfer_request.id,
                "request_sequence": transfer_request.sequence,
                "amount_deducted": amount,
                "new_wallet_balance": partner.wallet_balance,
                "state": "pending"
            })

        except Exception as e:
            _logger.exception("Error creating transfer request: %s", e)
            msg_error = "حدث خطأ داخلي، يرجى المحاولة لاحقاً" if is_ar else str(e)
            return _json_err(msg_error, status=500)
    @http.route("/api/wallet/transfer/status", type="http", auth="public", methods=["GET"], csrf=False)
    def get_transfer_status(self, **kwargs):
        """
        Get the status of a wallet transfer request.

        Query params:
            - transfer_request_id: ID of the transfer request
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            transfer_request_id = kwargs.get("transfer_request_id")
            if not transfer_request_id:
                return _json_err("transfer_request_id is required", status=400)

            transfer_req = request.env["wallet.transfer.request"].sudo().search([
                ("id", "=", int(transfer_request_id)),
                ("partner_id", "=", partner.id)
            ], limit=1)

            if not transfer_req:
                return _json_err("Transfer request not found", status=404)

            return _json_ok("Transfer request status fetched", {
                "transfer_request_id": transfer_req.id,
                "request_sequence": transfer_req.sequence,
                "transfer_amount": transfer_req.transfer_amount,
                "wallet_balance_at_request": transfer_req.wallet_balance_at_request,
                "bank_name": transfer_req.bank_name,
                "account_number": transfer_req.account_number,
                "state": transfer_req.state,
                "state_display": dict(transfer_req._fields['state'].selection).get(transfer_req.state),
                "decline_reason": transfer_req.decline_reason or "",
                "bank_transfer_reference": transfer_req.bank_transfer_reference or "",
                "requested_at": str(transfer_req.requested_at)[:19] if transfer_req.requested_at else None,
                "completed_at": str(transfer_req.completed_at)[:19] if transfer_req.completed_at else None,
            })

        except Exception as e:
            _logger.exception("Error fetching transfer status: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/wallet/transfer/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_transfer_history(self, **kwargs):
        """
        Get all wallet transfer requests for the customer.

        Query params (optional):
            - state: Filter by state (pending, approved, processing, completed, declined)
            - limit: Number of records (default: 20)
            - offset: Offset for pagination (default: 0)
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            state = kwargs.get("state")
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            domain = [("partner_id", "=", partner.id)]
            if state:
                domain.append(("state", "=", state))

            TransferRequest = request.env["wallet.transfer.request"].sudo()
            total_count = TransferRequest.search_count(domain)
            requests_list = TransferRequest.search(domain, limit=limit, offset=offset, order="create_date desc")

            data = []
            for req in requests_list:
                data.append({
                    "transfer_request_id": req.id,
                    "request_sequence": req.sequence,
                    "transfer_amount": req.transfer_amount,
                    "bank_name": req.bank_name,
                    "account_number": req.account_number[-4:] if len(req.account_number) > 4 else req.account_number,
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection).get(req.state),
                    "decline_reason": req.decline_reason or "",
                    "requested_at": str(req.requested_at)[:19] if req.requested_at else None,
                    "completed_at": str(req.completed_at)[:19] if req.completed_at else None,
                })

            return _json_ok("Transfer history fetched", {
                "count": len(data),
                "total": total_count,
                "offset": offset,
                "limit": limit,
                "transfer_requests": data
            })

        except Exception as e:
            _logger.exception("Error fetching transfer history: %s", e)
            return _json_err(str(e), status=500)
