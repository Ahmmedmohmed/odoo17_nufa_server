# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools
import logging
_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'


    image_not_show = fields.Boolean(related='config_id.allow_image_on_orderline',store=True)

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    line_image = fields.Binary(string="Product Image",related='product_id.image_128',store=True)

