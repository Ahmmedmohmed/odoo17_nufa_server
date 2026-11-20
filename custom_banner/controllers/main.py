import json
import requests
import re
from odoo import http
from odoo.http import request, Response

class BannerController(http.Controller):

    # --- META API CONFIGURATION ---
    # Get these from https://developers.facebook.com/
    META_TOKEN = "EAFuId4IjxeEBQSFeQD7RJdJFRUFuv6BT6XWDvbCgTORukY4OZCuDmquZChtRlC6N2EFmBQKvzG84fHsbqvaa657a85gfAHoLkKqvzQrEBDHMZC8PMZC5ISPQ9bdoDFkOmENXbLzecsYZBkaAkXezEPFFlQrNJiB8877i9Jfoe6ZAE5zZAnVZAIHkbYNcy3z6wdVOhwZDZD"
    PHONE_NUMBER_ID = "926541170542819"
    META_URL = f"https://graph.facebook.com/v24.0/{PHONE_NUMBER_ID}/messages"

    def _json(self, data, status=200):
        return Response(
            json.dumps(data),
            status=status,
            content_type='application/json;charset=utf-8'
        )

    # ---------------------------------------------------------
    # BANNER API (Existing)
    # ---------------------------------------------------------
    @http.route('/api/banners', type='http', auth='public', methods=['GET'], csrf=False)
    def get_banners(self, **kwargs):
        try:
            limit = int(kwargs.get('limit', 10))
            offset = int(kwargs.get('offset', 0))
            banner_model = request.env['custom.banner'].sudo()
            banner_recs = banner_model.search([], limit=limit, offset=offset, order='id asc')
            
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            data = [{
                'id': b.id,
                'name': b.name,
                'image_url': f"{base_url}/web/image/custom.banner/{b.id}/image",
                'external_url': b.external_url or "",
            } for b in banner_recs]

            return self._json({'banners': data, 'total': banner_model.search_count([])})
        except Exception as e:
            return self._json({'error': str(e)}, status=500)

    # ---------------------------------------------------------
    # NEW WHATSAPP API (Server-to-Server)
    # ---------------------------------------------------------
    @http.route('/api/send_appointment_whatsapp', type='http', auth='none', methods=['POST'], csrf=False)
    def api_send_whatsapp_direct(self, **kwargs):
        data = dict(kwargs)
        if not all(data.get(k) for k in ('name', 'phone', 'order_id', 'amount')) and request.httprequest.data:
            try:
                json_body = json.loads(request.httprequest.data.decode('utf-8'))
                if isinstance(json_body, dict):
                    data.update({k: v for k, v in json_body.items() if v is not None})
            except Exception:
                pass

        name = data.get('name')
        phone = data.get('phone')
        order_id = data.get('order_id')
        amount = data.get('amount')

        # Check if all fields are present
        if not all([name, phone, order_id, amount]):
            return self._json({'status': 'error', 'message': 'Missing required fields: name, phone, order_id, amount'}, status=400)

        base_url = request.httprequest.host_url  # Returns 'https://yourdomain.com/'
        invoice_url = f"{base_url.rstrip('/')}/appointment/pos-user/invoice/{order_id}"
        try:
            headers = {
                "Authorization": f"Bearer {self.META_TOKEN}",
                "Content-Type": "application/json"
            }

            # Payload updated to use 'order_sucess' with your parameters
            payload = {
                "messaging_product": "whatsapp",
                "to": str(phone),
                "type": "template",
                "template": {
                    "name": "order_sucess",
                    "language": {
                        "code": "en_US"
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                { "type": "text", "text": str(name) },     # {{1}}
                                { "type": "text", "text": str(order_id) }, # {{2}}
                                { "type": "text", "text": str(amount) }    # {{3}}
                            ]
                        },
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0", # The index of the button in your template (starts at 0)
                            "parameters": [
                                {
                                    "type": "text",
                                    "text": str(order_id) # The dynamic part of the URL
                                }
                            ]
                        }
                    ],
                }
            }

            response = requests.post(self.META_URL, json=payload, headers=headers, timeout=30)
            result = response.json()
            if response.status_code == 200:
                messages = result.get('messages') or [{}]
                return self._json({
                    'status': 'success',
                    'wa_id': messages[0].get('id'),
                    'invoice_url': invoice_url
                })
            else:
                return self._json({
                    'status': 'error',
                    'meta_response': result
                }, status=response.status_code)

        except Exception as e:
            return self._json({'error': str(e)}, status=500)