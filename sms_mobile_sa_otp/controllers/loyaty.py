# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import jwt
import logging
import json
import requests
from datetime import datetime

SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"
_logger = logging.getLogger(__name__)

# WhatsApp Meta API Configuration
META_TOKEN = "EAFuId4IjxeEBQSFeQD7RJdJFRUFuv6BT6XWDvbCgTORukY4OZCuDmquZChtRlC6N2EFmBQKvzG84fHsbqvaa657a85gfAHoLkKqvzQrEBDHMZC8PMZC5ISPQ9bdoDFkOmENXbLzecsYZBkaAkXezEPFFlQrNJiB8877i9Jfoe6ZAE5zZAnVZAIHkbYNcy3z6wdVOhwZDZD"
PHONE_NUMBER_ID = "926541170542819"
META_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"


# ==========================================
# 🛠️ Helper Functions
# ==========================================
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
        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("Partner not found", 404)
        return partner, None
    except jwt.ExpiredSignatureError:
        return None, _json_err("Token has expired", 401)
    except jwt.InvalidTokenError:
        return None, _json_err("Invalid token", 401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err(str(e), 400)


# ==========================================
# 🛍️ Loyalty, Promo Codes & Gift Cards APIs
# ==========================================
class MobileLoyaltyAPI(http.Controller):

    # -------------------------------------------------------------------------
    # 1. جلب رصيد نقاط الولاء (Get Points Balance & Profile)
    # -------------------------------------------------------------------------
    @http.route('/api/loyalty/points', type='http', auth='public', methods=['GET'], csrf=False)
    def get_loyalty_points_balance(self, **kwargs):
        """جلب إجمالي النقاط المتاحة في محفظة العميل ومستواه"""
        partner, err = _partner_from_token()
        if err: return err

        is_ar = request.httprequest.headers.get('lang', 'en').lower() == 'ar'

        try:
            loyalty_cards = request.env['loyalty.card'].sudo().search([
                ('partner_id', '=', partner.id)
            ])

            total_points = sum(loyalty_cards.mapped('points'))

            if total_points >= 1000:
                tier = 'ذهبي' if is_ar else 'Gold'
            elif total_points >= 500:
                tier = 'فضي' if is_ar else 'Silver'
            else:
                tier = 'برونزي' if is_ar else 'Bronze'

            data = {
                "total_points": total_points,
                "tier": tier,
                "cards": [{
                    "card_id": card.id,
                    "program_name": card.program_id.name,
                    "points": card.points,
                    "code": card.code
                } for card in loyalty_cards]
            }

            msg = "تم جلب رصيد النقاط بنجاح" if is_ar else "Points balance fetched successfully"
            return _json_ok(msg, data)

        except Exception as e:
            _logger.exception("Get Points Balance Error")
            return _json_err(str(e), status=500)

    # -------------------------------------------------------------------------
    # 2. تطبيق كود خصم أو كارت هدية (Apply Promo / Gift Card)
    # -------------------------------------------------------------------------
    @http.route('/api/v1/loyalty/apply_code', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    def apply_code(self, **kwargs):
        partner, device_id, is_guest, error_response = _partner_or_device()
        if error_response: return error_response

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            order_id, code = body.get('order_id'), body.get('code')

            order = request.env['sale.order'].sudo().browse(int(order_id))
            if not order.exists() or order.partner_id.id != partner.id:
                return _json_err("Access Denied", status=403)

            # 1. تحديث البرامج
            order.sudo()._update_programs_and_rewards()

            # 2. الحل السحري: هننادي الدالة من الكلاس الأصلي (sale_loyalty)
            # عشان نهرب من الـ TypeError اللي بيعمله موديول الشحن
            from odoo.addons.sale_loyalty.models.sale_order import SaleOrder as SaleLoyaltyBase

            try:
                # محاولة التطبيق العادية
                status = order.sudo()._try_apply_code(code)
            except TypeError:
                # لو ضربت TypeError، هننادي دالة الأب مباشرة بالـ ID بتاع الأوردر
                _logger.warning("Applying fallback for _try_apply_code due to TypeError")
                status = SaleLoyaltyBase._try_apply_code(order.sudo(), code)

            # 3. فحص النتيجة
            if isinstance(status, dict) and (status.get('error') or status.get('not_found')):
                return _json_err(status.get('error') or status.get('not_found'), status=400)

            # 4. تحديث نهائي وحساب الخصم
            order.sudo()._update_programs_and_rewards()
            reward_lines = order.order_line.filtered(lambda l: l.is_reward_line)
            discount = abs(sum(reward_lines.mapped('price_subtotal')))

            return _json_ok(data={
                'total': order.amount_total,
                'discount': round(discount, 2),
                'status': 'applied'
            })

        except Exception as e:
            _logger.exception("Final attempt failed: %s", e)
            return _json_err(str(e), status=500)

    # -------------------------------------------------------------------------
    # 3. جلب المكافآت المتاحة للعميل (Available Rewards for Cart)
    # -------------------------------------------------------------------------
    @http.route('/api/loyalty/available_rewards', type='http', auth='public', methods=['GET'], csrf=False)
    def get_available_rewards(self, **kwargs):
        """عرض المكافآت المتاحة للاستبدال بناءً على نقاط العميل ومحتوى السلة"""
        partner, err = _partner_from_token()
        if err: return err

        is_ar = request.httprequest.headers.get('lang', 'en').lower() == 'ar'
        order_id = kwargs.get('order_id')

        if not order_id:
            return _json_err("رقم الطلب مطلوب" if is_ar else "order_id is required")

        try:
            order = request.env['sale.order'].sudo().browse(int(order_id))
            if not order.exists() or order.partner_id.id != partner.id:
                return _json_err("الطلب غير موجود" if is_ar else "Order not found", status=404)

            order._update_programs_and_rewards()
            claimable_rewards_dict = order._get_claimable_rewards()

            rewards_list = []
            for card, rewards in claimable_rewards_dict.items():
                for reward in rewards:
                    rewards_list.append({
                        "reward_id": reward.id,
                        "description": reward.description,
                        "points_cost": reward.required_points,
                        "card_points_balance": card.points,
                        "reward_type": reward.reward_type
                    })

            msg = "تم جلب المكافآت" if is_ar else "Rewards fetched"
            return _json_ok(msg, {"rewards": rewards_list})

        except Exception as e:
            _logger.exception("Get Rewards Error")
            return _json_err(str(e), status=500)

    # -------------------------------------------------------------------------
    # 4. استبدال نقاط الولاء بمكافأة (Redeem Loyalty Points)
    # -------------------------------------------------------------------------
    @http.route('/api/loyalty/redeem', type='http', auth='public', methods=['POST'], csrf=False)
    def redeem_loyalty_points(self, **kwargs):
        """استبدال النقاط بمكافأة معينة وإضافتها كخصم على السلة"""
        partner, err = _partner_from_token()
        if err: return err

        is_ar = request.httprequest.headers.get('lang', 'en').lower() == 'ar'

        try:
            data = json.loads(request.httprequest.data or '{}')
        except:
            data = kwargs

        order_id = data.get('order_id')
        reward_id = data.get('reward_id')

        if not order_id or not reward_id:
            return _json_err("رقم الطلب ورقم المكافأة مطلوبان" if is_ar else "order_id and reward_id are required")

        try:
            order = request.env['sale.order'].sudo().browse(int(order_id))
            reward = request.env['loyalty.reward'].sudo().browse(int(reward_id))

            if not order.exists() or not reward.exists():
                return _json_err("الطلب أو المكافأة غير موجودة" if is_ar else "Order or Reward not found", status=404)

            res = order._apply_program_reward(reward, coupon=False)

            if res and 'error' in res:
                return _json_err(res['error'])

            msg = "تم استبدال النقاط بنجاح" if is_ar else "Points redeemed successfully"
            discount_amount = sum(line.price_subtotal for line in order.order_line if line.is_reward_line)

            return _json_ok(msg, {
                "order_id": order.id,
                "new_amount_total": order.amount_total,
                "discount_amount": abs(discount_amount)
            })

        except Exception as e:
            _logger.exception("Redeem Points Error")
            return _json_err(str(e), status=500)