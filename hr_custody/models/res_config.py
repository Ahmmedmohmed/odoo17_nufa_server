# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    custody_picking_type_id = fields.Many2one("stock.picking.type", string="Custody Operation Type",
                                              domain=[("code", "=", "outgoing")],
                                              config_parameter="hr_custody.custody_picking_type_id")
