# add (or keep) this import near the top
from odoo.http import request, Response
from odoo import http
from odoo.http import request
import requests
import random
import json
import jwt
from datetime import datetime, timedelta
from werkzeug.exceptions import Forbidden
import google.auth.transport.requests
from google.oauth2 import id_token
import os, uuid
from datetime import datetime, timedelta

import logging
_logger = logging.getLogger(__name__)


SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

# ==================== MULTI-LANGUAGE SUPPORT ====================

# Message translations dictionary for partner API
PARTNER_MESSAGES = {
    "authorization_required": {
        "en": "Authorization header is required",
        "ar": "رمز التفويض مطلوب"
    },
    "token_not_found": {
        "en": "Token not found in Authorization header",
        "ar": "لم يتم العثور على الرمز في رأس التفويض"
    },
    "invalid_token_type": {
        "en": "Invalid token type",
        "ar": "نوع الرمز غير صالح"
    },
    "partner_not_found": {
        "en": "Partner not found",
        "ar": "لم يتم العثور على الحساب"
    },
    "token_expired": {
        "en": "Token has expired",
        "ar": "انتهت صلاحية الرمز"
    },
    "invalid_token": {
        "en": "Invalid token",
        "ar": "رمز غير صالح"
    },
    "invalid_json": {
        "en": "Invalid JSON payload",
        "ar": "بيانات JSON غير صالحة"
    },
    "email_or_phone_required": {
        "en": "At least one of email or phone is required",
        "ar": "يجب توفير البريد الإلكتروني أو رقم الهاتف على الأقل"
    },
    "email_in_use": {
        "en": "Email is already in use by another account",
        "ar": "البريد الإلكتروني مستخدم بالفعل من حساب آخر"
    },
    "phone_in_use": {
        "en": "Phone number is already in use by another account",
        "ar": "رقم الهاتف مستخدم بالفعل من حساب آخر"
    },
    "profile_updated": {
        "en": "Profile updated successfully",
        "ar": "تم تحديث الملف الشخصي بنجاح"
    },
    "server_error": {
        "en": "An error occurred. Please try again.",
        "ar": "حدث خطأ. يرجى المحاولة مرة أخرى."
    },
}


def _get_lang():
    """Get language from request header. Default is English."""
    lang_header = request.httprequest.headers.get("lang") or request.httprequest.headers.get("Lang") or request.httprequest.headers.get("Accept-Language") or ""
    lang = lang_header.lower().strip()
    if lang.startswith("ar"):
        return "ar"
    return "en"


def _t(key, **kwargs):
    """
    Translate message key to current language.
    Usage: _t("authorization_required") or _t("custom", en="Hello", ar="مرحبا")
    """
    lang = _get_lang()

    # If custom translations provided in kwargs
    if "en" in kwargs or "ar" in kwargs:
        return kwargs.get(lang, kwargs.get("en", key))

    # Look up in PARTNER_MESSAGES dictionary
    if key in PARTNER_MESSAGES:
        return PARTNER_MESSAGES[key].get(lang, PARTNER_MESSAGES[key].get("en", key))

    # Return key as-is if not found
    return key


def _json(payload, status=200):
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _json_ok(message, data=None, status=200):
    # Auto-translate if message is a key
    translated_message = _t(message) if message in PARTNER_MESSAGES else message
    return Response(json.dumps({
        "status": "success", "message": translated_message, "data": data or {}
    }), status=status, content_type="application/json")


def _json_err(message, status=400, data=None, error_code=None):
    # Auto-translate if message is a key
    translated_message = _t(message) if message in PARTNER_MESSAGES else message
    payload = {"status": "failed", "message": translated_message, "error": translated_message, "data": data or {}}
    if error_code:
        payload["error_code"] = error_code
    return Response(json.dumps(payload), status=status, content_type="application/json")


def _base_url():
    return request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''

def _partner_from_access_token():
    """
    Read Authorization header, decode HS256 access token, return partner record.
    Returns (partner, error_response) where error_response is an HTTP Response if anything fails.
    """
    auth = request.httprequest.headers.get("Authorization")
    if not auth:
        return None, _json_err("authorization_required", 401)

    token = auth.split(" ")[1] if " " in auth else auth
    if not token:
        return None, _json_err("token_not_found", 401)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") and payload.get("type") != "access":
            return None, _json_err("invalid_token_type", 401)

        partner = request.env["res.partner"].sudo().browse(payload.get("partner_id"))
        if not partner.exists():
            return None, _json_err("partner_not_found", 401)
        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json_err("token_expired", 401)
    except jwt.InvalidTokenError:
        return None, _json_err("invalid_token", 401)
    except Exception as e:
        return None, _json_err("server_error", 400)

def _serialize_partner(p):
    return {
        "id": p.id,
        "name": p.name or "",
        "phone": p.phone or "",
        "email": p.email or "",
        "birthday": str(p.birthday) if getattr(p, "birthday", False) else None,
        "marriage_date": str(p.marriage_date) if getattr(p, "marriage_date", False) else None,
        # "company_type": p.company_type or "",
        "avatar_url": f"{_base_url()}/web/image?model=res.partner&id={p.id}&field=image_1920",
    }


class SmsApiController(http.Controller):

    @http.route("/api/me", type="http", auth="public", methods=["GET"], csrf=False)
    def me(self, **kwargs):
        """
        GET /api/me
        Headers: Authorization: Bearer <access_token>
        Returns the profile for the partner encoded in the access token.
        """
        partner, err = _partner_from_access_token()
        if err:
            return err
        return _json({"status": "success", "profile": _serialize_partner(partner)})

    @http.route("/api/me/update", type="http", auth="public", methods=["POST"], csrf=False)
    def me_update(self, **kwargs):
        """
        POST /api/me/update
        Headers: Authorization: Bearer <access_token>
        Body: {"email": "...", "phone": "..."}  (at least one required)
        Updates the authenticated user's email and/or phone.
        If phone changes, verify is reset to False.
        """
        partner, err = _partner_from_access_token()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw)
        except json.JSONDecodeError:
            return _json_err("invalid_json", 400)

        email = (body.get("email") or "").strip()
        phone = (body.get("phone") or "").strip()

        if not email and not phone:
            return _json_err("email_or_phone_required", 400)

        update_vals = {}

        if email:
            existing = request.env["res.partner"].sudo().search([
                ("email", "=", email),
                ("id", "!=", partner.id)
            ], limit=1)
            if existing:
                return _json_err("email_in_use", 409)
            update_vals["email"] = email

        if phone:
            # --- 🚀 بداية لوجيك الأرقام الذكي لضمان عدم التكرار ---
            phone_variations = [phone]
            clean_phone = ''.join(filter(str.isdigit, phone))

            if clean_phone:
                phone_variations.extend([clean_phone, '+' + clean_phone, '00' + clean_phone])
                # مصر
                if clean_phone.startswith('2001') and len(clean_phone) == 13:
                    core_phone = clean_phone[3:]
                    phone_variations.extend(
                        ['0' + core_phone, '20' + core_phone, '+20' + core_phone, '0020' + core_phone])
                elif clean_phone.startswith('20') and len(clean_phone) == 12:
                    phone_variations.append('0' + clean_phone[2:])
                elif clean_phone.startswith('01') and len(clean_phone) == 11:
                    phone_variations.extend(['20' + clean_phone[1:], '+20' + clean_phone[1:], '0020' + clean_phone[1:]])
                # السعودية
                if clean_phone.startswith('96605') and len(clean_phone) == 13:
                    core_phone = clean_phone[4:]
                    phone_variations.extend(
                        ['0' + core_phone, '966' + core_phone, '+966' + core_phone, '00966' + core_phone])
                elif clean_phone.startswith('966') and len(clean_phone) == 12:
                    phone_variations.append('0' + clean_phone[3:])
                elif clean_phone.startswith('05') and len(clean_phone) == 10:
                    phone_variations.extend(
                        ['966' + clean_phone[1:], '+966' + clean_phone[1:], '00966' + clean_phone[1:]])

            # البحث باللوجيك الذكي في حقل التليفون والموبايل
            existing = request.env["res.partner"].sudo().search([
                ('id', '!=', partner.id),
                '|',
                ("phone", "in", phone_variations),
                ("mobile", "in", phone_variations)
            ], limit=1)
            # --- نهاية لوجيك الأرقام ---

            if existing:
                return _json_err("phone_in_use", 409)  # 👈 ده الإيرور اللي كان بيظهرلك

            update_vals["phone"] = phone
            # Reset verification when phone changes
            if phone != (partner.phone or ""):
                update_vals["verify"] = False

        partner.sudo().write(update_vals)

        return _json_ok("profile_updated", data={"profile": _serialize_partner(partner)})