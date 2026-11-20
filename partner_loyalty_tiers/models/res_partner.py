# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    loyalty_tier_id = fields.Many2one('loyalty.tier', string='مستوى الولاء',
                                      compute='_compute_loyalty_tier', store=True, readonly=False)

    is_manual_tier = fields.Boolean(string='تثبيت المستوى يدوياً', default=False,
                                    help='تفعيل هذا الخيار يمنع النظام من تغيير مستوى العميل تلقائياً')

    total_purchase = fields.Float(string='إجمالي المشتريات', compute='_compute_total_purchase', store=True)

    @api.depends('sale_order_ids.state', 'sale_order_ids.amount_total')
    def _compute_total_purchase(self):
        for partner in self:
            orders = self.env['sale.order'].search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['sale', 'done'])
            ])
            partner.total_purchase = sum(orders.mapped('amount_total'))

    def _send_tier_upgrade_notification(self, partner, tier_name):
        """Create multilingual tier upgrade notification for the customer."""
        if 'notifications.model' not in self.env or not tier_name:
            return
        self.env['notifications.model'].sudo().create({
            'partner': partner.id,
            'noti_type': 'Reminder',
            'content_ar': 'ترقية مستوى الولاء! 🎉',
            'content_en': 'Loyalty Tier Upgraded! 🎉',
            'sub_content_ar': f'تهانينا {partner.name}! لقد تم ترقيتك إلى المستوى {tier_name}. استمتع بمكافآت وخصومات أكبر.',
            'sub_content_en': f'Congratulations {partner.name}! You have been upgraded to the {tier_name} tier. Enjoy greater rewards and discounts.',
        })

    @api.depends('total_purchase', 'is_manual_tier')
    def _compute_loyalty_tier(self):
        tiers = self.env['loyalty.tier'].search([])
        for partner in self:
            # لو المستوى متثبت يدوي، ملناش دعوة بيه ونتخطاه
            if partner.is_manual_tier:
                continue

            assigned_tier = False
            for tier in tiers:
                if partner.total_purchase >= tier.min_purchase:
                    assigned_tier = tier
                    break

            # =========================================================
            # اصطياد التغيير التلقائي للمستوى وإرسال الإشعار
            # =========================================================
            # نتأكد إن العميل متسجل فعلياً في الداتابيز (رقم صحيح مش ريكورد وهمي وقت الإنشاء)
            if isinstance(partner.id, int):
                old_tier_id = partner.loyalty_tier_id.id
                new_tier_id = assigned_tier.id if assigned_tier else False

                # لو العميل كان ليه مستوى قديم، والمستوى الجديد مختلف (حصلت ترقية)
                if old_tier_id and new_tier_id and old_tier_id != new_tier_id:
                    self._send_tier_upgrade_notification(partner, assigned_tier.name)
            # =========================================================

            # تحديث حقل المستوى في الداتابيز
            partner.loyalty_tier_id = assigned_tier.id if assigned_tier else False

    # =========================================================
    # اصطياد التغيير اليدوي للمستوى وإرسال الإشعار
    # =========================================================
    def write(self, vals):
        # 1. نحتفظ بالمستوى القديم لكل عميل قبل ما الداتا تتحدث
        old_tiers = {partner.id: partner.loyalty_tier_id.id for partner in self}

        # 2. ننفذ التحديث الأساسي في الداتابيز
        res = super(ResPartner, self).write(vals)

        # 3. نلف على العملاء ونقارن المستوى القديم بالجديد
        for partner in self:
            old_tier_id = old_tiers.get(partner.id)
            new_tier_id = partner.loyalty_tier_id.id

            # الشرط: المستوى اتغير + المستوى الجديد مش فاضي + العميل كان ليه مستوى قديم
            # (الشرط الأخير عشان منبعتش إشعار ترقية لعميل لسه متكريت لأول مرة بياخد أول مستوى)
            if new_tier_id and new_tier_id != old_tier_id and old_tier_id:
                self._send_tier_upgrade_notification(partner, partner.loyalty_tier_id.name)

        return res