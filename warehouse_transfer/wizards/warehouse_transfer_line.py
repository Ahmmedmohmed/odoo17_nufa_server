# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WarehouseTransferLine(models.TransientModel):
    _name = 'warehouse.transfer.line'


    name            = fields.Char('Description', index=True)
    product_id      = fields.Many2one('product.product')
    product_uom     = fields.Many2one('uom.uom')
    product_uom_qty = fields.Float('Initial Demand')
    available_qty   = fields.Char("Available Quantity")
    lot_id          = fields.Many2one('stock.lot', string='Lot Name')
    expiration_date = fields.Datetime(string='Expiration Date', related="lot_id.expiration_date")
    warehouse_transfer_id = fields.Many2one('warehouse.transfer')


    @api.onchange('product_id')
    def onchange_product_id(self):
        self.product_uom = self.product_id.with_context(lang=self.env.user.lang).uom_id.id
        self.name = self.product_id.with_context(lang=self.env.user.lang).partner_ref or ''
        return {'domain': {'product_uom': [('category_id', '=', self.product_id.with_context(lang=self.env.user.lang).uom_id.category_id.id)], 'lot_id': [('product_id', '=', self.product_id.id)]}}