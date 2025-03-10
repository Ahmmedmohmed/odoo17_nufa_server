# -*- encoding: utf-8 -*-

from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    warehouse_transfer = fields.Boolean('Warehouse Transfer')
