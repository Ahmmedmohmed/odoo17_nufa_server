# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    # =========================================================================
    # إضافة loyalty_tier_id لبيانات res.partner المُرسَلة للـ POS
    # =========================================================================
    def _loader_params_res_partner(self):
        result = super()._loader_params_res_partner()
        fields_list = result['search_params']['fields']
        if 'loyalty_tier_id' not in fields_list:
            fields_list.append('loyalty_tier_id')
        return result

    # =========================================================================
    # إضافة allowed_tier_ids لبيانات loyalty.reward المُرسَلة للـ POS
    # =========================================================================
    def _loader_params_loyalty_reward(self):
        if not hasattr(super(), '_loader_params_loyalty_reward'):
            _logger.warning("[LoyaltyTiers] _loader_params_loyalty_reward غير موجودة في الـ parent.")
            return {'search_params': {'domain': [], 'fields': ['allowed_tier_ids']}}
        result = super()._loader_params_loyalty_reward()
        fields_list = result['search_params']['fields']
        if 'allowed_tier_ids' not in fields_list:
            fields_list.append('allowed_tier_ids')
        return result

    # =========================================================================
    # إضافة allowed_tier_ids لبيانات loyalty.rule المُرسَلة للـ POS
    # =========================================================================
    def _loader_params_loyalty_rule(self):
        if not hasattr(super(), '_loader_params_loyalty_rule'):
            _logger.warning("[LoyaltyTiers] _loader_params_loyalty_rule غير موجودة في الـ parent.")
            return {'search_params': {'domain': [], 'fields': ['allowed_tier_ids']}}
        result = super()._loader_params_loyalty_rule()
        fields_list = result['search_params']['fields']
        if 'allowed_tier_ids' not in fields_list:
            fields_list.append('allowed_tier_ids')
        return result

    # =========================================================================
    # إضافة بيانات loyalty.tier كاملة لحزمة الـ POS
    #
    # loyalty.tier ليس مودلاً معروفاً للـ POS store افتراضياً.
    # هذه الدالة تُضيفه كـ key في الـ data dictionary الذي يُرسَل
    # للـ frontend عند فتح جلسة الـ POS.
    #
    # ملاحظة: _get_pos_data هي الدالة المعتمدة في Odoo 17 لإرسال
    # بيانات إضافية. إذا لم تعمل، استخدم _pos_data_process كـ fallback.
    # =========================================================================
    def _get_pos_data(self):
        data = super()._get_pos_data()
        if 'loyalty.tier' not in data:
            tiers = self.env['loyalty.tier'].sudo().search_read(
                domain=[('active', '=', True)],
                fields=['id', 'name', 'min_purchase', 'point_value'],
            )
            data['loyalty.tier'] = tiers
            _logger.info("[LoyaltyTiers] Sent %d tiers to POS.", len(tiers))
        return data

    # =========================================================================
    # Fallback: نفس الغرض لكن عبر _pos_data_process
    # (بعض إصدارات Odoo 17 تستدعي هذه بدلاً من _get_pos_data)
    # =========================================================================
    def _pos_data_process(self, loaded_data):
        result = super()._pos_data_process(loaded_data)
        if 'loyalty.tier' not in loaded_data:
            tiers = self.env['loyalty.tier'].sudo().search_read(
                domain=[('active', '=', True)],
                fields=['id', 'name', 'min_purchase', 'point_value'],
            )
            loaded_data['loyalty.tier'] = tiers
            _logger.info("[LoyaltyTiers] (fallback) Sent %d tiers to POS.", len(tiers))
        return result