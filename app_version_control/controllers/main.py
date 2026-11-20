# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class MobileAppConfigController(http.Controller):

    @http.route('/api/app/control_config', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_mobile_app_config(self, **kw):
        """
        Endpoint للموبايل يسحب الإعدادات بصيغة JSON حقيقية وبدون تعقيد JSON-RPC
        """
        # بنجيب آخر إعدادات للأندرويد والآيفون
        android = request.env['mobile.app.config'].sudo().search([('platform', '=', 'android')], limit=1,
                                                                 order='write_date desc')
        ios = request.env['mobile.app.config'].sudo().search([('platform', '=', 'ios')], limit=1,
                                                             order='write_date desc')

        # تجهيز البيانات
        data = {
            "meta": {
                "updated_at": android.write_date.isoformat() if android else "",
                "updated_by": android.updated_by.name if android else "System",
                "change_reason": android.change_reason or "Initial setup"
            },
            "android": {
                "exact_blocked_version": android.exact_blocked_version or "",
                "min_supported_version": android.min_supported_version or "",
                "maintenance_mode": android.maintenance_mode or False,
                "maintenance_message": android.maintenance_message or ""
            },
            "ios": {
                "exact_blocked_version": ios.exact_blocked_version if ios else "",
                "min_supported_version": ios.min_supported_version if ios else "",
                "maintenance_mode": ios.maintenance_mode if ios else False,
                "maintenance_message": ios.maintenance_message if ios else ""
            }
        }

        # في أودو 17: استخدم make_json_response عشان يرجع JSON نظيف 100%
        return request.make_json_response(data)