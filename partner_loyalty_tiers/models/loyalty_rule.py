# -*- coding: utf-8 -*-
from odoo import models, fields

class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    allowed_tier_ids = fields.Many2many(
        'loyalty.tier',
        string='مخصصة لمستويات معينة',
        help='إذا تم تحديد مستويات، فلن تطبق قاعدة اكتساب النقاط هذه إلا على عملاء هذه المستويات. اتركها فارغة لتطبق على الجميع.'
    )

    # الدالة الجديدة للتحقق من أهلية اكتساب النقاط
    def _is_valid_for_tier(self, partner):
        self.ensure_one()
        if not self.allowed_tier_ids:
            return True
        if not partner or not partner.loyalty_tier_id:
            return False
        return partner.loyalty_tier_id.id in self.allowed_tier_ids.ids