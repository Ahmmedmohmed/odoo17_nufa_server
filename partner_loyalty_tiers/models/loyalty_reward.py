# -*- coding: utf-8 -*-
from odoo import models, fields

class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    allowed_tier_ids = fields.Many2many(
        'loyalty.tier',
        string='مخصصة لمستويات معينة',
        help='إذا تم تحديد مستويات، فلن تظهر هذه المكافأة إلا للعملاء المنتمين لهذه المستويات. اتركها فارغة لتكون متاحة للجميع.'
    )

    # الدالة الجديدة للتحقق من الأهلية
    def _is_valid_for_tier(self, partner):
        self.ensure_one()
        # لو مفيش مستويات متحددة = الجائزة متاحة للجميع
        if not self.allowed_tier_ids:
            return True
        # لو الجائزة مقيدة بمستوى، والطلب مفيش فيه عميل أو العميل ملوش مستوى
        if not partner or not partner.loyalty_tier_id:
            return False
        # هل مستوى العميل موجود ضمن المستويات المسموحة للجائزة؟
        return partner.loyalty_tier_id.id in self.allowed_tier_ids.ids