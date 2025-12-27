# -*- coding: utf-8 -*-

from odoo import models
from odoo.tools.float_utils import float_round


class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    def create_returns(self):
        res = super(StockReturnPicking, self).create_returns()

        # check move line related to custody line
        for stock_move in self.mapped("picking_id.move_ids_without_package").filtered(lambda m: m.custody_line_id):
            custody_line = stock_move.custody_line_id
            quantity = stock_move.product_qty
            for move in stock_move.move_dest_ids:
                if move.origin_returned_move_id and move.origin_returned_move_id != stock_move:
                    continue
                if move.state in ('partially_available', 'assigned'):
                    quantity -= sum(move.move_line_ids.mapped('quantity'))
                elif move.state in ('done'):
                    quantity -= move.product_qty
            quantity = float_round(quantity, precision_rounding=stock_move.product_uom.rounding)
            
            vals = {"full_return": False}
            if custody_line.quantity != quantity:
                vals.update({"inventory_state": "return"})

            if quantity == 0:
                vals.update({"full_return": True})
            custody_line.write(vals)
        return res
