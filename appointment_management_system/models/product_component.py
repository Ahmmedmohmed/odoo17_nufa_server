# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductComponent(models.Model):
    _name = 'product.component'
    _description = 'Product Component'


    component_id = fields.Many2one('product.product', string='Component', required=True)
    quantity = fields.Float(string='Quantity')

    product_id = fields.Many2one('product.product', string='Product')