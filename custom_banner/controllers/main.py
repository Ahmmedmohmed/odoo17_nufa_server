import json
import requests
from odoo import http
from odoo.http import request, Response

class BannerController(http.Controller):

    # --- META API CONFIGURATION ---
    # Get these from https://developers.facebook.com/
    META_TOKEN = "EAFuId4IjxeEBQSFVsU7gH2exgl7ukZBebdDnAUZBnVwh60EKSLwufJAKv1Y17C2pbue5i9NOkRUGRb9QCiyzQl5FEnBPUgP7XcfmkKpl6T6CS32RNpZBIEYpDGgdlZABoYeYqCm535uBkdqjm8BlIPjeolppIJpZCfZCdiuDqbXQvbTWAAebXOcDQM1TXqaSYP0CPoFoLXyk6QEl5fMQ8CkkBy9fAw6w619VE5f147oDq3ZAWrQntpSDY29884LpGTUYX1ZCr4kcp8CaRzoKU6GWAwsG"
    PHONE_NUMBER_ID = "907241232476654"
    META_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

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
    @http.route('/api/send_appointment_whatsapp', type='http', auth='public', methods=['POST'], csrf=False)
    def api_send_whatsapp_direct(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data)
            appointment_id = body.get('appointment_id')
            
            appt = request.env['appointment.management'].sudo().browse(int(appointment_id))
            if not appt.exists():
                return self._json({'error': 'Appointment not found'}, status=404)

            # 1. Generate or Get your PDF URL
            # Meta requires a publicly accessible link (HTTPS). 
            # In production, use Odoo's internal URL or an S3 link.
            pdf_url = "http://localhost:8017/custom_banner/static/file-sample_150kB.pdf"
            
            payload = {
                "messaging_product": "whatsapp",
                "to": "917405072262", 
                "type": "template",
                "template": {
                    "name": "appointment_confirmation_pdf", # Must match Meta name
                    "language": {"code": "en_US"},
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "document",
                                    "document": {
                                        "link": pdf_url,
                                        "filename": f"Appointment_pdf.pdf"
                                    }
                                }
                            ]
                        },
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "kabir"},
                                {"type": "text", "text": "kabir"},
                                # {"type": "text", "text": appt.partner_id.name},
                                # {"type": "text", "text": appt.name}
                            ]
                        }
                    ]
                }
            }

            headers = {"Authorization": f"Bearer {self.META_TOKEN}", "Content-Type": "application/json"}
            response = requests.post(self.META_URL, json=payload, headers=headers)
            return self._json(response.json(), status=response.status_code)

        except Exception as e:
            return self._json({'error': str(e)}, status=500)