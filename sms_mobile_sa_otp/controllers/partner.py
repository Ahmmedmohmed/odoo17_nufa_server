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

def _json(payload, status=200):
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        content_type="application/json; charset=utf-8",
    )

def _base_url():
    return request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''

def _partner_from_access_token():
    """
    Read Authorization header, decode HS256 access token, return partner record.
    Returns (partner, error_response) where error_response is an HTTP Response if anything fails.
    """
    auth = request.httprequest.headers.get("Authorization")
    if not auth:
        return None, _json({"error": "Authorization header is required"}, 401)

    token = auth.split(" ")[1] if " " in auth else auth
    if not token:
        return None, _json({"error": "Token not found in Authorization header"}, 401)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") and payload.get("type") != "access":
            return None, _json({"error": "Invalid token type"}, 401)

        partner = request.env["res.partner"].sudo().browse(payload.get("partner_id"))
        if not partner.exists():
            return None, _json({"error": "Partner not found"}, 401)
        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json({"error": "Token has expired"}, 401)
    except jwt.InvalidTokenError:
        return None, _json({"error": "Invalid token"}, 401)
    except Exception as e:
        return None, _json({"error": str(e)}, 400)

def _serialize_partner(p):
    return {
        "id": p.id,
        "name": p.name or "",
        "phone": p.phone or "",
        # "email": p.email or "",
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
