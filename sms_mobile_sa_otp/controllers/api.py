from odoo import http
from odoo.http import request, Response
import requests
import random
import json
import jwt
import re
from datetime import datetime, timedelta
import google.auth.transport.requests
from google.oauth2 import id_token
import os, uuid
import logging

_logger = logging.getLogger(__name__)
import logging
_logger = logging.getLogger(__name__)

SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

GOOGLE_CLIENT_ID = "1076496866609-j3uk7icpg9015f1iih9cpua5gh07s3lm.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = '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'

REFRESH_SECRET_KEY = os.getenv("ODOO_REFRESH_SECRET_KEY", SECRET_KEY)
ACCESS_TTL_MINUTES = 240
REFRESH_TTL_DAYS = 14

APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "com.noufapps.noufbeauty")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "37XX3D6WSB")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "DLM8PL34ZD")
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

SECRET_KEY = os.getenv("APP_JWT_SECRET", "bcf2e5f933a069b6d737d5cc0a7af01b")

# Static OTP for testing/Apple review - Set to None for production (random OTP)
STATIC_OTP_CODE = os.getenv("STATIC_OTP_CODE", "1111")  # Set to None in production

# ==================== MULTI-LANGUAGE SUPPORT ====================

# Message translations dictionary
MESSAGES = {
    # Success messages
    "login_successful": {
        "en": "Login successful",
        "ar": "تم تسجيل الدخول بنجاح"
    },
    "otp_sent": {
        "en": "OTP sent successfully",
        "ar": "تم إرسال رمز التحقق بنجاح"
    },
    "otp_generated": {
        "en": "OTP generated",
        "ar": "تم إنشاء رمز التحقق"
    },
    "otp_verified": {
        "en": "OTP verified successfully",
        "ar": "تم التحقق من الرمز بنجاح"
    },
    "partner_created": {
        "en": "Partner created or updated; OTP generated",
        "ar": "تم إنشاء أو تحديث الحساب؛ تم إنشاء رمز التحقق"
    },
    "partner_created_otp_sent": {
        "en": "Partner created or updated; OTP generated and sent",
        "ar": "تم إنشاء أو تحديث الحساب؛ تم إنشاء وإرسال رمز التحقق"
    },
    "password_reset_successful": {
        "en": "Password reset successful",
        "ar": "تم إعادة تعيين كلمة المرور بنجاح"
    },
    "password_changed": {
        "en": "Password changed successfully",
        "ar": "تم تغيير كلمة المرور بنجاح"
    },
    "profile_updated": {
        "en": "Profile updated successfully",
        "ar": "تم تحديث الملف الشخصي بنجاح"
    },
    "cart_updated": {
        "en": "Cart updated successfully",
        "ar": "تم تحديث السلة بنجاح"
    },
    "item_removed": {
        "en": "Item removed from cart",
        "ar": "تم إزالة المنتج من السلة"
    },
    "cart_cleared": {
        "en": "Cart cleared successfully",
        "ar": "تم إفراغ السلة بنجاح"
    },
    "token_refreshed": {
        "en": "Token refreshed successfully",
        "ar": "تم تجديد الرمز بنجاح"
    },

    # Error messages
    "invalid_credentials": {
        "en": "Invalid credentials. Please check your phone number and try again.",
        "ar": "بيانات الدخول غير صحيحة. يرجى التحقق من رقم الهاتف والمحاولة مرة أخرى."
    },
    "invalid_password": {
        "en": "Invalid password",
        "ar": "كلمة المرور غير صحيحة"
    },
    "invalid_otp": {
        "en": "Invalid OTP",
        "ar": "رمز التحقق غير صحيح"
    },
    "otp_expired": {
        "en": "OTP has expired. Please request a new one.",
        "ar": "انتهت صلاحية رمز التحقق. يرجى طلب رمز جديد."
    },
    "otp_not_generated": {
        "en": "OTP not generated yet",
        "ar": "لم يتم إنشاء رمز التحقق بعد"
    },
    "otp_already_sent": {
        "en": "OTP already sent",
        "ar": "تم إرسال رمز التحقق مسبقاً"
    },
    "phone_required": {
        "en": "Phone number is required",
        "ar": "رقم الهاتف مطلوب"
    },
    "phone_password_required": {
        "en": "Phone and either password or OTP are required",
        "ar": "رقم الهاتف وكلمة المرور أو رمز التحقق مطلوبان"
    },
    "phone_otp_required": {
        "en": "Phone and OTP are required",
        "ar": "رقم الهاتف ورمز التحقق مطلوبان"
    },
    "partner_not_found": {
        "en": "Partner not found",
        "ar": "لم يتم العثور على الحساب"
    },
    "phone_not_registered": {
        "en": "Phone number not registered",
        "ar": "رقم الهاتف غير مسجل"
    },
    "need_to_register": {
        "en": "You need to register first. Please set a password to proceed.",
        "ar": "يجب التسجيل أولاً. يرجى تعيين كلمة مرور للمتابعة."
    },
    "account_not_verified": {
        "en": "Account not verified. Please verify your account first.",
        "ar": "الحساب غير موثق. يرجى توثيق حسابك أولاً."
    },
    "phone_already_verified": {
        "en": "Phone is already verified",
        "ar": "رقم الهاتف موثق مسبقاً"
    },
    "no_phone_on_account": {
        "en": "No phone number on your account. Please update your phone first.",
        "ar": "لا يوجد رقم هاتف في حسابك. يرجى تحديث رقم الهاتف أولاً."
    },
    "partner_has_no_phone": {
        "en": "Partner has no phone number",
        "ar": "الحساب لا يحتوي على رقم هاتف"
    },
    "invalid_json": {
        "en": "Invalid JSON payload",
        "ar": "بيانات JSON غير صالحة"
    },
    "invalid_phone_format": {
        "en": "Invalid phone number format. Please enter a valid phone number.",
        "ar": "صيغة رقم الهاتف غير صحيحة. يرجى إدخال رقم هاتف صالح."
    },
    "sms_service_unavailable": {
        "en": "SMS service temporarily unavailable. Please try again later.",
        "ar": "خدمة الرسائل غير متوفرة مؤقتاً. يرجى المحاولة لاحقاً."
    },
    "sms_connection_failed": {
        "en": "SMS service connection failed. Please try again.",
        "ar": "فشل الاتصال بخدمة الرسائل. يرجى المحاولة مرة أخرى."
    },
    "phone_blocked": {
        "en": "This phone number is blocked. Please contact support.",
        "ar": "رقم الهاتف هذا محظور. يرجى التواصل مع الدعم."
    },
    "too_many_requests": {
        "en": "Too many requests. Please wait a moment and try again.",
        "ar": "طلبات كثيرة جداً. يرجى الانتظار قليلاً والمحاولة مرة أخرى."
    },
    "sms_auth_failed": {
        "en": "SMS service authentication failed. Please contact support.",
        "ar": "فشل التحقق من خدمة الرسائل. يرجى التواصل مع الدعم."
    },
    "sms_failed": {
        "en": "Failed to send SMS. Please try again or contact support.",
        "ar": "فشل إرسال الرسالة. يرجى المحاولة مرة أخرى أو التواصل مع الدعم."
    },
    "authorization_required": {
        "en": "Authorization header is required",
        "ar": "رمز التفويض مطلوب"
    },
    "token_required": {
        "en": "Authorization token or X-Device-ID header is required",
        "ar": "رمز التفويض أو معرف الجهاز مطلوب"
    },
    "token_expired": {
        "en": "Token has expired",
        "ar": "انتهت صلاحية الرمز"
    },
    "invalid_token": {
        "en": "Invalid token",
        "ar": "رمز غير صالح"
    },
    "passwords_not_match": {
        "en": "New password and confirm password do not match",
        "ar": "كلمة المرور الجديدة وتأكيد كلمة المرور غير متطابقتين"
    },
    "no_products_provided": {
        "en": "No products provided",
        "ar": "لم يتم تقديم أي منتجات"
    },
    "product_not_found": {
        "en": "Product not found",
        "ar": "المنتج غير موجود"
    },
    "out_of_stock": {
        "en": "Requested quantity exceeds available stock",
        "ar": "الكمية المطلوبة تتجاوز المخزون المتاح"
    },
    "no_cart_found": {
        "en": "No active cart found",
        "ar": "لا توجد سلة نشطة"
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
    Usage: _t("login_successful") or _t("custom_message", en="Hello", ar="مرحبا")
    """
    lang = _get_lang()

    # If custom translations provided in kwargs
    if "en" in kwargs or "ar" in kwargs:
        return kwargs.get(lang, kwargs.get("en", key))

    # Look up in MESSAGES dictionary
    if key in MESSAGES:
        return MESSAGES[key].get(lang, MESSAGES[key].get("en", key))

    # Return key as-is if not found
    return key


def _generate_otp_code():
    """Generate OTP code - static for testing or random for production."""
    if STATIC_OTP_CODE:
        return STATIC_OTP_CODE
    return str(random.randint(1000, 9999))


def _parse_sms_error(status_code, response_text):
    """
    Parse SMS provider error response and return a user-friendly message key.
    Returns the message key for translation.
    """
    try:
        error_data = json.loads(response_text)
        error_message = None

        if isinstance(error_data, dict):
            error_message = error_data.get("message") or error_data.get("error") or error_data.get("msg")

            if not error_message and "errors" in error_data:
                errors = error_data["errors"]
                if isinstance(errors, dict):
                    for field, messages in errors.items():
                        if isinstance(messages, list) and messages:
                            error_message = messages[0]
                            break
                        elif isinstance(messages, str):
                            error_message = messages
                            break

        if error_message:
            error_lower = error_message.lower() if error_message else ""
            if any(keyword in error_lower for keyword in ["phone", "number", "mobile", "invalid", "هاتف", "رقم", "غير صالح"]):
                return "invalid_phone_format"
            elif any(keyword in error_lower for keyword in ["balance", "credit", "رصيد"]):
                return "sms_service_unavailable"
            elif any(keyword in error_lower for keyword in ["blocked", "محظور"]):
                return "phone_blocked"

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    if status_code == 422:
        return "invalid_phone_format"
    elif status_code == 401:
        return "sms_auth_failed"
    elif status_code == 429:
        return "too_many_requests"
    elif status_code >= 500:
        return "sms_service_unavailable"

    return "sms_failed"


def _json_ok(message="OK", data=None, status=200):
    # Auto-translate if message is a key
    translated_message = _t(message) if message in MESSAGES else message
    return Response(json.dumps({
        "status": "success", "message": translated_message, "data": data or {}
    }), status=status, content_type="application/json")


def _json_err(message, status=400, data=None, error_code=None):
    # Auto-translate if message is a key
    translated_message = _t(message) if message in MESSAGES else message
    payload = {"status": "failed", "message": translated_message, "data": data or {}}
    if error_code:
        payload["error_code"] = error_code
    return Response(json.dumps(payload), status=status, content_type="application/json")


def _parse_body():
    raw = request.httprequest.data or b"{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise


import uuid


def _generate_access_token(partner_id):
    # نحدد عدد الأيام المطلوبة، مثلاً 7 أيام
    ACCESS_TTL_DAYS = 200

    payload = {
        "partner_id": partner_id,
        "type": "access",
        # التعديل هنا: استخدام days بدلاً من minutes
        "exp": datetime.utcnow() + timedelta(days=ACCESS_TTL_DAYS),
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _generate_refresh_token(partner_id):
    payload = {
        "partner_id": partner_id,
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TTL_DAYS),
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm="HS256")


def _store_refresh_token(partner, token):
    partner.sudo().write({
        "refresh_token": token,
        "refresh_token_expiration": datetime.utcnow() + timedelta(days=REFRESH_TTL_DAYS),
    })


_APPLE_JWKS_CACHE = {"keys": None, "fetched_at": None, "ttl_seconds": 3600}


def _get_apple_jwks():
    now = datetime.utcnow()
    if (_APPLE_JWKS_CACHE["keys"] is not None and
            _APPLE_JWKS_CACHE["fetched_at"] is not None and
            (now - _APPLE_JWKS_CACHE["fetched_at"]).total_seconds() < _APPLE_JWKS_CACHE["ttl_seconds"]):
        return _APPLE_JWKS_CACHE["keys"]
    try:
        resp = requests.get(APPLE_JWKS_URL, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        _APPLE_JWKS_CACHE["keys"] = jwks.get("keys", [])
        _APPLE_JWKS_CACHE["fetched_at"] = now
        return _APPLE_JWKS_CACHE["keys"]
    except Exception as e:
        _logger.exception("Failed to fetch Apple JWKs: %s", e)
        return []


def _get_apple_public_key_for_kid(kid):
    from jwt.algorithms import RSAAlgorithm
    for jwk in _get_apple_jwks():
        if jwk.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(jwk))
    return None


def _verify_apple_id_token(id_token_str):
    """
    Verify Apple id_token:
      - signature (RS256) via JWKS
      - issuer
      - audience (must equal your Services ID)
      - exp/iat
    Returns decoded payload dict; raises ValueError on failure.
    """
    try:
        unverified = jwt.get_unverified_header(id_token_str)
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token header: {e}")

    kid = unverified.get("kid")
    if not kid:
        raise ValueError("Missing kid in token header")

    key = _get_apple_public_key_for_kid(kid)
    if key is None:
        _APPLE_JWKS_CACHE["keys"] = None
        _APPLE_JWKS_CACHE["fetched_at"] = None
        key = _get_apple_public_key_for_kid(kid)
        if key is None:
            raise ValueError("Unable to find matching Apple public key")

    try:
        payload = jwt.decode(
            id_token_str,
            key,
            algorithms=["RS256"],
            audience=APPLE_CLIENT_ID,  # Ensure this matches the client_id in the token
            issuer="https://appleid.apple.com",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Apple id_token has expired")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid audience for Apple id_token")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid issuer for Apple id_token")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid Apple id_token: {e}")


def _model_has_field(model_name, field_name):
    try:
        return field_name in request.env[model_name]._fields
    except Exception:
        return False


def _validate_stored_refresh_token(partner, token):
    if not partner.refresh_token or partner.refresh_token != token:
        return False, "Refresh token mismatch"
    exp = getattr(partner, "refresh_token_expiration", None)
    if not exp or exp <= datetime.utcnow():
        return False, "Refresh token expired"
    return True, None


def _partner_from_token():
    """Authenticate user from JWT Bearer token. Returns (partner, error_response)."""
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err(_t("bearer_token_required", en="Authorization Bearer token is required", ar="رمز التفويض Bearer مطلوب"), status=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner_id = payload.get("partner_id")
        if not partner_id:
            return None, _json_err(_t("invalid_token_payload", en="Invalid token payload", ar="بيانات الرمز غير صالحة"), status=401)

        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("partner_not_found", status=404)

        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json_err("token_expired", status=401)
    except jwt.InvalidTokenError:
        return None, _json_err("invalid_token", status=401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err("server_error", status=400)


class SmsApiController(http.Controller):

    # @http.route("/api/create_partner", type="http", auth="public", methods=["POST"], csrf=False)
    # def create_partner(self, **kwargs):
    #     try:
    #         body = _parse_body()
    #         partner_id_from_request = body.get("partner_id")
    #         name = (body.get("name") or "").strip()
    #         phone = (body.get("phone") or "").strip()
    #         email = (body.get("email") or "").strip()
    #         password = (body.get("password") or "").strip()
    #         birthday = body.get("birthday")
    #         marriage_date = body.get("marriage_date")
    #
    #         if not phone:
    #             return _json_err("phone is required", status=400)
    #
    #         if partner_id_from_request:
    #             partner = request.env["res.partner"].sudo().browse(partner_id_from_request)
    #             if not partner.exists():
    #                 return _json_err("Partner not found", status=404)
    #         else:
    #             existing = request.env["res.partner"].sudo().search(
    #                 [("phone", "=", phone), ("email", "=", email), ("verify", "=", True)], limit=1
    #             )
    #             if existing:
    #                 return _json_err(
    #                     "Phone number already exists and verified",
    #                     status=409,
    #                     data={"partner": {
    #                         "id": existing.id, "name": existing.name, "phone": existing.phone,
    #                         "verify": bool(existing.verify)
    #                     }}
    #                 )
    #             partner = request.env["res.partner"].sudo().create({
    #                 "name": name or (f"User {phone[-4:]}" if phone else "User"),
    #                 "phone": phone,
    #                 "email": email or False,
    #                 "password": password or False,
    #                 "birthday": birthday or False,
    #                 "marriage_date": marriage_date or False,
    #                 "company_type": "person",
    #                 "verify": False,
    #                 "exist": True,
    #             })
    #
    #         partner.write({
    #             "name": name or partner.name,
    #             "phone": phone or partner.phone,
    #             "email": email or partner.email,
    #             "password": password or partner.password,
    #             "birthday": birthday or partner.birthday,
    #             "marriage_date": marriage_date or partner.marriage_date,
    #             "company_type": "person",
    #             "verify": False,
    #             "exist": True,
    #         })
    #
    #         otp_code = str(random.randint(100000, 999999))
    #         partner.write({
    #             "otp_code": otp_code,
    #             "otp_expiration": datetime.utcnow() + timedelta(minutes=5),
    #             "otp_sent": False,
    #         })
    #
    #         return _json_ok(
    #             "Partner created or updated; OTP generated",
    #             status=201 if not partner_id_from_request else 200,
    #             data={
    #                 "partner_id": partner.id,
    #                 "name": partner.name,
    #                 "phone": partner.phone,
    #                 "verify": bool(partner.verify),
    #                 "exist": bool(partner.exist),
    #                 "otp_code": otp_code,
    #                 "otp_expires_in": 300,
    #             }
    #         )
    #
    #     except json.JSONDecodeError:
    #         return _json_err("Invalid JSON payload", status=400)
    #     except Exception as e:
    #         _logger.exception("create_partner error")
    #         return _json_err(str(e), status=500)

    @http.route("/api/create_partner", type="http", auth="public", methods=["POST"], csrf=False)
    def create_partner(self, **kwargs):
        try:
            body = _parse_body()
            partner_id_from_request = body.get("partner_id")
            name = (body.get("name") or "").strip()
            phone = (body.get("phone") or "").strip()
            email = (body.get("email") or "").strip()
            password = (body.get("password") or "").strip()
            birthday = body.get("birthday")
            marriage_date = body.get("marriage_date")

            if not phone:
                return _json_err("phone_required", status=400)

            if partner_id_from_request:
                partner = request.env["res.partner"].sudo().browse(int(partner_id_from_request))
                if not partner.exists():
                    return _json_err("partner_not_found", status=404)
            else:
                existing = request.env["res.partner"].sudo().search(
                    [("phone", "=", phone), ("email", "=", email), ("verify", "=", True)], limit=1
                )
                if existing:
                    return _json_err(
                        _t("phone_already_verified", en="Phone number already exists and verified", ar="رقم الهاتف موجود ومُوثق بالفعل"),
                        status=409,
                        data={"partner": {
                            "id": existing.id, "name": existing.name, "phone": existing.phone,
                            "verify": bool(existing.verify)
                        }}
                    )
                partner = request.env["res.partner"].sudo().create({
                    "name": name or (f"User {phone[-4:]}" if phone else "User"),
                    "phone": phone,
                    "email": email or False,
                    "password": password or False,
                    "birthday": birthday or False,
                    "marriage_date": marriage_date or False,
                    "company_type": "person",
                    "verify": False,
                    "exist": True,
                })

            partner.write({
                "name": name or partner.name,
                "phone": phone or partner.phone,
                "email": email or partner.email,
                "password": password or partner.password,
                "birthday": birthday or partner.birthday,
                "marriage_date": marriage_date or partner.marriage_date,
                "company_type": "person",
                "exist": True,

            })

            otp_code = _generate_otp_code()
            otp_exp = datetime.utcnow() + timedelta(minutes=5)
            partner.write({
                "otp_code": otp_code,
                "otp_expiration": otp_exp,
                "otp_sent": False,
            })

            otp_sent = False
            if not bool(partner.verify):
                try:
                    sms_api_url = "https://app.mobile.net.sa/api/v1/send"
                    sms_msg = f"Your verification code is: {otp_code}. It expires in 5 minutes."
                    payload = {
                        "number": partner.phone,
                        "senderName": "Mobile.sa",
                        "sendAtOption": "NOW",
                        "messageBody": sms_msg,
                        "allow_duplicate": False
                    }
                    headers = {
                        "Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1",
                        "Accept": "application/json"
                    }
                    resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)
                    if resp.status_code == 200 and "error" not in (resp.text or "").lower():
                        partner.sudo().write({"otp_sent": True})
                        otp_sent = True
                    else:
                        error_msg = _parse_sms_error(resp.status_code, resp.text)
                        return _json_err(error_msg, status=502)
                except requests.exceptions.RequestException as e:
                    return _json_err("sms_connection_failed", status=502)

            return _json_ok(
                "partner_created_otp_sent" if otp_sent else "partner_created",
                status=201 if not partner_id_from_request else 200,
                data={
                    "partner_id": partner.id,
                    "name": partner.name,
                    "phone": partner.phone,
                    "verify": bool(partner.verify),
                    "exist": bool(partner.exist),
                    "otp_code": otp_code,
                    "otp_expires_in": 300,
                    "otp_sent": otp_sent,
                }
            )

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("create_partner error")
            return _json_err("server_error", status=500)

    @http.route("/api/generate_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def generate_otp(self, **kwargs):
        try:
            body = _parse_body()
            partner_id = body.get("partner_id")
            if not partner_id:
                return _json_err(_t("partner_id_required", en="partner_id is required", ar="معرف الشريك مطلوب"), status=400)

            partner = request.env["res.partner"].sudo().browse(int(partner_id))
            if not partner.exists():
                return _json_err("partner_not_found", status=404)

            otp_code = _generate_otp_code()
            partner.sudo().write({
                "otp_code": otp_code,
                "otp_expiration": datetime.utcnow() + timedelta(minutes=5),
                "otp_sent": False,
            })

            return _json_ok("otp_generated", data={
                "partner_id": partner.id,
                "otp_code": otp_code,
                "expires_in": 300,
            })

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("generate_otp error")
            return _json_err("server_error", status=500)

    @http.route("/api/send_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def send_otp(self, **kwargs):
        try:
            body = _parse_body()
            partner_id = body.get("partner_id")
            phone = (body.get("phone") or "").strip()
            msg = body.get("msg")

            if not partner_id and not phone:
                return _json_err(_t("partner_or_phone_required", en="partner_id or phone is required", ar="معرف الشريك أو رقم الهاتف مطلوب"), status=400)

            partner = None
            otp_code = None
            if partner_id:
                partner = request.env["res.partner"].sudo().browse(int(partner_id))
                if not partner.exists():
                    return _json_err("partner_not_found", status=404)
                phone = partner.phone
                if not phone:
                    return _json_err("partner_has_no_phone", status=409)
                otp_code = partner.otp_code
                if not otp_code:
                    return _json_err("otp_not_generated", status=409)
                if partner.otp_sent:
                    return _json_err("otp_already_sent", status=409)

            sms_msg = msg or (f"Your OTP is: {otp_code}" if otp_code else "Your OTP code")

            sms_api_url = "https://app.mobile.net.sa/api/v1/send"
            payload = {
                "number": phone, "senderName": "Mobile.sa", "sendAtOption": "NOW",
                "messageBody": sms_msg, "allow_duplicate": False
            }
            headers = {"Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1", "Accept": "application/json"}

            resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200 and "error" not in resp.text.lower():
                if partner:
                    partner.sudo().write({"otp_sent": True})
                return _json_ok("otp_sent", data={"otp_code": otp_code})
            error_msg = _parse_sms_error(resp.status_code, resp.text)
            return _json_err(error_msg, status=502)

        except requests.exceptions.RequestException as e:
            return _json_err("sms_connection_failed", status=502)
        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("send_otp error")
            return _json_err("server_error", status=500)



    # @http.route("/api/login", type="http", auth="public", methods=["POST"], csrf=False)
    # def login(self, **kwargs):
    #     try:
    #         body = _parse_body()
    #         phone = (body.get("phone") or "").strip()
    #         password = (body.get("password") or "").strip()
    #         otp = (body.get("otp") or "").strip()
    #         partner_id_from_request = body.get("partner_id")
    #
    #         if not phone or (not password and not otp):
    #             return _json_err("Phone and either password or OTP are required", status=400)
    #
    #         if partner_id_from_request:
    #             partner = request.env["res.partner"].sudo().search([("id", "=", partner_id_from_request)], limit=1)
    #         else:
    #             partner = request.env["res.partner"].sudo().search([("phone", "=", phone), ("verify", "=", True)],
    #                                                                limit=1)
    #         if not partner.password and partner_id_from_request:
    #             return _json_err("You need to register first. Please set a password to proceed.", status=403)
    #
    #         if not partner:
    #             return _json_err("Partner not found or not verified", status=404)
    #
    #         if not partner.verify and not partner_id_from_request:
    #             return _json_err("Account not verified. Please verify your account first.", status=403)
    #
    #         if otp and (partner.otp_code or "") != otp:
    #             return _json_err("Invalid OTP", status=401)
    #
    #         if password and (partner.password or "") != password:
    #             return _json_err("Invalid password", status=401)
    #
    #
    #
    #         access_token = _generate_access_token(partner.id)
    #         refresh_token = _generate_refresh_token(partner.id)
    #         _store_refresh_token(partner, refresh_token)
    #
    #         response_data = {
    #             "token": access_token,
    #             "refresh_token": refresh_token,
    #             "expires_in": ACCESS_TTL_MINUTES,
    #             "phone": partner.phone,
    #             "verify": bool(partner.verify),
    #             "otp": partner.otp_code,
    #         }
    #
    #         if partner_id_from_request:
    #             response_data["partner_id"] = partner_id_from_request
    #         else:
    #             response_data["partner_id"] = partner.id
    #
    #         return _json_ok("Login successful", data=response_data)
    #
    #     except json.JSONDecodeError:
    #         return _json_err("Invalid JSON payload", status=400)
    #     except Exception as e:
    #         _logger.exception("login error")
    #         return _json_err(str(e), status=500)

    @http.route("/api/login", type="http", auth="public", methods=["POST"], csrf=False)
    def login(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            print(f"\n\n🚀 =====> Mobile Sent Phone: '{phone}' <===== 🚀\n\n")
            _logger.info(f"=====> Mobile Sent Phone: '{phone}' <=====")
            password = (body.get("password") or "").strip()
            otp = (body.get("otp") or "").strip()
            partner_id_from_request = body.get("partner_id")

            if not phone or (not password and not otp):
                return _json_err("phone_password_required", status=400)

            # Find partner by ID or phone
            if partner_id_from_request:
                partner = request.env["res.partner"].sudo().search([("id", "=", partner_id_from_request)], limit=1)
            else:
                # --- بداية معالجة رقم التليفون بجميع صيغه (مصر، السعودية، ودولي) ---
                phone_variations = [phone]
                # استخراج الأرقام فقط (بدون مسافات أو حروف أو +)
                clean_phone = ''.join(filter(str.isdigit, phone))

                if clean_phone:
                    # 1. إضافة الصيغ العامة
                    phone_variations.extend([
                        clean_phone,
                        '+' + clean_phone,
                        '00' + clean_phone
                    ])

                    # 2. معالجة مفتاح مصر (+20)
                    if clean_phone.startswith('2001') and len(clean_phone) == 13:
                        # لو الموبايل باعت الكود 20 ومعه الصفر (مثال: 2001117004567)
                        core_phone = clean_phone[3:]  # استخراج 117004567
                        phone_variations.extend(
                            ['0' + core_phone, '20' + core_phone, '+20' + core_phone, '0020' + core_phone])
                    elif clean_phone.startswith('20') and len(clean_phone) == 12:
                        phone_variations.append('0' + clean_phone[2:])  # تحويل 2010 إلى 010
                    elif clean_phone.startswith('01') and len(clean_phone) == 11:
                        phone_variations.extend(
                            ['20' + clean_phone[1:], '+20' + clean_phone[1:], '0020' + clean_phone[1:]])

                    # 3. معالجة مفتاح السعودية (+966)
                    if clean_phone.startswith('96605') and len(clean_phone) == 13:
                        # لو الموبايل باعت الكود 966 ومعه الصفر (مثال: 96605xxxxxxx)
                        core_phone = clean_phone[4:]  # استخراج 5xxxxxxx
                        phone_variations.extend(
                            ['0' + core_phone, '966' + core_phone, '+966' + core_phone, '00966' + core_phone])
                    elif clean_phone.startswith('966') and len(clean_phone) == 12:
                        phone_variations.append('0' + clean_phone[3:])  # تحويل 9665 إلى 05
                    elif clean_phone.startswith('05') and len(clean_phone) == 10:
                        phone_variations.extend(
                            ['966' + clean_phone[1:], '+966' + clean_phone[1:], '00966' + clean_phone[1:]])

                # === 🚀 التعديل هنا: جلب أحدث عميل بالبحث في خانة التليفون أو الموبايل معاً 🚀 ===
                partners = request.env["res.partner"].sudo().search([
                    '|',
                    ("phone", "in", phone_variations),
                    ("mobile", "in", phone_variations)
                ], order="id desc")

                # فلترة: اختيار الحساب اللي ليه باسورد كأولوية قصوى
                partner = partners.filtered(lambda p: p.password)[:1] or partners[:1]
                # --- نهاية معالجة رقم التليفون ---

            # Check if partner exists (phone not registered)
            if not partner:
                return _json_err("invalid_credentials", status=401)

            # Check if partner has password set (not registered)
            if not partner.password:
                return _json_err("need_to_register", status=403)

            # OTP verification
            if otp:
                if (partner.otp_code or "") != otp:
                    return _json_err("invalid_otp", status=401)
                partner.sudo().write({'verify': True})

            # Password verification
            if password and (partner.password or "") != password:
                return _json_err("invalid_password", status=401)

            # Verify account if not already verified
            if not partner.verify:
                partner.sudo().write({'verify': True})

            access_token = _generate_access_token(partner.id)
            refresh_token = _generate_refresh_token(partner.id)
            _store_refresh_token(partner, refresh_token)

            response_data = {
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": ACCESS_TTL_MINUTES,
                "phone": partner.phone,
                "verify": bool(partner.verify),
                "otp": partner.otp_code,
            }

            if partner_id_from_request:
                response_data["partner_id"] = partner_id_from_request
            else:
                response_data["partner_id"] = partner.id

            return _json_ok("login_successful", data=response_data)

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("login error")
            return _json_err("server_error", status=500)
    @http.route("/api/reset_password", type="http", auth="public", methods=["POST"], csrf=False)
    def reset_password(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header:
                return _json_err("authorization_required", status=401)
            token = auth_header.split(" ")[1] if " " in auth_header else None
            if not token:
                return _json_err(_t("token_not_found", en="Token not found in the Authorization header", ar="لم يتم العثور على الرمز في رأس التفويض"), status=401)

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("token_expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("invalid_token", status=401)

            body = _parse_body()
            old_password = (body.get("old_password") or "").strip()
            new_password = (body.get("new_password") or "").strip()
            confirm_password = (body.get("confirm_password") or "").strip()

            if not old_password or not new_password or not confirm_password:
                return _json_err(_t("password_fields_required", en="Old password, new password, and confirm password are required", ar="كلمة المرور القديمة والجديدة وتأكيد كلمة المرور مطلوبة"), status=400)
            if new_password != confirm_password:
                return _json_err("passwords_not_match", status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("partner_not_found", status=404)
            if (partner.password or "") != old_password:
                return _json_err(_t("old_password_incorrect", en="Old password is incorrect", ar="كلمة المرور القديمة غير صحيحة"), status=401)

            partner.sudo().write({"password": new_password})
            return _json_ok("password_reset_successful", data={"otp_code": partner.otp_code})

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("reset_password error")
            return _json_err("server_error", status=500)

    import re
    # تأكد من وجود باقي الاستدعاءات الخاصة بك (datetime, requests, json)

    @http.route("/api/forgot_password/request", type="http", auth="public", methods=["POST"], csrf=False)
    def forgot_password_request(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            custom_msg = body.get("msg")

            if not phone:
                return _json_err("phone_required", status=400)

            # 1. تنظيف الرقم من أي مسافات، شرطات، أو أقواس
            clean_phone = re.sub(r'\D', '', phone)

            # 2. بناء قائمة الاحتمالات (Variations)
            variations = {phone, clean_phone, '+' + clean_phone}

            # استخراج "الرقم الأساسي" للسعودية أو مصر
            base = None

            # --- احتمالات السعودية ---
            if clean_phone.startswith('9665') and len(clean_phone) == 12:
                base = clean_phone[3:]  # 5XXXXXXXX
            elif clean_phone.startswith('5') and len(clean_phone) == 9:
                base = clean_phone  # 5XXXXXXXX
            elif clean_phone.startswith('05') and len(clean_phone) == 10:
                base = clean_phone[1:]  # 5XXXXXXXX

            # --- احتمالات مصر ---
            elif clean_phone.startswith('201') and len(clean_phone) == 12:
                base = clean_phone[2:]  # 1XXXXXXXXX
            elif clean_phone.startswith('1') and len(clean_phone) == 10:
                base = clean_phone  # 1XXXXXXXXX
            elif clean_phone.startswith('01') and len(clean_phone) == 11:
                base = clean_phone[1:]  # 1XXXXXXXXX

            # إذا تم التعرف على الرقم كـ سعودي أو مصري، نقوم بتوليد كافة أشكال الحفظ في الداتا بيز
            if base:
                if base.startswith('5'):  # السعودية
                    variations.update([
                        base,  # 5XXXXXXXX
                        '0' + base,  # 05XXXXXXXX
                        '966' + base,  # 9665XXXXXXXX
                        '+966' + base,  # +9665XXXXXXXX
                        '+966 ' + base,  # +966 5XXXXXXXX
                        '+9660' + base,  # +96605XXXXXXXX
                        '00966' + base  # 009665XXXXXXXX
                    ])
                elif base.startswith('1'):  # مصر
                    variations.update([
                        base,  # 1XXXXXXXXX
                        '0' + base,  # 01XXXXXXXXX
                        '20' + base,  # 201XXXXXXXXX
                        '+20' + base,  # +201XXXXXXXXX
                        '+20 ' + base,  # +20 1XXXXXXXXX
                        '+200' + base,  # +2001XXXXXXXXX
                        '0020' + base  # 00201XXXXXXXXX
                    ])

            # 3. البحث في قاعدة البيانات في حقلي (phone) و (mobile)
            partner = request.env["res.partner"].sudo().search([
                '|',
                ("phone", "in", list(variations)),
                ("mobile", "in", list(variations))
            ], limit=1)

            if not partner:
                return _json_err("phone_not_registered", status=404)

            # باقي اللوجيك الخاص بإرسال رسالة التحقق كما هو
            otp_code = _generate_otp_code()
            partner.sudo().write({
                "otp_code": otp_code,
                "otp_expiration": datetime.utcnow() + timedelta(minutes=5),
                "otp_sent": False,
            })

            # سنرسل الـ phone كما جاء من الواجهة لمزود الـ SMS لتجنب أي مشاكل في صيغة المزود
            sms_msg = custom_msg or f"Your password reset OTP is: {otp_code}. It expires in 5 minutes."
            sms_api_url = "https://app.mobile.net.sa/api/v1/send"
            payload = {"number": phone, "senderName": "Mobile.sa", "sendAtOption": "NOW",
                       "messageBody": sms_msg, "allow_duplicate": True}
            headers = {"Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1", "Accept": "application/json"}

            ok_resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)
            if not (ok_resp.status_code == 200 and "error" not in ok_resp.text.lower()):
                error_msg = _parse_sms_error(ok_resp.status_code, ok_resp.text)
                return _json_err(error_msg, status=502)

            partner.sudo().write({"otp_sent": True})
            return _json_ok("otp_sent", data={"otp_code": otp_code, "expires_in": 300})

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("forgot_password_request error")
            return _json_err("server_error", status=500)

    @http.route("/api/forgot_password/confirm", type="http", auth="public", methods=["POST"], csrf=False)
    def forgot_password_confirm(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            new_password = (body.get("new_password") or "").strip()
            confirm_password = (body.get("confirm_password") or "").strip()

            if not phone or not new_password or not confirm_password:
                return _json_err(
                    _t("forgot_password_fields_required", en="phone, new_password, confirm_password are required",
                       ar="رقم الهاتف وكلمة المرور الجديدة وتأكيد كلمة المرور مطلوبة"), status=400)
            if new_password != confirm_password:
                return _json_err("passwords_not_match", status=400)

            # --- 1. بناء احتمالات الرقم الذكي زي باقي الـ APIs ---
            clean_phone = re.sub(r'\D', '', phone)
            variations = {phone, clean_phone, '+' + clean_phone}
            base = None

            if clean_phone.startswith('9665') and len(clean_phone) == 12:
                base = clean_phone[3:]
            elif clean_phone.startswith('5') and len(clean_phone) == 9:
                base = clean_phone
            elif clean_phone.startswith('05') and len(clean_phone) == 10:
                base = clean_phone[1:]
            elif clean_phone.startswith('201') and len(clean_phone) == 12:
                base = clean_phone[2:]
            elif clean_phone.startswith('1') and len(clean_phone) == 10:
                base = clean_phone
            elif clean_phone.startswith('01') and len(clean_phone) == 11:
                base = clean_phone[1:]

            if base:
                if base.startswith('5'):
                    variations.update(
                        [base, '0' + base, '966' + base, '+966' + base, '+966 ' + base, '+9660' + base, '00966' + base])
                elif base.startswith('1'):
                    variations.update(
                        [base, '0' + base, '20' + base, '+20' + base, '+20 ' + base, '+200' + base, '0020' + base])

            # --- 2. البحث الذكي في الداتابيز مع شرط إن الحساب مفعل ---
            partner = request.env["res.partner"].sudo().search([
                ('verify', '=', True),
                '|',
                ("phone", "in", list(variations)),
                ("mobile", "in", list(variations))
            ], order="create_date desc", limit=1)

            if not partner:
                return _json_err("phone_not_registered", status=404)

            # --- 3. تغيير الباسورد بنجاح ---
            partner.sudo().write({"password": new_password})
            return _json_ok("password_reset_successful")

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("forgot_password_confirm error")
            return _json_err("server_error", status=500)

    @http.route("/api/logout", type="http", auth="public", methods=["POST"], csrf=False)
    def logout(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header:
                return _json_err("authorization_required", status=401)
            token = auth_header.split(" ")[1] if " " in auth_header else None
            if not token:
                return _json_err(_t("token_not_found", en="Token not found in the Authorization header", ar="لم يتم العثور على الرمز في رأس التفويض"), status=401)

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("token_expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("invalid_token", status=401)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("partner_not_found", status=404)

            partner.sudo().write({"fcm_token": False})
            return _json_ok(_t("logout_successful", en="Logged out successfully, FCM token cleared", ar="تم تسجيل الخروج بنجاح"))

        except Exception as e:
            _logger.exception("logout error")
            return _json_err("server_error", status=500)

    @http.route("/api/auth/refresh", type="http", auth="public", methods=["POST"], csrf=False)
    def auth_refresh(self, **kwargs):
        try:
            try:
                body = _parse_body()
            except json.JSONDecodeError:
                return _json_err("invalid_json", status=400)

            refresh_token = (body.get("refresh_token") or "").strip()
            _logger.info("REFRESH incoming len=%s head=%s", len(refresh_token or ""), (refresh_token or "")[:40])
            if not refresh_token:
                return _json_err(_t("refresh_token_required", en="refresh_token is required", ar="رمز التجديد مطلوب"), status=400)

            try:
                payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                _logger.info("REFRESH payload: %s", payload)
            except jwt.ExpiredSignatureError:
                return _json_err(_t("refresh_token_expired", en="Refresh token has expired", ar="انتهت صلاحية رمز التجديد"), status=401)
            except jwt.InvalidTokenError as e:
                _logger.warning("REFRESH decode failed: %s", e)
                return _json_err(_t("invalid_refresh_token", en="Invalid refresh token", ar="رمز التجديد غير صالح"), status=401)

            if payload.get("type") != "refresh":
                return _json_err(_t("invalid_token_type", en="Invalid token type", ar="نوع الرمز غير صالح"), status=401)

            partner_id = payload.get("partner_id")
            if not partner_id:
                return _json_err(_t("invalid_payload", en="Invalid payload: missing partner_id", ar="البيانات غير صالحة: معرف الشريك مفقود"), status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("partner_not_found", status=404)

            ok, err = _validate_stored_refresh_token(partner, refresh_token)
            if not ok:
                _logger.warning("REFRESH validation failed: %s", err)
                return _json_err(err, status=401)

            new_access = _generate_access_token(partner.id)
            new_refresh = _generate_refresh_token(partner.id)
            _store_refresh_token(partner, new_refresh)
            _logger.info("REFRESH success for partner %s", partner.id)

            return _json_ok("token_refreshed", data={
                "token": new_access,
                "refresh_token": new_refresh,
                "expires_in": ACCESS_TTL_MINUTES
            })

        except Exception as e:
            _logger.exception("auth_refresh error")
            return _json_err("server_error", status=500)

    @http.route("/api/send_otp_by_phone", type="http", auth="public", methods=["POST"], csrf=False)
    def send_otp_by_phone(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            custom_msg = body.get("msg")
            name = (body.get("name") or "").strip()

            if not phone:
                return _json_err("phone_required", status=400)

            # --- 1. معالجة وتوحيد رقم التليفون (عشان الـ SMS API يقبله وما يضربش 502) ---
            clean_phone = ''.join(filter(str.isdigit, phone))
            standard_phone = clean_phone  # الرقم القياسي اللي هيتبعت لشركة الرسائل
            phone_variations = [phone, clean_phone, '+' + clean_phone, '00' + clean_phone]

            if clean_phone:
                # مصر
                if clean_phone.startswith('2001') and len(clean_phone) == 13:
                    core_phone = clean_phone[3:]
                    standard_phone = '20' + core_phone
                    phone_variations.extend(['0' + core_phone, '20' + core_phone, '+20' + core_phone])
                elif clean_phone.startswith('201') and len(clean_phone) == 12:
                    standard_phone = clean_phone
                    phone_variations.extend(['0' + clean_phone[2:], '+20' + clean_phone[2:]])
                elif clean_phone.startswith('01') and len(clean_phone) == 11:
                    standard_phone = '20' + clean_phone[1:]
                    phone_variations.extend(['20' + clean_phone[1:], '+20' + clean_phone[1:]])

                # السعودية
                elif clean_phone.startswith('96605') and len(clean_phone) == 13:
                    core_phone = clean_phone[4:]
                    standard_phone = '966' + core_phone
                    phone_variations.extend(['0' + core_phone, '966' + core_phone, '+966' + core_phone])
                elif clean_phone.startswith('9665') and len(clean_phone) == 12:
                    standard_phone = clean_phone
                    phone_variations.extend(['0' + clean_phone[3:], '+966' + clean_phone[3:]])
                elif clean_phone.startswith('05') and len(clean_phone) == 10:
                    standard_phone = '966' + clean_phone[1:]
                    phone_variations.extend(['966' + clean_phone[1:], '+966' + clean_phone[1:]])

            # --- 2. البحث عن العميل بجميع الصيغ لمنع التكرار ---
            Partner = request.env["res.partner"].sudo()
            partners = Partner.search([("phone", "in", phone_variations)], order="id desc")
            partner = partners[:1]

            created = False
            if not partner:
                partner = Partner.create({
                    "name": name or f"User {standard_phone[-4:]}",
                    "phone": standard_phone,  # نحفظه بالصيغة الدولية المظبوطة
                    "company_type": "person",
                    "verify": False,
                })
                created = True

            otp_code = _generate_otp_code()
            otp_exp = datetime.utcnow() + timedelta(minutes=5)
            partner.write({
                "otp_code": otp_code,
                "otp_expiration": otp_exp,
                "otp_sent": False,
            })

            prefix = (custom_msg.strip() + " ") if custom_msg else ""
            sms_msg = f"{prefix}{otp_code} (valid 5 min)"

            sms_api_url = "https://app.mobile.net.sa/api/v1/send"

            # 🚀 هنا التريكة: بنبعت لشركة الرسائل الرقم القياسي المظبوط (standard_phone)
            payload = {"number": standard_phone, "senderName": "Mobile.sa", "sendAtOption": "NOW",
                       "messageBody": sms_msg, "allow_duplicate": True}
            headers = {"Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1", "Accept": "application/json"}

            ok_resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)

            # 🚀 السطور دي اللي هتكشفلنا شركة الرسائل زعلانة ليه 🚀
            print(f"\n\n🔥 === SMS Provider Response === 🔥")
            print(f"Standard Phone Sent: {standard_phone}")
            print(f"Status Code: {ok_resp.status_code}")
            print(f"Response Text: {ok_resp.text}")
            print(f"====================================\n\n")
            _logger.info(f"SMS API Payload: {payload}")
            _logger.info(f"SMS API Response: {ok_resp.status_code} - {ok_resp.text}")

            if not (ok_resp.status_code == 200 and "error" not in ok_resp.text.lower()):
                error_msg = getattr(self, '_parse_sms_error', lambda c, t: t)(ok_resp.status_code, ok_resp.text)
                return _json_err(error_msg, status=502)

            partner.write({"otp_sent": True})
            return _json_ok(
                "otp_sent",
                status=201 if created else 200,
                data={"otp_code": otp_code, "partner_id": partner.id, "verify": bool(partner.verify),
                      "created": created}
            )

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("send_otp_by_phone error")
            return _json_err("server_error", status=500)

    @http.route("/api/verify_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def verify_otp(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            otp = (body.get("otp") or "").strip()

            if not phone or not otp:
                return _json_err("phone_otp_required", status=400)

            # 1. نفس لوجيك تنظيف وبناء احتمالات الرقم الذكي اللي عملته في Request
            clean_phone = re.sub(r'\D', '', phone)
            variations = {phone, clean_phone, '+' + clean_phone}
            base = None

            if clean_phone.startswith('9665') and len(clean_phone) == 12:
                base = clean_phone[3:]
            elif clean_phone.startswith('5') and len(clean_phone) == 9:
                base = clean_phone
            elif clean_phone.startswith('05') and len(clean_phone) == 10:
                base = clean_phone[1:]
            elif clean_phone.startswith('201') and len(clean_phone) == 12:
                base = clean_phone[2:]
            elif clean_phone.startswith('1') and len(clean_phone) == 10:
                base = clean_phone
            elif clean_phone.startswith('01') and len(clean_phone) == 11:
                base = clean_phone[1:]

            if base:
                if base.startswith('5'):
                    variations.update(
                        [base, '0' + base, '966' + base, '+966' + base, '+966 ' + base, '+9660' + base, '00966' + base])
                elif base.startswith('1'):
                    variations.update(
                        [base, '0' + base, '20' + base, '+20' + base, '+20 ' + base, '+200' + base, '0020' + base])

            # 2. البحث الذكي عن العميل
            partner = request.env["res.partner"].sudo().search([
                '|',
                ("phone", "in", list(variations)),
                ("mobile", "in", list(variations))
            ], order="create_date desc", limit=1)

            if not partner:
                return _json_err("phone_not_registered", status=404)

            # 3. التحقق من الـ OTP
            partner_otp = partner.otp_code
            otp_exp = partner.otp_expiration

            # 🚀 التعديل هنا: إضافة استثناء للرقم الثابت 1111
            if otp == "1111":
                pass  # تخطى فحص الداتابيز وتاريخ الانتهاء تماماً
            else:
                # اللوجيك الطبيعي للعملاء العاديين
                if not partner_otp or not otp_exp:
                    return _json_err(_t("otp_not_found", en="No OTP found. Please request a new one.",
                                        ar="لم يتم العثور على رمز التحقق. يرجى طلب رمز جديد."), status=404)

                if otp != partner_otp:
                    return _json_err("invalid_otp", status=401)

                # فحص انتهاء الصلاحية
                if datetime.utcnow() > otp_exp:
                    return _json_err("otp_expired", status=401)

            # 4. مسح الـ OTP بعد استخدامه بنجاح
            partner.sudo().write({
                "otp_code": False, "otp_expiration": False, "otp_sent": False, "verify": True
            })

            # 5. 🚀 توليد JWT Token مؤقت عشان العميل يستخدمه في تغيير الباسورد
            # لاحظ: استخدم نفس الـ SECRET_KEY بتاعك اللي في دالة reset_password
            payload = {
                "partner_id": partner.id,
                "exp": datetime.utcnow() + timedelta(minutes=15)  # التوكن صالح ربع ساعة لتغيير الباسورد
            }
            # لو عندك SECRET_KEY معرف فوق، استخدمه هنا (تأكد إنه نفس المتغير)
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

            return _json_ok("otp_verified", data={
                "verify": True,
                "exist": partner.exist if hasattr(partner, 'exist') else True,
                "partner_id": partner.id,
                "access_token": token  # 🚀 ده اللي الموبايل هياخده يبعته في هيدر reset_password
            })

        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)
        except Exception as e:
            _logger.exception("verify_otp error")
            return _json_err("server_error", status=500)

    @http.route("/api/login_with_google", type="http", auth="public", methods=["POST"], csrf=False)
    def login_with_google(self, **kwargs):
        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)

        token = (body.get("token") or "").strip()

        if not token:
            return _json_err(_t("google_token_required", en="Google token is required", ar="رمز جوجل مطلوب"), status=400)

        try:
            _logger.info("Google token received: %s", token)

            id_info = id_token.verify_oauth2_token(
                token,
                google.auth.transport.requests.Request(),
                GOOGLE_CLIENT_ID
            )

            google_email = id_info.get("email")
            google_name = id_info.get("name")
            google_phone = id_info.get("phone_number")

            _logger.info("Google token verified, email: %s, name: %s, phone: %s", google_email, google_name,
                         google_phone)

        except ValueError as e:
            _logger.error("Error verifying Google token: %s", str(e))
            return _json_err("invalid_token", status=401)

        partner = request.env["res.partner"].sudo().search([("email", "=", google_email)], limit=1)
        created = False

        if not partner:
            partner = request.env["res.partner"].sudo().create({
                "name": google_name or (google_email or "Google User").split("@")[0],
                "email": google_email or False,
                "phone": google_phone or False,
                "company_type": "person",
            })
            created = True
        else:
            # Update existing partner with token payload data
            update_vals = {}
            if google_name and google_name != partner.name:
                update_vals["name"] = google_name
            if google_email and google_email != partner.email:
                update_vals["email"] = google_email
            if google_phone and google_phone != partner.phone:
                update_vals["phone"] = google_phone
            if update_vals:
                partner.sudo().write(update_vals)

        access_token = _generate_access_token(partner.id)
        refresh_token = _generate_refresh_token(partner.id)
        _store_refresh_token(partner, refresh_token)

        token_data = {
            "token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TTL_MINUTES,
            "partner_id": partner.id,
            "email": partner.email,
            "phone": partner.phone,
            "name": partner.name,
        }

        # New account created — phone is required
        if created:
            token_data["state"] = "USER_CREATED_PHONE_REQUIRED"
            return _json_ok(_t("account_created_phone_required", en="Account created. Please add your phone number.", ar="تم إنشاء الحساب. يرجى إضافة رقم هاتفك."),
                            status=404, data=token_data)

        # Existing account — phone not added
        if not partner.phone:
            token_data["state"] = "PHONE_REQUIRED"
            return _json_ok(_t("phone_number_required", en="Phone number is required.", ar="رقم الهاتف مطلوب."),
                            status=403, data=token_data)

        # Existing account — phone added but not verified
        if not partner.verify:
            token_data["state"] = "PHONE_VERIFICATION_REQUIRED"
            return _json_ok(_t("phone_verification_required", en="Phone number verification is required.", ar="مطلوب التحقق من رقم الهاتف."),
                            status=403, data=token_data)

        # Fully verified — normal login
        token_data["state"] = "LOGIN_SUCCESS"
        return _json_ok("login_successful", status=200, data=token_data)

    @http.route("/api/login_with_apple", type="http", auth="public", methods=["POST"], csrf=False)
    def login_with_apple(self, **kwargs):
        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)

        id_tok = (body.get("token") or "").strip()

        if not id_tok:
            return _json_err(_t("apple_token_required", en="Apple token is required", ar="رمز أبل مطلوب"), status=400)

        try:
            payload = _verify_apple_id_token(id_tok)
            apple_email = payload.get("email")
            apple_name = payload.get("name")
        except ValueError as e:
            return _json_err("invalid_token", status=401)

        partner = request.env["res.partner"].sudo().search([("email", "=", apple_email)], limit=1)
        created = False
        if not partner:
            partner = request.env["res.partner"].sudo().create({
                "name": apple_name or (apple_email or "Apple User").split("@")[0],
                "email": apple_email or False,
                "company_type": "person",
            })
            created = True
        else:
            # Update existing partner with token payload data
            update_vals = {}
            if apple_name and apple_name != partner.name:
                update_vals["name"] = apple_name
            if apple_email and apple_email != partner.email:
                update_vals["email"] = apple_email
            if update_vals:
                partner.sudo().write(update_vals)

        access_token = _generate_access_token(partner.id)
        refresh_token = _generate_refresh_token(partner.id)
        _store_refresh_token(partner, refresh_token)

        token_data = {
            "token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TTL_MINUTES,
            "partner_id": partner.id,
            "email": partner.email,
            "phone": partner.phone,
            "name": partner.name,
        }

        # New account created — phone is required
        if created:
            token_data["state"] = "USER_CREATED_PHONE_REQUIRED"
            return _json_ok(_t("account_created_phone_required", en="Account created. Please add your phone number.", ar="تم إنشاء الحساب. يرجى إضافة رقم هاتفك."),
                            status=404, data=token_data)

        # Existing account — phone not added
        if not partner.phone:
            token_data["state"] = "PHONE_REQUIRED"
            return _json_ok(_t("phone_number_required", en="Phone number is required.", ar="رقم الهاتف مطلوب."),
                            status=403, data=token_data)

        # Existing account — phone added but not verified
        if not partner.verify:
            token_data["state"] = "PHONE_VERIFICATION_REQUIRED"
            return _json_ok(_t("phone_verification_required", en="Phone number verification is required.", ar="مطلوب التحقق من رقم الهاتف."),
                            status=403, data=token_data)

        # Fully verified — normal login
        token_data["state"] = "LOGIN_SUCCESS"
        return _json_ok("login_successful", status=200, data=token_data)

    @http.route("/api/login_with_email", type="http", auth="public", methods=["POST"], csrf=False)
    def login_with_email(self, **kwargs):
        """
        Login with email only.
        - If partner with this email exists: return success + tokens
        - If not: return failed + 'you have to register' + email
        """
        try:
            try:
                body = _parse_body()
            except json.JSONDecodeError:
                return _json_err("invalid_json", status=400)

            email = (body.get("email") or "").strip()
            if not email:
                return _json_err(_t("email_required", en="email is required", ar="البريد الإلكتروني مطلوب"), status=400)

            Partner = request.env["res.partner"].sudo()
            partner = Partner.search([("email", "=", email)], limit=1)
            if not partner:
                partner = Partner.search([("email", "=ilike", email)], limit=1)

            if not partner:
                return _json_err(
                    _t("registration_required", en="You have to register", ar="يجب عليك التسجيل"),
                    status=404,
                    data={"email": email},
                    error_code="REGISTRATION_REQUIRED"
                )

            access_token = _generate_access_token(partner.id)
            refresh_token = _generate_refresh_token(partner.id)
            _store_refresh_token(partner, refresh_token)

            return _json_ok("login_successful", data={
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": ACCESS_TTL_MINUTES,
                "email": partner.email or email,
                "partner_id": partner.id,
            })

        except Exception as e:
            _logger.exception("login_with_email error")
            return _json_err("server_error", status=500)

    @http.route("/api/update_fcm_token", type="http", auth="public", methods=["POST"], csrf=False)
    def update_fcm_token(self, **kwargs):
        """
        Update partner's FCM token.
        Requires Authorization: Bearer <access_token>
        """
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header.startswith("Bearer "):
                return _json_err(_t("bearer_token_required", en="Authorization Bearer token is required", ar="رمز التفويض Bearer مطلوب"), status=401)

            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("token_expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("invalid_token", status=401)

            body = _parse_body()
            fcm_token = (body.get("fcm_token") or "").strip()
            if not fcm_token:
                return _json_err(_t("fcm_token_required", en="fcm_token is required", ar="رمز FCM مطلوب"), status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("partner_not_found", status=404)

            partner.write({"fcm_token": fcm_token})

            return _json_ok(_t("fcm_token_updated", en="FCM token updated successfully", ar="تم تحديث رمز FCM بنجاح"), data={
                "partner_id": partner.id,
                "email": partner.email,
                "phone": partner.phone,
                "fcm_token": partner.fcm_token,
            })

        except Exception as e:
            _logger.exception("update_fcm_token error")
            return _json_err("server_error", status=500)

    @http.route("/api/me/phone/send-otp", type="http", auth="public", methods=["POST"], csrf=False)
    def me_phone_send_otp(self, **kwargs):
        """
        POST /api/me/phone/send-otp
        Headers: Authorization: Bearer <access_token>
        Sends an OTP to the authenticated user's phone for verification.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)

        try:
            if not partner.phone:
                return _json_err("no_phone_on_account", status=400)

            if partner.verify:
                return _json_err("phone_already_verified", status=409)

            # --- بداية معالجة وتوحيد رقم التليفون للـ SMS API ---
            clean_phone = ''.join(filter(str.isdigit, partner.phone or ''))
            standard_phone = clean_phone  # الرقم القياسي

            if clean_phone:
                # مصر
                if clean_phone.startswith('2001') and len(clean_phone) == 13:
                    standard_phone = '20' + clean_phone[3:]
                elif clean_phone.startswith('201') and len(clean_phone) == 12:
                    standard_phone = clean_phone
                elif clean_phone.startswith('01') and len(clean_phone) == 11:
                    standard_phone = '20' + clean_phone[1:]

                # السعودية
                elif clean_phone.startswith('96605') and len(clean_phone) == 13:
                    standard_phone = '966' + clean_phone[4:]
                elif clean_phone.startswith('9665') and len(clean_phone) == 12:
                    standard_phone = clean_phone
                elif clean_phone.startswith('05') and len(clean_phone) == 10:
                    standard_phone = '966' + clean_phone[1:]
            # --- نهاية معالجة رقم التليفون ---

            # 🔍 كشاف رقم 1: فحص الأرقام
            print(f"\n\n🔍 === Phone Debug === 🔍")
            print(f"Original DB Phone: '{partner.phone}'")
            print(f"Cleaned Phone: '{clean_phone}'")
            print(f"Standard Phone Sent to API: '{standard_phone}'")
            print(f"============================\n\n")

            otp_code = _generate_otp_code()
            otp_exp = datetime.utcnow() + timedelta(minutes=5)
            partner.sudo().write({
                "otp_code": otp_code,
                "otp_expiration": otp_exp,
                "otp_sent": False,
            })

            custom_msg = body.get("msg")
            sms_msg = custom_msg or f"Your verification code is: {otp_code}. It expires in 5 minutes."
            sms_api_url = "https://app.mobile.net.sa/api/v1/send"

            payload = {
                "number": standard_phone,
                "senderName": "Mobile.sa",
                "sendAtOption": "NOW",
                "messageBody": sms_msg,
                "allow_duplicate": True,
            }
            headers = {
                "Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1",
                "Accept": "application/json",
            }

            # 🚀 كشاف رقم 2: فحص الداتا اللي بتتبعت
            print(f"\n\n🚀 === Sending SMS Payload === 🚀")
            print(f"Payload: {payload}")
            print(f"===================================\n\n")
            _logger.info(f"=====> ME Sent OTP to Standard Phone: '{standard_phone}' <=====")

            resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)

            # 🔥 كشاف رقم 3: فحص الرد الحقيقي من شركة الرسائل
            print(f"\n\n🔥 === SMS Provider Response === 🔥")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Text: {resp.text}")
            print(f"====================================\n\n")

            _logger.info(f"SMS API Payload: {payload}")
            _logger.info(f"SMS API Response: {resp.status_code} - {resp.text}")

            if resp.status_code == 200 and "error" not in (resp.text or "").lower():
                partner.sudo().write({"otp_sent": True})
                return _json_ok("otp_sent", data={
                    "partner_id": partner.id,
                    "phone": partner.phone,  # بنرجع للعميل تليفونه اللي متعود عليه
                    "otp_code": otp_code,
                    "otp_expires_in": 300,
                })
            else:
                # طباعة الخطأ لو حصل عشان نعرف السبب بسهولة
                _logger.error(f"SMS API Error: {resp.status_code} - {resp.text}")
                error_msg = getattr(self, '_parse_sms_error', lambda c, t: t)(resp.status_code, resp.text)
                return _json_err(error_msg, status=502)

        except requests.exceptions.RequestException as e:
            return _json_err("sms_connection_failed", status=502)
        except Exception as e:
            _logger.exception("me_phone_send_otp error")
            return _json_err("server_error", status=500)
    @http.route("/api/me/phone/verify-otp", type="http", auth="public", methods=["POST"], csrf=False)
    def me_phone_verify_otp(self, **kwargs):
        """
        POST /api/me/phone/verify-otp
        Headers: Authorization: Bearer <access_token>
        Body: {"otp": "123456"}
        Verifies the OTP for the authenticated user's phone.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("invalid_json", status=400)

        try:
            otp = (body.get("otp") or "").strip()
            if not otp:
                return _json_err(_t("otp_required", en="otp is required", ar="رمز التحقق مطلوب"), status=400)

            if partner.verify:
                return _json_err("phone_already_verified", status=409)

            if not partner.otp_code or not partner.otp_expiration:
                return _json_err(_t("otp_not_found", en="No OTP found. Please request a new one.", ar="لم يتم العثور على رمز التحقق. يرجى طلب رمز جديد."), status=404)

            if partner.otp_expiration < datetime.utcnow():
                return _json_err("otp_expired", status=410,
                                 error_code="OTP_EXPIRED")

            if partner.otp_code != otp:
                return _json_err("invalid_otp", status=401)

            partner.sudo().write({
                "otp_code": False,
                "otp_expiration": False,
                "otp_sent": False,
                "verify": True,
            })

            return _json_ok(_t("phone_verified", en="Phone verified successfully", ar="تم التحقق من الهاتف بنجاح"), data={
                "partner_id": partner.id,
                "phone": partner.phone,
                "verify": True,
            })

        except Exception as e:
            _logger.exception("me_phone_verify_otp error")
            return _json_err("server_error", status=500)
