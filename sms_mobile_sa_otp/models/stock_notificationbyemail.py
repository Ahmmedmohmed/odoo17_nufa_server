# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductStockNotification(models.Model):
    _name = 'product.stock.notification'
    _description = 'Notify User When Product in Stock'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Customer', ondelete='cascade')
    email = fields.Char(string='Email', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, ondelete='cascade')
    is_notified = fields.Boolean(string='Notified', default=False)

    @api.model
    def _check_stock_and_notify(self):
        """
        دالة بتشتغل كل فترة (Cron Job) عشان تدور على المنتجات اللي توفرت
        وتبعث إيميل للعملاء اللي طلبوا إشعار.
        """
        pending_requests = self.search([('is_notified', '=', False)])

        for req in pending_requests:
            # لو الكمية المتاحة أكبر من صفر
            if req.product_id.qty_available > 0:
                # استدعاء قالب الإيميل (تأكد من تغيير my_module_name لاسم الموديول بتاعك)
                template = self.env.ref('my_module_name.email_template_restock_notification', raise_if_not_found=False)
                if template:
                    template.send_mail(req.id, force_send=True)

                # تحديث الحالة عشان ميتبعتش تاني
                req.is_notified = True