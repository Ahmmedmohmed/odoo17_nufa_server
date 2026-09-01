# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.wrappers import Response
import json
import jwt
import logging

_logger = logging.getLogger(__name__)
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"


# =================================================================
# دوال الـ JWT الأساسية للتحقق
# =================================================================
def _json_err(msg, status=400):
    return Response(json.dumps({"status": "failed", "message": msg, "data": {}}),
                    status=status, content_type="application/json")


def _partner_from_token():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err("Authorization Bearer token is required", 401)
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner = request.env["res.partner"].sudo().browse(payload.get("partner_id"))
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


class MobileNotificationsAPI(http.Controller):

    # --- دالة مساعدة للرد بصيغة JSON ---
    def _http_json(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers={'Content-Type': 'application/json'},
            status=status
        )

    # --- دالة مساعدة لجلب اللغة من الهيدر ---
    def _get_lang_context(self):
        header_lang = request.httprequest.headers.get('lang', 'en').lower()
        return 'ar_001' if header_lang == 'ar' else 'en_US'

    # =================================================================
    # 1. جلب كل الإشعارات
    # =================================================================
    @http.route('/api/notifications/all', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_notifications(self, **kwargs):
        try:
            partner, err_response = _partner_from_token()
            if err_response:
                return err_response

            header_lang = request.httprequest.headers.get('lang', 'en').lower()
            odoo_lang = 'ar_001' if header_lang == 'ar' else 'en_US'

            user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            user_id = user.id if user else 0

            domain = ['|', ('partner', '=', partner.id), ('employee_id.user_id', '=', user_id)]

            NotificationsModel = request.env['notifications.model'].sudo().with_context(lang=odoo_lang)
            notifs = NotificationsModel.search(domain, order='id desc')

            noti_type_selection = dict(NotificationsModel.fields_get(['noti_type'])['noti_type']['selection'])

            data = []
            for n in notifs:
                title = n.content_ar if header_lang == 'ar' else n.content_en
                body = n.sub_content_ar if header_lang == 'ar' else n.sub_content_en
                type_display = noti_type_selection.get(n.noti_type, n.noti_type)

                data.append({
                    'id': n.id,
                    'title': title or "",
                    'body': body or "",
                    'type': type_display or "",
                    'date': str(n.date) if n.date else "",
                    'is_read': n.read_noti
                })

            msg = "تم جلب الإشعارات بنجاح" if odoo_lang == 'ar_001' else "All notifications fetched successfully"
            return self._http_json({'status': True, 'message': msg, 'data': data}, 200)

        except Exception as e:
            _logger.exception("Error in get_all_notifications")
            return self._http_json({'status': False, 'message': str(e)}, 500)

    # =================================================================
    # 2. جلب الإشعارات المقروءة فقط
    # =================================================================
    @http.route('/api/notifications/read', type='http', auth='public', methods=['GET'], csrf=False)
    def get_read_notifications(self, **kwargs):
        try:
            partner, err_response = _partner_from_token()
            if err_response:
                return err_response

            header_lang = request.httprequest.headers.get('lang', 'en').lower()
            odoo_lang = 'ar_001' if header_lang == 'ar' else 'en_US'

            user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            user_id = user.id if user else 0

            domain = [
                ('read_noti', '=', True),
                '|', ('partner', '=', partner.id), ('employee_id.user_id', '=', user_id)
            ]
            NotificationsModel = request.env['notifications.model'].sudo().with_context(lang=odoo_lang)
            notifs = NotificationsModel.search(domain, order='id desc')

            noti_type_selection = dict(NotificationsModel.fields_get(['noti_type'])['noti_type']['selection'])

            data = []
            for n in notifs:
                # 🚀 تحديث الحقول هنا كمان للنسخة الجديدة المترجمة
                title = n.content_ar if header_lang == 'ar' else n.content_en
                body = n.sub_content_ar if header_lang == 'ar' else n.sub_content_en
                type_display = noti_type_selection.get(n.noti_type, n.noti_type)

                data.append({
                    'id': n.id,
                    'title': title or "",
                    'body': body or "",
                    'type': type_display or "",
                    'date': str(n.date) if n.date else "",
                    'is_read': n.read_noti
                })

            msg = "تم جلب الإشعارات المقروءة بنجاح" if odoo_lang == 'ar_001' else "Read notifications fetched successfully"
            return self._http_json({'status': True, 'message': msg, 'data': data}, 200)

        except Exception as e:
            _logger.exception("Error in get_read_notifications")
            return self._http_json({'status': False, 'message': str(e)}, 500)

    # =================================================================
    # 3. تحويل حالة الإشعار إلى "تمت القراءة"
    # =================================================================
    @http.route('/api/notifications/mark_read', type='http', auth='public', methods=['POST'], csrf=False)
    def mark_notification_read(self, **kwargs):
        try:
            partner, err_response = _partner_from_token()
            if err_response:
                return err_response

            odoo_lang = self._get_lang_context()
            user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            user_id = user.id if user else 0

            try:
                data = json.loads(request.httprequest.data or '{}')
            except:
                data = kwargs

            notification_id = data.get('notification_id')

            if not notification_id:
                msg = "رقم الإشعار مطلوب" if odoo_lang == 'ar_001' else "notification_id is required"
                return self._http_json({'status': False, 'message': msg}, 400)

            domain = [
                ('id', '=', int(notification_id)),
                '|', ('partner', '=', partner.id), ('employee_id.user_id', '=', user_id)
            ]
            notification = request.env['notifications.model'].sudo().search(domain, limit=1)

            if not notification:
                msg = "الإشعار غير موجود أو لا تملك صلاحية" if odoo_lang == 'ar_001' else "Notification not found or access denied"
                return self._http_json({'status': False, 'message': msg}, 404)

            notification.sudo().write({'read_noti': True})

            msg = "تم تحديد الإشعار كمقروء" if odoo_lang == 'ar_001' else "Notification marked as read successfully"
            return self._http_json({
                'status': True,
                'message': msg,
                'notification_id': notification.id
            }, 200)

        except Exception as e:
            _logger.exception("Error in mark_notification_read")
            return self._http_json({'status': False, 'message': str(e)}, 500)