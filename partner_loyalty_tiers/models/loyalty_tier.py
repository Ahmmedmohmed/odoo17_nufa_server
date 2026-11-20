# -*- coding: utf-8 -*-
from odoo import models, fields

class LoyaltyTier(models.Model):
    _name = 'loyalty.tier'
    _description = 'Customer Loyalty Tier'
    _order = 'min_purchase desc'

    name = fields.Char(string='Tier Name', required=True, translate=True)
    min_purchase = fields.Float(string='Minimum Purchase Amount', required=True)
    point_value = fields.Float(string='Point Redemption Value', required=True, default=1.0,
                               help='The monetary value of a point when the customer redeems it.')
    active = fields.Boolean(default=True)