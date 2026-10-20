# -*- coding: utf-8 -*-
from . import controllers
from . import models

from odoo import Command


def post_init_hook(env):
    Provider = env['payment.provider']
    provider = Provider.search([('code', '=', 'hyperpay')], limit=1)
    if not provider:
        provider = Provider.create({
            'name': 'HyperPay',
            'code': 'hyperpay',
            'state': 'disabled',   # غيّرها لـ 'enabled' لو عايزه يشتغل فوراً
        })

    # فورم التحويل (كان ملف payment_provider_data.xml بيعمله)
    redirect_form = env.ref('hyperpay_api_integration.redirect_form',
                            raise_if_not_found=False)
    if redirect_form:
        provider.redirect_form_view_id = redirect_form.id

    # طرق الدفع: فعّل المخفي منها واربطها بالـ provider
    methods = env['payment.method'].with_context(active_test=False).search([
        ('code', 'in', ['visa', 'mastercard', 'mada']),
    ])
    methods.filtered(lambda m: not m.active).write({'active': True})
    provider.payment_method_ids = [Command.link(m.id) for m in methods]