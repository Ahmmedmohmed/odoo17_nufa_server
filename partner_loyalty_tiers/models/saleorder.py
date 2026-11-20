# -*- coding: utf-8 -*-
import logging
from odoo import models
from odoo.addons.sale_loyalty.models.sale_order import SaleOrder as BaseSaleOrder

_logger = logging.getLogger(__name__)


# --- 1. الـ Patch العالمي (مع تمرير forced_coupons بشكل صحيح) ---
def apply_global_loyalty_patch():
    try:
        # بنخلي الدالة الأم تقبل أي حاجة تتبعت لها مع الحفاظ على forced_coupons
        if not hasattr(BaseSaleOrder, '_original_get_claimable_rewards'):
            BaseSaleOrder._original_get_claimable_rewards = BaseSaleOrder._get_claimable_rewards

            def patched_get_claimable_rewards(self, forced_coupons=None, *args, **kwargs):
                return self._original_get_claimable_rewards(forced_coupons=forced_coupons)

            BaseSaleOrder._get_claimable_rewards = patched_get_claimable_rewards
            _logger.info("✅ Global Patch Applied Successfully")
    except Exception as e:
        _logger.error("❌ Patch Error: %s", e)


apply_global_loyalty_patch()


# --- 2. الكلاس بتاعك (الـ Inherit) ---
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # لازم الدالة هنا كمان تقبل forced_coupons و **kwargs عشان الكوبونات وموديول الشحن يشتغلوا مع بعض
    def _get_claimable_rewards(self, forced_coupons=None, **kwargs):
        res = super()._get_claimable_rewards(forced_coupons=forced_coupons, **kwargs)

        partner = self.partner_id
        if not partner:
            return res

        filtered_res = {}
        for coupon, rewards in res.items():
            # فلترة الجوائز بناءً على التير (Tier) بتاع العميل
            valid_rewards = rewards.filtered(lambda r: r._is_valid_for_tier(partner))
            if valid_rewards:
                filtered_res[coupon] = valid_rewards

        return filtered_res

    def _update_programs_and_rewards(self):
        return super()._update_programs_and_rewards()
