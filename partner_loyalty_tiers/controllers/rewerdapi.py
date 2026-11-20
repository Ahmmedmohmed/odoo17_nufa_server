import json
import logging
import base64
import jwt
import pytz
from datetime import datetime

from odoo import http, fields
from odoo.http import request, Response
from odoo.tools import float_round
from odoo import http
import json

# استدعاء دوال المساعدة (تأكد من وجود ملف api.py في نفس الفولدر)
from .api import _json_ok, _json_err, _t

_logger = logging.getLogger(__name__)

# ==========================================
# 🔑 Secret Key (مفتاح تشفير الـ JWT)
# ==========================================
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"


# ==========================================
# 🛡️ Authentication Helpers (دوال الحماية)
# ==========================================

def _partner_from_token():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err(
            _t("bearer_token_required", en="Authorization Bearer token is required", ar="رمز التفويض Bearer مطلوب"),
            status=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner_id = payload.get("partner_id")
        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("partner_not_found", status=404)
        return partner, None
    except Exception as e:
        return None, _json_err("invalid_token", status=401)


def _partner_or_device():
    """
    التحقق من الهوية: إما عن طريق التوكن (مسجل) أو Device ID (زائر)
    """
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer "):
        partner, error = _partner_from_token()
        if not error:
            return partner, None, False, None

    device_id = request.httprequest.headers.get("X-Device-ID")
    if device_id:
        Partner = request.env["res.partner"].sudo()
        guest_partner = Partner.search([("email", "=", "guest@guest.local")], limit=1)
        if not guest_partner:
            guest_partner = Partner.create({"name": "Guest Customer", "email": "guest@guest.local"})
        return guest_partner, device_id, True, None

    return None, None, False, _json_err("token_required", status=401)


# ==========================================
# 🎯 Mobile Loyalty Endpoints (المحرك الأساسي)
# ==========================================

class MobileLoyaltyAPI(http.Controller):

    def _json(self, data, status=200):
        return http.Response(
            json.dumps(data),
            content_type='application/json',
            status=status
        )

    # 1️⃣ جلب العروض العامة (كتالوج العروض المتاحة في السيستم)
    @http.route('/api/v1/loyalty/offers', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_loyalty_offers(self, **kwargs):
        partner, device_id, is_guest, error_response = _partner_or_device()
        if error_response: return error_response

        try:
            today = fields.Date.today()
            domain = [
                ('active', '=', True),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ]

            all_programs = request.env['loyalty.program'].sudo().search(domain)
            available_programs = []
            for prog in all_programs:
                if prog.company_id and partner.company_id and prog.company_id != partner.company_id:
                    continue

                available_programs.append({
                    'program_id': prog.id,
                    'name': prog.name,
                    'program_type': prog.program_type,
                    'trigger': prog.trigger,
                    'description': prog.name,
                    'rules': [{'min_amount': r.minimum_amount, 'min_qty': r.minimum_qty} for r in prog.rule_ids],
                    'rewards': [{'reward_id': r.id, 'description': r.description, 'reward_type': r.reward_type} for r in prog.reward_ids]
                })

            return _json_ok(data=available_programs)
        except Exception as e:
            _logger.exception("Error in offers API: %s", e)
            return _json_err("Server Error", status=500)

    # 2️⃣ محفظة العميل (رصيد النقاط والكوبونات الشخصية)
        # 2️⃣ محفظة العميل (الإجمالي فقط)
    @http.route('/api/v1/loyalty/my_wallet', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_my_wallet(self, **kwargs):
        partner, error_response = _partner_from_token()
        if error_response: return error_response
        try:
            # 🚀 قراءة الرصيد المباشر من حقل المحفظة المخصص الخاص بالعميل
            total_balance = round(partner.wallet_balance, 2)

            # 🚀 جلب آخر حركة في المحفظة المخصصة كنوع من المرجعية (Reference)
            last_transaction = request.env['wallet.transaction'].sudo().search(
                [('partner_id', '=', partner.id), ('state', '=', 'confirmed')],
                limit=1, order='create_date desc'
            )

            wallet_data = {
                'total_balance': total_balance,
                'wallet_code': last_transaction.reference if last_transaction else "",
                'currency': partner.currency_id.name or request.env.company.currency_id.name or 'SAR'
            }

            return _json_ok(data=wallet_data, message="Wallet retrieved successfully")
        except Exception as e:
            _logger.exception("Error in wallet API: %s", e)
            return _json_err("Server Error", status=500)
    # 3️⃣ عروض السلة الحالية (المكافآت التي حقق العميل شروطها الآن)
    @http.route('/api/v1/loyalty/order_rewards', type='http', auth='public', methods=['GET'], csrf=False, cors='*')
    def get_order_rewards(self, order_id=None, **kwargs):
        partner, device_id, is_guest, error_response = _partner_or_device()
        if error_response: return error_response
        if not order_id: return _json_err("order_id missing", status=400)

        header_lang = request.httprequest.headers.get('lang', 'en').lower()
        is_ar = 'ar' in header_lang
        lang_code = 'ar_001' if is_ar else 'en_US'

        try:
            order = request.env['sale.order'].sudo().with_context(lang=lang_code).browse(int(order_id))
            if not order.exists() or order.partner_id.id != partner.id:
                return _json_err("Access Denied", status=403)

            # 🚀 ====== فحص السلة وتنظيفها من المنتجات المتضاربة ====== 🚀
            removed_products = []
            for line in order.order_line:
                # لو المنتج مربوط بشركة، والشركة دي مش هي نفس شركة السلة
                if line.product_id.company_id and line.product_id.company_id.id != order.company_id.id:
                    removed_products.append(line.product_id.with_context(lang=lang_code).name)
                    line.unlink()  # نحذف السطر من السلة بأمان

            # لو حذفنا منتجات، نرجع رسالة للعميل يعرف إن السلة اتحدثت
            if removed_products:
                products_str = ", ".join(removed_products)
                msg_ar = f"تم إزالة بعض المنتجات من سلتك لأنها غير متاحة في الفرع المختار: {products_str}"
                msg_en = f"Some products were removed as they are not available in the selected branch: {products_str}"
                return _json_err(msg_ar if is_ar else msg_en, status=400)
            # ==========================================================

            # 🔥 محاولة تحديث الخصومات بعد التأكد من نظافة السلة
            try:
                order.sudo()._update_programs_and_rewards()
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'name'):
                    error_msg = e.name
                elif hasattr(e, 'args') and e.args:
                    error_msg = e.args[0]

                # فحص احتياطي لو الخطأ لسه بيحصل لأي سبب تاني يخص الشركات
                if "company" in error_msg.lower() or "الشركة" in error_msg:
                    msg = "عذراً، يوجد تعارض في فروع بعض المنتجات. يرجى مراجعة السلة." if is_ar else "Some products are conflicting with the selected branch."
                    return _json_err(msg, status=400)
                else:
                    raise e

            claimable_rewards = order.sudo()._get_claimable_rewards()

            data = []
            seen_rewards = set()

            for coupon, rewards in claimable_rewards.items():
                program = coupon.program_id.with_context(lang=lang_code)

                if program.program_type != 'coupons':
                    for reward in rewards:
                        reward_translated = reward.with_context(lang=lang_code)

                        if reward_translated.id in seen_rewards:
                            continue

                        seen_rewards.add(reward_translated.id)

                        data.append({
                            'program_id': program.id,
                            'program_name': program.name,
                            'reward_id': reward_translated.id,
                            'description': reward_translated.description,
                            'reward_type': reward_translated.reward_type,
                            'required_points': reward_translated.required_points
                        })

            return _json_ok(data=data)

        except Exception as e:
            import traceback
            _logger.error(traceback.format_exc())

            error_msg = str(e)
            if hasattr(e, 'name'):
                error_msg = e.name
            elif hasattr(e, 'args') and e.args:
                error_msg = e.args[0]

            final_msg = f"حدث خطأ: {error_msg}" if is_ar else f"Error: {error_msg}"
            return _json_err(final_msg, status=500)
    # 4️⃣ /api/v1/loyalty/apply_code معرف بالفعل في sms_mobile_sa_otp/controllers/loyaty.py (منعاً لتكرار المسار)
    # @http.route('/api/v1/loyalty/apply_code', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    # def apply_code(self, **kwargs): ...
    # 5️⃣ تطبيق الهدايا التلقائية (مثل BOGO)
    @http.route('/api/v1/loyalty/apply_auto_promotions', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    def apply_auto_promotions(self, **kwargs):
        partner, device_id, is_guest, error_response = _partner_or_device()
        if error_response: return error_response

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            order_id = body.get('order_id')
            if not order_id:
                return _json_err("order_id missing", status=400)
            order = request.env['sale.order'].sudo().browse(int(order_id))
            if not order.exists():
                return _json_err("Order not found", status=404)
            if not is_guest and order.partner_id.id != partner.id:
                return _json_err("Access Denied", status=403)

            order._update_programs_and_rewards()
            # _get_claimable_rewards() في أودو 17 ترجع dict مفتاحه الكوبون (loyalty.card) وليس البرنامج
            claimable = order._get_claimable_rewards()
            applied = []
            for coupon, rewards in claimable.items():
                program = coupon.program_id
                # العروض التلقائية فقط (ليست أكواد/كوبونات/نقاط/محافظ/جيفت كارت)
                if program.trigger != 'auto' or program.program_type not in ('promotion', 'buy_x_get_y'):
                    continue
                for reward in rewards:
                    result = order._apply_program_reward(reward, coupon)
                    if result and result.get('error'):
                        continue
                    applied.append(reward.description)
                    break  # مكافأة واحدة لكل عرض لتجنب تطبيق بدائل متعددة

            order._update_programs_and_rewards()
            return _json_ok(data={'total': order.amount_total, 'applied_rewards': applied})
        except Exception as e:

            # ده هيخلي الإيرور يظهر في Postman بالظبط هو إيه
            return _json_err(str(e), status=500)

    # 6️⃣ تنفيذ استلام المكافأة المختارة (Claim)
    @http.route('/api/v1/loyalty/claim_reward', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    def claim_reward(self, **kwargs):
        partner, error_response = _partner_from_token()
        if error_response: return error_response

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            order_id, reward_id = body.get('order_id'), body.get('reward_id')

            if not order_id or not reward_id:
                return _json_err("order_id and reward_id are required", status=400)
            order = request.env['sale.order'].sudo().browse(int(order_id))
            reward = request.env['loyalty.reward'].sudo().browse(int(reward_id))
            if not order.exists() or order.partner_id.id != partner.id:
                return _json_err("Access Denied", status=403)
            if not reward.exists():
                return _json_err("Reward not found", status=404)

            order._update_programs_and_rewards()
            # _apply_program_reward تحتاج الكوبون (loyalty.card) وليس البرنامج
            # ملاحظة: في العروض التلقائية قد يكون مفتاح الـ dict هو recordset فارغ loyalty.card() لذلك نفحص بـ is None
            claimable = order._get_claimable_rewards()
            coupon = next((c for c, rws in claimable.items() if reward in rws), None)
            if coupon is None and reward.program_id.program_type in ('loyalty', 'ewallet'):
                card = request.env['loyalty.card'].sudo().search([
                    ('partner_id', '=', partner.id),
                    ('program_id', '=', reward.program_id.id),
                ], limit=1)
                if card:
                    coupon = card
            if coupon is None:
                return _json_err("Reward is not claimable for this order", status=400)
            result = order._apply_program_reward(reward, coupon)
            if result and result.get('error'):
                return _json_err(result['error'], status=400)
            order._update_programs_and_rewards()

            return _json_ok(data={'new_total': order.amount_total})
        except Exception as e:
            _logger.exception("Error in claim_reward: %s", e)
            return _json_err(str(e), status=400)

    @http.route('/api/checkout/simulate_discount', type='http', auth='public', methods=['POST'], csrf=False)
    def simulate_discount(self, **kwargs):
        try:
            # 1. التحقق من التوكن (Token) أو معرف الجهاز للزائر (X-Device-ID)
            auth_header = request.httprequest.headers.get("Authorization") or ""
            device_id = request.httprequest.headers.get("X-Device-ID")
            partner = None

            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                    partner = request.env["res.partner"].sudo().browse(payload.get("partner_id"))
                    if not partner.exists():
                        return self._json({'status': 'error', 'message': 'Partner not found'}, status=404)
                except Exception:
                    return self._json({'status': 'error', 'message': 'Invalid or expired token'}, status=401)
            elif device_id:
                Partner = request.env["res.partner"].sudo()
                partner = Partner.search([("email", "=", "guest@guest.local")], limit=1)
                if not partner:
                    partner = Partner.create({"name": "Guest Customer", "email": "guest@guest.local"})
            else:
                return self._json({'status': 'error', 'message': 'Authorization Bearer token is required'}, status=401)

            # 2. استخراج البيانات المرسلة في جسم الطلب (JSON Body)
            import json
            body = json.loads(request.httprequest.data)
            order_id = body.get('order_id')
            reward_id = body.get('reward_id')
            coupon_code = body.get('coupon_code')

            if not order_id:
                return self._json({'status': 'error', 'message': 'Missing order_id'}, status=400)

            order = request.env['sale.order'].sudo().browse(int(order_id))
            if not order.exists() or order.partner_id.id != partner.id:
                return self._json({'status': 'error', 'message': 'Order not found or access denied'}, status=404)

            if order.state != 'draft':
                return self._json({'status': 'error', 'message': 'Only draft orders can simulate discounts'},
                                  status=400)

            order_total = order.amount_total

            # تحديد لغة الاستجابة لترجمة وصف المكافأة (Reward Description)
            lang = request.httprequest.headers.get('lang', 'en').lower()
            is_ar = 'ar' in lang
            odoo_lang = 'ar_001' if is_ar else 'en_US'

            reward = None
            program = None
            applied_rule = None
            available_points = 0.0

            # 3. المنطق الأساسي للبحث عن المكافأة أو كود الخصم
            if reward_id:
                reward = request.env['loyalty.reward'].sudo().with_context(lang=odoo_lang).browse(int(reward_id))
                if not reward.exists():
                    return self._json({'status': 'error', 'message': 'Reward not found'}, status=404)
                program = reward.program_id

                if program.program_type in ['loyalty', 'ewallet']:
                    card = request.env['loyalty.card'].sudo().search(
                        [('partner_id', '=', partner.id), ('program_id', '=', program.id)], limit=1)
                    available_points = card.points if card else 0.0

                    if reward.required_points > available_points or available_points <= 0:
                        msg = 'نقاطك غير كافية لاستبدال هذه المكافأة' if is_ar else 'Insufficient points'
                        return self._json({'status': 'error', 'message': msg}, status=400)

            elif coupon_code:
                card = request.env['loyalty.card'].sudo().search([('code', '=', coupon_code)], limit=1)

                if card:
                    program = card.program_id
                    if card.expiration_date and card.expiration_date < fields.Date.today():
                        msg = 'انتهت صلاحية كود الخصم' if is_ar else 'This coupon has expired.'
                        return self._json({'status': 'error', 'message': msg}, status=400)

                    if card.points <= 0 or (program.reward_ids and card.points < program.reward_ids[0].required_points):
                        msg = 'تم استخدام كود الخصم هذا مسبقاً أو لا يوجد به رصيد' if is_ar else 'This coupon has already been used or has insufficient balance.'
                        return self._json({'status': 'error', 'message': msg}, status=400)

                    reward = program.reward_ids[0].with_context(lang=odoo_lang) if program.reward_ids else None
                    available_points = card.points

                    if card.partner_id and card.partner_id.id != partner.id:
                        msg = 'كود الخصم غير صالح لحسابك' if is_ar else 'Code not valid for your account'
                        return self._json({'status': 'error', 'message': msg}, status=400)
                else:
                    rule = request.env['loyalty.rule'].sudo().search(
                        [('code', '=', coupon_code), ('program_id.active', '=', True)], limit=1)
                    if rule:
                        program = rule.program_id
                        reward = program.reward_ids[0].with_context(lang=odoo_lang) if program.reward_ids else None
                        applied_rule = rule

            if not program or not program.active or not reward:
                msg = 'كود الخصم غير صحيح أو العرض منتهي' if is_ar else 'Invalid coupon or inactive program'
                return self._json({'status': 'error', 'message': msg}, status=400)

            # التحقق من صلاحية الفئة (Tier) للعميل إن وجدت
            if hasattr(reward, '_is_valid_for_tier') and not reward._is_valid_for_tier(partner):
                msg = 'هذه المكافأة غير متاحة لمستوى عضويتك الحالي' if is_ar else 'This reward is not available for your current loyalty tier'
                return self._json({'status': 'error', 'message': msg}, status=400)

            # 🚀 ====== التحقق من شروط القواعد (الحد الأدنى للمبلغ والكمية) ====== 🚀
            # ملاحظة: قواعد برامج كروت الهدايا والمحفظة تخص شراء الكارت/الشحن وليس استرداد الرصيد
            if program.program_type not in ('gift_card', 'ewallet'):
                rules_to_check = applied_rule if applied_rule else program.rule_ids
                non_reward_lines = order.order_line.filtered(lambda l: not l.is_reward_line and not l.reward_id and not l.display_type)
                for rule in rules_to_check:
                    # التحقق مما إذا كان الحد الأدنى يحسب قبل أو بعد الضريبة بناءً على إعدادات أودو
                    check_amount = order.amount_untaxed if rule.minimum_amount_tax_mode == 'excl' else order.amount_total

                    if rule.minimum_amount > 0 and check_amount < rule.minimum_amount:
                        currency_name = order.currency_id.name or ''
                        msg_en = f"A minimum of {rule.minimum_amount} {currency_name} should be purchased to get the reward"
                        msg_ar = f"يجب أن يكون إجمالي الطلب {rule.minimum_amount} {currency_name} على الأقل لتطبيق الخصم"
                        return self._json({'status': 'error', 'message': msg_ar if is_ar else msg_en}, status=400)

                    if rule.minimum_qty > 0:
                        valid_products = rule._get_valid_products() if hasattr(rule, '_get_valid_products') else False
                        if valid_products:
                            rule_lines = non_reward_lines.filtered(lambda l: l.product_id in valid_products)
                        else:
                            rule_lines = non_reward_lines
                        total_qty = sum(rule_lines.mapped('product_uom_qty'))
                        if total_qty < rule.minimum_qty:
                            msg_en = f"A minimum quantity of {rule.minimum_qty} qualifying products is required to get the reward"
                            msg_ar = f"يجب شراء عدد ({rule.minimum_qty}) من المنتجات المؤهلة على الأقل لتطبيق الخصم"
                            return self._json({'status': 'error', 'message': msg_ar if is_ar else msg_en}, status=400)
            # ==============================================================

            # 4. حساب قيمة الخصم بناءً على إعدادات المكافأة ونطاق تطبيقها
            discount_amount = 0.0
            if reward.reward_type == 'discount':
                # تحديد الوعاء الخاضع للخصم حسب discount_applicability (الطلب كامل / منتجات محددة / الأرخص)
                discountable = order_total
                try:
                    if reward.discount_applicability == 'specific' and hasattr(order, '_discountable_specific'):
                        discountable, _ = order._discountable_specific(reward)
                    elif reward.discount_applicability == 'cheapest' and hasattr(order, '_discountable_cheapest'):
                        discountable, _ = order._discountable_cheapest(reward)
                    elif hasattr(order, '_discountable_order'):
                        discountable, _ = order._discountable_order(reward)
                except Exception:
                    discountable = order_total

                if discountable <= 0:
                    msg = 'لا توجد منتجات مؤهلة لهذا الخصم في سلتك' if is_ar else 'No qualifying products in your cart for this discount'
                    return self._json({'status': 'error', 'message': msg}, status=400)

                if reward.discount_mode == 'percent':
                    discount_amount = discountable * (reward.discount / 100.0)
                elif reward.discount_mode == 'per_order':
                    discount_amount = min(reward.discount, discountable)
                elif reward.discount_mode == 'per_point':
                    if program.program_type in ('gift_card', 'ewallet'):
                        points_to_use = available_points
                    elif reward.required_points:
                        points_to_use = (available_points // reward.required_points) * reward.required_points
                    else:
                        points_to_use = available_points
                    discount_amount = min(points_to_use * reward.discount, discountable)

                if getattr(reward, 'discount_max_amount', 0.0) > 0.0 and discount_amount > reward.discount_max_amount:
                    discount_amount = reward.discount_max_amount

            elif reward.reward_type == 'product':
                reward_product = getattr(reward, 'reward_product_id', False)
                reward_qty = getattr(reward, 'reward_product_qty', 1.0) or 1.0
                if reward_product:
                    matching_line = order.order_line.filtered(
                        lambda l: l.product_id.id == reward_product.id and not l.is_reward_line and not l.reward_id
                    )[:1]
                    if matching_line and matching_line.product_uom_qty > 0:
                        unit_total = matching_line.price_total / matching_line.product_uom_qty
                        discount_amount = unit_total * min(reward_qty, matching_line.product_uom_qty)
                    else:
                        taxes = reward_product.taxes_id.filtered(lambda t: t.company_id == order.company_id)
                        if order.fiscal_position_id:
                            taxes = order.fiscal_position_id.map_tax(taxes)
                        tax_res = taxes.compute_all(
                            reward_product.lst_price,
                            currency=order.currency_id,
                            quantity=reward_qty,
                            product=reward_product,
                            partner=order.partner_id,
                        )
                        discount_amount = tax_res.get('total_included', reward_product.lst_price * reward_qty)

            elif reward.reward_type == 'shipping':
                delivery_lines = order.order_line.filtered(lambda l: getattr(l, 'is_delivery', False))
                discount_amount = sum(delivery_lines.mapped('price_total'))
                if getattr(reward, 'discount_max_amount', 0.0) > 0.0 and discount_amount > reward.discount_max_amount:
                    discount_amount = reward.discount_max_amount

            if discount_amount > order_total:
                discount_amount = order_total

            return self._json({
                'status': 'success',
                'data': {
                    'is_valid': True,
                    'discount_amount': round(discount_amount, 2),
                    'original_total': round(order_total, 2),
                    'new_total': round(order_total - discount_amount, 2),
                    'reward_description': getattr(reward, 'description', '') or reward.name
                }
            }, status=200)

        except Exception as e:
            _logger.exception("simulate_discount failed")
            return self._json({'status': 'error', 'message': str(e)}, status=500)
