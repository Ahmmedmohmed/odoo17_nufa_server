# -*- coding: utf-8 -*-
from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        # every new company gets its own (disabled) HyperPay provider
        self.env['payment.provider'].sudo()._hyperpay_setup_companies(companies)
        return companies