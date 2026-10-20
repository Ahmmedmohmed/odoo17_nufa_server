# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    """Create one HyperPay provider per existing company (disabled until
    the credentials are filled in on the provider form)."""
    env['payment.provider']._hyperpay_setup_companies(env['res.company'].search([]))