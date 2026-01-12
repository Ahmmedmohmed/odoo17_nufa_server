from odoo import http
from odoo.http import request, Response
import requests
import random
import json
import jwt
from datetime import datetime, timedelta
import google.auth.transport.requests
from google.oauth2 import id_token
import os, uuid
import logging

_logger = logging.getLogger(__name__)

SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

GOOGLE_CLIENT_ID = "1076496866609-j3uk7icpg9015f1iih9cpua5gh07s3lm.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = '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'

REFRESH_SECRET_KEY = os.getenv("ODOO_REFRESH_SECRET_KEY", SECRET_KEY)
ACCESS_TTL_MINUTES = 240
REFRESH_TTL_DAYS = 14

APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID", "com.noufapps.noufbeauty.service")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID", "37XX3D6WSB")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID", "DLM8PL34ZD")
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

SECRET_KEY = os.getenv("APP_JWT_SECRET", "bcf2e5f933a069b6d737d5cc0a7af01b")


def _json_ok(message="OK", data=None, status=200):
    return Response(json.dumps({
        "status": "success", "message": message, "data": data or {}
    }), status=status, content_type="application/json")


def _json_err(message, status=400, data=None, error_code=None):
    payload = {"status": "failed", "message": message, "data": data or {}}
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
    payload = {
        "partner_id": partner_id,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TTL_MINUTES),
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
                return _json_err("phone is required", status=400)

            if partner_id_from_request:
                partner = request.env["res.partner"].sudo().browse(int(partner_id_from_request))
                if not partner.exists():
                    return _json_err("Partner not found", status=404)
            else:
                existing = request.env["res.partner"].sudo().search(
                    [("phone", "=", phone), ("email", "=", email), ("verify", "=", True)], limit=1
                )
                if existing:
                    return _json_err(
                        "Phone number already exists and verified",
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

            otp_code = str(random.randint(100000, 999999))
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
                        return _json_err(f"SMS API error: {resp.status_code} {resp.text}", status=502)
                except requests.exceptions.RequestException as e:
                    return _json_err(f"SMS API error: {str(e)}", status=502)

            return _json_ok(
                "Partner created or updated; OTP generated" + (" and sent" if otp_sent else ""),
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
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("create_partner error")
            return _json_err(str(e), status=500)

    @http.route("/api/generate_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def generate_otp(self, **kwargs):
        try:
            body = _parse_body()
            partner_id = body.get("partner_id")
            if not partner_id:
                return _json_err("partner_id is required", status=400)

            partner = request.env["res.partner"].sudo().browse(int(partner_id))
            if not partner.exists():
                return _json_err("Partner not found", status=404)

            otp_code = str(random.randint(100000, 999999))
            partner.sudo().write({
                "otp_code": otp_code,
                "otp_expiration": datetime.utcnow() + timedelta(minutes=5),
                "otp_sent": False,
            })

            return _json_ok("OTP generated", data={
                "partner_id": partner.id,
                "otp_code": otp_code,
                "expires_in": 300,
            })

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("generate_otp error")
            return _json_err(str(e), status=500)

    @http.route("/api/send_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def send_otp(self, **kwargs):
        try:
            body = _parse_body()
            partner_id = body.get("partner_id")
            phone = (body.get("phone") or "").strip()
            msg = body.get("msg")

            if not partner_id and not phone:
                return _json_err("partner_id or phone is required", status=400)

            partner = None
            otp_code = None
            if partner_id:
                partner = request.env["res.partner"].sudo().browse(int(partner_id))
                if not partner.exists():
                    return _json_err("Partner not found", status=404)
                phone = partner.phone
                if not phone:
                    return _json_err("Partner has no phone number", status=409)
                otp_code = partner.otp_code
                if not otp_code:
                    return _json_err("OTP not generated yet", status=409)
                if partner.otp_sent:
                    return _json_err("OTP already sent", status=409)

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
                return _json_ok({"message": "OTP sent successfully", "otp_code": otp_code})
            return _json_err(f"SMS API error: {resp.status_code} {resp.text}", status=502)

        except requests.exceptions.RequestException as e:
            return _json_err(f"SMS API error: {str(e)}", status=502)
        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("send_otp error")
            return _json_err(str(e), status=500)



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
            password = (body.get("password") or "").strip()
            otp = (body.get("otp") or "").strip()
            partner_id_from_request = body.get("partner_id")

            if not phone or (not password and not otp):
                return _json_err("Phone and either password or OTP are required", status=400)

            if partner_id_from_request:
                partner = request.env["res.partner"].sudo().search([("id", "=", partner_id_from_request)], limit=1)
            else:
                partner = request.env["res.partner"].sudo().search([("phone", "=", phone)],
                                                                   limit=1)
            if otp:
                if (partner.otp_code or "") != otp:
                    return _json_err("Invalid OTP", status=401)
                partner.sudo().write({'verify': True})

            if not partner.password and partner_id_from_request:
                return _json_err("You need to register first. Please set a password to proceed.", status=403)

            if not partner.password :
                return _json_err("You need to register first. Please set a password to proceed.", status=403)

            if not partner.verify:
                partner.sudo().write({'verify': True})

            if not partner:
                return _json_err("Partner not found or not verified", status=404)

            if not partner.verify and not partner_id_from_request:
                return _json_err("Account not verified. Please verify your account first.", status=403)

            if otp and (partner.otp_code or "") != otp:
                return _json_err("Invalid OTP", status=401)



            if password and (partner.password or "") != password:
                return _json_err("Invalid password", status=401)

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

            return _json_ok("Login successful", data=response_data)

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("login error")
            return _json_err(str(e), status=500)

    @http.route("/api/reset_password", type="http", auth="public", methods=["POST"], csrf=False)
    def reset_password(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header:
                return _json_err("Authorization header is required", status=401)
            token = auth_header.split(" ")[1] if " " in auth_header else None
            if not token:
                return _json_err("Token not found in the Authorization header", status=401)

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("Token has expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("Invalid token", status=401)

            body = _parse_body()
            old_password = (body.get("old_password") or "").strip()
            new_password = (body.get("new_password") or "").strip()
            confirm_password = (body.get("confirm_password") or "").strip()

            if not old_password or not new_password or not confirm_password:
                return _json_err("Old password, new password, and confirm password are required", status=400)
            if new_password != confirm_password:
                return _json_err("New password and confirm password do not match", status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("Partner not found", status=404)
            if (partner.password or "") != old_password:
                return _json_err("Old password is incorrect", status=401)

            partner.sudo().write({"password": new_password})
            return _json_ok("Password reset successful", data={"otp_code": partner.otp_code})

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("reset_password error")
            return _json_err(str(e), status=500)

    @http.route("/api/forgot_password/request", type="http", auth="public", methods=["POST"], csrf=False)
    def forgot_password_request(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            custom_msg = body.get("msg")

            if not phone:
                return _json_err("phone is required", status=400)

            partner = request.env["res.partner"].sudo().search([("phone", "=", phone)], limit=1)
            if not partner:
                return _json_err("Phone number not registered", status=404)

            otp_code = str(random.randint(100000, 999999))
            partner.sudo().write({
                "otp_code": otp_code,
                "otp_expiration": datetime.utcnow() + timedelta(minutes=5),
                "otp_sent": False,
            })

            sms_msg = custom_msg or f"Your password reset OTP is: {otp_code}. It expires in 5 minutes."
            sms_api_url = "https://app.mobile.net.sa/api/v1/send"
            payload = {"number": phone, "senderName": "Mobile.sa", "sendAtOption": "NOW",
                       "messageBody": sms_msg, "allow_duplicate": False}
            headers = {"Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1", "Accept": "application/json"}

            ok_resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)
            if not (ok_resp.status_code == 200 and "error" not in ok_resp.text.lower()):
                return _json_err(f"SMS API error: {ok_resp.status_code} {ok_resp.text}", status=502)

            partner.sudo().write({"otp_sent": True})
            return _json_ok("OTP sent successfully",
                            data={"otp_code": otp_code, "expires_in": 300})

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("forgot_password_request error")
            return _json_err(str(e), status=500)

    @http.route("/api/forgot_password/confirm", type="http", auth="public", methods=["POST"], csrf=False)
    def forgot_password_confirm(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            new_password = (body.get("new_password") or "").strip()
            confirm_password = (body.get("confirm_password") or "").strip()

            if not phone or not new_password or not confirm_password:
                return _json_err("phone, new_password, confirm_password are required", status=400)
            if new_password != confirm_password:
                return _json_err("new_password and confirm_password do not match", status=400)

            partner = request.env["res.partner"].sudo().search([("phone", "=", phone), ("verify", "=", True)], limit=1)
            if not partner:
                return _json_err("Phone number not registered", status=404)

            partner.sudo().write({"password": new_password})
            return _json_ok("Password has been reset successfully")

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("forgot_password_confirm error")
            return _json_err(str(e), status=500)

    @http.route("/api/logout", type="http", auth="public", methods=["POST"], csrf=False)
    def logout(self, **kwargs):
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header:
                return _json_err("Authorization header is required", status=401)
            token = auth_header.split(" ")[1] if " " in auth_header else None
            if not token:
                return _json_err("Token not found in the Authorization header", status=401)

            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("Token has expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("Invalid token", status=401)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("Partner not found", status=404)

            partner.sudo().write({"fcm_token": False})
            return _json_ok("Logged out successfully, FCM token cleared")

        except Exception as e:
            _logger.exception("logout error")
            return _json_err(str(e), status=500)

    @http.route("/api/auth/refresh", type="http", auth="public", methods=["POST"], csrf=False)
    def auth_refresh(self, **kwargs):
        try:
            try:
                body = _parse_body()
            except json.JSONDecodeError:
                return _json_err("Invalid JSON payload", status=400)

            refresh_token = (body.get("refresh_token") or "").strip()
            _logger.info("REFRESH incoming len=%s head=%s", len(refresh_token or ""), (refresh_token or "")[:40])
            if not refresh_token:
                return _json_err("refresh_token is required", status=400)

            try:
                payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=["HS256"])
                _logger.info("REFRESH payload: %s", payload)
            except jwt.ExpiredSignatureError:
                return _json_err("Refresh token has expired", status=401)
            except jwt.InvalidTokenError as e:
                _logger.warning("REFRESH decode failed: %s", e)
                return _json_err("Invalid refresh token", status=401)

            if payload.get("type") != "refresh":
                return _json_err("Invalid token type", status=401)

            partner_id = payload.get("partner_id")
            if not partner_id:
                return _json_err("Invalid payload: missing partner_id", status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("Partner not found", status=404)

            ok, err = _validate_stored_refresh_token(partner, refresh_token)
            if not ok:
                _logger.warning("REFRESH validation failed: %s", err)
                return _json_err(err, status=401)

            new_access = _generate_access_token(partner.id)
            new_refresh = _generate_refresh_token(partner.id)
            _store_refresh_token(partner, new_refresh)
            _logger.info("REFRESH success for partner %s", partner.id)

            return _json_ok("Token refreshed", data={
                "token": new_access,
                "refresh_token": new_refresh,
                "expires_in": ACCESS_TTL_MINUTES
            })

        except Exception as e:
            _logger.exception("auth_refresh error")
            return _json_err(str(e), status=500)

    @http.route("/api/send_otp_by_phone", type="http", auth="public", methods=["POST"], csrf=False)
    def send_otp_by_phone(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            custom_msg = body.get("msg")
            name = (body.get("name") or "").strip()

            if not phone:
                return _json_err("phone is required", status=400)

            Partner = request.env["res.partner"].sudo()
            partner = Partner.search([("phone", "=", phone)], limit=1)
            created = False
            if not partner:
                partner = Partner.create({
                    "name": name or f"User {phone[-4:]}",
                    "phone": phone,
                    "company_type": "person",
                    "verify": False,
                })
                created = True

            otp_code = str(random.randint(100000, 999999))
            otp_exp = datetime.utcnow() + timedelta(minutes=5)
            partner.write({
                "otp_code": otp_code,
                "otp_expiration": otp_exp,
                "otp_sent": False,
            })

            prefix = (custom_msg.strip() + " ") if custom_msg else ""
            sms_msg = f"{prefix}{otp_code} (valid 5 min)"

            sms_api_url = "https://app.mobile.net.sa/api/v1/send"
            payload = {"number": phone, "senderName": "Mobile.sa", "sendAtOption": "NOW",
                       "messageBody": sms_msg, "allow_duplicate": False}
            headers = {"Authorization": "Bearer akdSxPseY1LbaFJUiep5gsxa1Vhxg5YCBepu6Tj1", "Accept": "application/json"}
            ok_resp = requests.post(sms_api_url, json=payload, headers=headers, timeout=15)
            if not (ok_resp.status_code == 200 and "error" not in ok_resp.text.lower()):
                return _json_err(f"SMS API error: {ok_resp.status_code} {ok_resp.text}", status=502)

            partner.write({"otp_sent": True})
            return _json_ok(
                "OTP sent successfully",
                status=201 if created else 200,
                data={"otp_code": otp_code, "partner_id": partner.id, "verify": bool(partner.verify),
                      "created": created}
            )

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("send_otp_by_phone error")
            return _json_err(str(e), status=500)

    @http.route("/api/verify_otp", type="http", auth="public", methods=["POST"], csrf=False)
    def verify_otp(self, **kwargs):
        try:
            body = _parse_body()
            phone = (body.get("phone") or "").strip()
            otp = (body.get("otp") or "").strip()

            if not phone or not otp:
                return _json_err("phone and otp are required", status=400)

            partner = request.env["res.partner"].sudo().search(
                [("phone", "=", phone)], order="create_date desc", limit=1
            )
            if not partner:
                return _json_err("Phone number not registered", status=404)

            if not partner.password:
                return _json_err("You need to register first. Please set a password to proceed.", status=400)

            partner_otp = partner.otp_code
            otp_exp = partner.otp_expiration
            if not partner_otp or not otp_exp:
                return _json_err("No OTP found. Please request a new one.", status=404)

            if otp != partner_otp:
                return _json_err("Invalid OTP", status=401)

            partner.sudo().write({
                "otp_code": False, "otp_expiration": False, "otp_sent": False, "verify": True
            })

            return _json_ok("OTP verified successfully", data={
                "verify": True,
                "exist": partner.exist,
                "partner_id": partner.id,
            })

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("verify_otp error")
            return _json_err(str(e), status=500)

    @http.route("/api/login_with_google", type="http", auth="public", methods=["POST"], csrf=False)
    def login_with_google(self, **kwargs):
        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)

        token = (body.get("token") or "").strip()

        if not token:
            return _json_err("Google token is required", status=400)

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
            return _json_err("Invalid token", status=401)

        partner = request.env["res.partner"].sudo().search([("email", "=", google_email)], limit=1)

        if not partner:
            return _json_err(f"Email {google_email} does not exist in the system", status=404,
                             data={"email": google_email})

        if google_phone:
            partner.sudo().write({"phone": google_phone})

        access_token = _generate_access_token(partner.id)
        refresh_token = _generate_refresh_token(partner.id)
        _store_refresh_token(partner, refresh_token)

        return _json_ok("Login successful", status=200, data={
            "token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TTL_MINUTES,
            "partner_id": partner.id,
            "email": partner.email,
            "phone": partner.phone,
        })

    @http.route("/api/login_with_apple", type="http", auth="public", methods=["POST"], csrf=False)
    def login_with_apple(self, **kwargs):
        try:
            body = _parse_body()
        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)

        id_tok = (body.get("token") or "").strip()
        name_override = (body.get("name") or "").strip()

        if not id_tok:
            return _json_err("Apple token is required", status=400)

        try:
            payload = _verify_apple_id_token(id_tok)
            apple_email = payload.get("email")
        except ValueError as e:
            return _json_err(str(e), status=401)

        partner = request.env["res.partner"].sudo().search([("email", "=", apple_email)], limit=1)
        created = False
        if not partner:
            partner = request.env["res.partner"].sudo().create({
                "name": name_override or (apple_email or f"Apple User").split("@")[0],
                "email": apple_email or False,
                "company_type": "person",
            })
            created = True

        access_token = _generate_access_token(partner.id)
        refresh_token = _generate_refresh_token(partner.id)
        _store_refresh_token(partner, refresh_token)

        return _json_ok("Login successful", status=201 if created else 200, data={
            "token": access_token,
            "refresh_token": refresh_token,
            "expires_in": ACCESS_TTL_MINUTES,
            "created": created,
            "partner_id": partner.id,
            "email": partner.email,
        })

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
                return _json_err("Invalid JSON payload", status=400)

            email = (body.get("email") or "").strip()
            if not email:
                return _json_err("email is required", status=400)

            Partner = request.env["res.partner"].sudo()
            partner = Partner.search([("email", "=", email)], limit=1)
            if not partner:
                partner = Partner.search([("email", "=ilike", email)], limit=1)

            if not partner:
                return _json_err(
                    "You have to register",
                    status=404,
                    data={"email": email},
                    error_code="REGISTRATION_REQUIRED"
                )

            access_token = _generate_access_token(partner.id)
            refresh_token = _generate_refresh_token(partner.id)
            _store_refresh_token(partner, refresh_token)

            return _json_ok("Login successful", data={
                "token": access_token,
                "refresh_token": refresh_token,
                "expires_in": ACCESS_TTL_MINUTES,
                "email": partner.email or email,
                "partner_id": partner.id,
            })

        except Exception as e:
            _logger.exception("login_with_email error")
            return _json_err(str(e), status=500)

    @http.route("/api/update_fcm_token", type="http", auth="public", methods=["POST"], csrf=False)
    def update_fcm_token(self, **kwargs):
        """
        Update partner's FCM token.
        Requires Authorization: Bearer <access_token>
        """
        try:
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if not auth_header.startswith("Bearer "):
                return _json_err("Authorization Bearer token is required", status=401)

            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
            except jwt.ExpiredSignatureError:
                return _json_err("Token has expired", status=401)
            except jwt.InvalidTokenError:
                return _json_err("Invalid token", status=401)

            body = _parse_body()
            fcm_token = (body.get("fcm_token") or "").strip()
            if not fcm_token:
                return _json_err("fcm_token is required", status=400)

            partner = request.env["res.partner"].sudo().browse(partner_id)
            if not partner.exists():
                return _json_err("Partner not found", status=404)

            partner.write({"fcm_token": fcm_token})

            return _json_ok("FCM token updated successfully", data={
                "partner_id": partner.id,
                "email": partner.email,
                "phone": partner.phone,
                "fcm_token": partner.fcm_token,
            })

        except Exception as e:
            _logger.exception("update_fcm_token error")
            return _json_err(str(e), status=500)
