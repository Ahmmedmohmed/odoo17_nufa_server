# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    allow_image_on_orderline = fields.Boolean(string="Allow Image on Orderline")




class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_allow_image_on_orderline = fields.Boolean(related='pos_config_id.allow_image_on_orderline', readonly=False)






