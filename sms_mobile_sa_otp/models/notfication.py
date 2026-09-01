# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import UserError
from odoo.http import request  # 🚀 ضفنا الـ request عشان نقرأ الهيدر من الموبايل
import firebase_admin
from firebase_admin import credentials, messaging
import logging
import pathlib
import os

_logger = logging.getLogger(__name__)


class Notifications(models.Model):
    _name = 'notifications.model'
    _rec_name = 'noti_type'

    partner = fields.Many2one('res.partner', string="Partner")
    employee_id = fields.Many2one('hr.employee', string='Employee')
    noti_type = fields.Selection([
        ('Invoice', 'Invoice'),
        ('Reminder', 'Reminder'),
        ('Booking', 'Booking'),
        ('Failure', 'Failure')
    ], string='Type')
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # 🚀 تقسيم الحقول للغتين
    content_ar = fields.Text(string='Title (Arabic)')
    content_en = fields.Text(string='Title (English)')
    sub_content_ar = fields.Text(string='SubTitle (Arabic)')
    sub_content_en = fields.Text(string='SubTitle (English)')

    read_noti = fields.Boolean(string='Read')

    @api.model
    def _ensure_firebase_initialized(self):
        if not firebase_admin._apps:
            try:
                key_name = 'nouf-beauty-8acd2-firebase-adminsdk-fbsvc-f19f67e40a.json'
                current_dir = os.path.dirname(os.path.abspath(__file__))
                key_path = os.path.join(current_dir, key_name)
                if os.path.exists(key_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(credential=cred)
                else:
                    _logger.error(f"FIREBASE ERROR: Key file not found at {key_path}")
            except Exception as e:
                _logger.error(f"Firebase Init Error: {str(e)}")

    @api.model
    def create(self, vals):
        result = super(Notifications, self).create(vals)
        if result.employee_id and result.employee_id.user_id and result.employee_id.user_id.partner_id.fcm_token:
            result._send_fcm_notification(result.employee_id.user_id.partner_id.fcm_token)
        if result.partner and result.partner.fcm_token:
            result._send_fcm_notification(result.partner.fcm_token)
        return result

    def _send_fcm_notification(self, token):
        self.ensure_one()
        self._ensure_firebase_initialized()
        try:
            # 🚀 اللوجيك الذكي لتحديد لغة الإشعار
            is_ar = True  # الافتراضي عربي
            try:
                # 1. محاولة قراءة اللغة من الهيدر (لو الإشعار جي من الـ API)
                if request and hasattr(request, 'httprequest'):
                    header_lang = request.httprequest.headers.get('lang', '').lower()
                    if header_lang in ['en', 'en_us']:
                        is_ar = False
                    elif header_lang in ['ar', 'ar_001']:
                        is_ar = True
                else:
                    # 2. لو مفيش هيدر (من لوحة التحكم)، نعتمد على لغة الداتابيز
                    if self.partner and self.partner.lang and self.partner.lang.startswith('en'):
                        is_ar = False
            except Exception:
                pass # تجاهل الخطأ والاعتماد على الافتراضي (عربي)

            title = self.content_ar if is_ar else self.content_en
            body = self.sub_content_ar if is_ar else self.sub_content_en

            sound = 'default'
            critical_sound = messaging.CriticalSound(name=sound, critical=True, volume=1)
            aps_alert = messaging.ApsAlert(title=title, body=body)
            aps = messaging.Aps(alert=aps_alert, content_available=True, sound=critical_sound)
            aps_config = messaging.APNSConfig(payload=messaging.APNSPayload(aps=aps))

            android_notif = messaging.AndroidNotification(
                title=title, body=body, default_sound=True, visibility="public"
            )
            android_config = messaging.AndroidConfig(priority='high', notification=android_notif)

            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
                android=android_config,
                apns=aps_config
            )
            messaging.send(message)
            _logger.info(f"FCM Sent Successfully to {token}")
        except Exception as e:
            _logger.error(f"FCM Failed for token {token}: {str(e)}")


class NotificationBroadcast(models.TransientModel):
    _name = 'notification.broadcast.wizard'
    _description = 'Broadcast Notification to All'

    title_ar = fields.Char(string="Title (Arabic)", required=True, default="تحديث جديد للتطبيق")
    body_ar = fields.Text(string="Message (Arabic)", required=True,
                          default="يرجى تحديث التطبيق للاستمتاع بأحدث الميزات.")

    title_en = fields.Char(string="Title (English)", required=True, default="New App Version")
    body_en = fields.Text(string="Message (English)", required=True,
                          default="Please update your app to enjoy the latest features.")

    def action_broadcast_update_notification(self):
        """إرسال إشعار للجميع مع فصل اللغة العربية عن الإنجليزية"""
        self.env['notifications.model']._ensure_firebase_initialized()
        partners = self.env['res.partner'].sudo().search([('fcm_token', '!=', False)])

        if not partners:
            raise UserError(_("No tokens found. Cannot send notifications."))

        # 🚀 التعديل هنا: اللي لغته إنجليزي صريحة يروح للدفعة الإنجليزية، الباقي كله عربي كافتراضي
        tokens_en = list({p.fcm_token for p in partners if p.lang and p.lang.startswith('en') and p.fcm_token})
        tokens_ar = list({p.fcm_token for p in partners if p.fcm_token and p.fcm_token not in tokens_en})

        success_count = 0
        max_batch = 500

        if tokens_ar:
            for i in range(0, len(tokens_ar), max_batch):
                batch_tokens = tokens_ar[i:i + max_batch]
                try:
                    message_ar = messaging.MulticastMessage(
                        notification=messaging.Notification(title=self.title_ar, body=self.body_ar),
                        tokens=batch_tokens
                    )
                    response_ar = messaging.send_multicast(message_ar)
                    success_count += response_ar.success_count
                except Exception as e:
                    _logger.error(f"Multicast AR error: {str(e)}")

        if tokens_en:
            for i in range(0, len(tokens_en), max_batch):
                batch_tokens = tokens_en[i:i + max_batch]
                try:
                    message_en = messaging.MulticastMessage(
                        notification=messaging.Notification(title=self.title_en, body=self.body_en),
                        tokens=batch_tokens
                    )
                    response_en = messaging.send_multicast(message_en)
                    success_count += response_en.success_count
                except Exception as e:
                    _logger.error(f"Multicast EN error: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Notification Sent"),
                'message': _(f"Successfully sent to {success_count} devices."),
                'sticky': False,
            }
        }