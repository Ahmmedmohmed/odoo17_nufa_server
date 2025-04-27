# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)

        if vals.get('move_type') == 'out_invoice':
            sale_id = self.env['sale.order'].search([('name', '=', vals.get('invoice_origin'))])
            move_ids = sale_id.invoice_ids
            if sale_id.amount_total < sum(move_ids.mapped('amount_residual')):
                raise UserError("Invoices cannot be created with a total value exceeding the quote value.")
            else:
                return res
        elif vals.get('move_type') == 'in_invoice':
            purchase_id = self.env['purchase.order'].search([('name', '=', vals.get('invoice_origin'))])
            move_ids = purchase_id.invoice_ids
            if purchase_id.amount_total < sum(move_ids.mapped('amount_residual')):
                raise UserError("Bills cannot be created with a total value exceeding the quote value.")
            else:
                return res
        else:
            return res