# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json, jwt

SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

def _json(payload, status=200):
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        content_type="application/json; charset=utf-8",
    )

def _require_jwt_and_partner():
    auth = request.httprequest.headers.get("Authorization")
    if not auth:
        return None, _json({"error": "Authorization header is required"}, 401)
    token = auth.split(" ")[1] if " " in auth else None
    if not token:
        return None, _json({"error": "Token not found in Authorization header"}, 401)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
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

def _base_url():
    return request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''

def _serialize_sub_color(sc):
    return {"id": sc.id, "color_hex": sc.color_hex}

def _serialize_color(c):
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description or "",
        "sub_colors": [_serialize_sub_color(sc) for sc in c.sub_color_ids],
        "sub_color_hex_values": c.sub_color_hex_values or "",
    }

def _serialize_img(img):
    return {
        "id": img.id,
        "url": f"{_base_url()}/web/image?model=img&id={img.id}&field=img"
    }

def _serialize_app_main(m):
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "colors": [_serialize_color(c) for c in m.color_ids],
        "images": [_serialize_img(i) for i in m.img_ids],
    }

class AppReadOnlyApiController(http.Controller):

    @http.route("/api/app/main/default", type="http", auth="public", methods=["GET"], csrf=False)
    def app_main_all(self, **kwargs):
        mains = request.env["app.main"].sudo().search([], order="id desc")
        if not mains:
            return _json({"error": "No App Main found"}, 404)

        return _json({
            "count": len(mains),
            "results": [_serialize_app_main(m) for m in mains],
        })



# class AppReadOnlyApiController(http.Controller):
#
#     @http.route("/api/app/main/default", type="http", auth="public", methods=["GET"], csrf=False)
#     def app_main_all(self, **kwargs):
#         _, err = _require_jwt_and_partner()
#         if err:
#             return err
#
#         mains = request.env["app.main"].sudo().search([], order="id desc")
#         if not mains:
#             return _json({"error": "No App Main found"}, 404)
#
#         return _json({
#             "count": len(mains),
#             "results": [_serialize_app_main(m) for m in mains],
#         })

    # @http.route("/api/app/main/<int:rec_id>", type="http", auth="public", methods=["GET"], csrf=False)
    # def app_main_read_one(self, rec_id, **kwargs):
    #     _, err = _require_jwt_and_partner()
    #     if err:
    #         return err
    #
    #     main = request.env["app.main"].sudo().browse(rec_id)
    #     if not main.exists():
    #         return _json({"error": "App Main not found"}, 404)
    #
    #     return _json(_serialize_app_main(main))
