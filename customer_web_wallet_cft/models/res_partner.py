# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    available_balance = fields.Monetary('Available Balance',
                                        compute='_calculate_available_balance')

    def _calculate_available_balance(self):
        for rec in self:
            domain = [
                ('account_id', '=', rec.property_account_receivable_id.id),
                ('partner_id', '=', rec._find_accounting_partner(rec).id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0),
                ('amount_residual_currency', '!=', 0.0),
                ('credit', '>', 0), ('debit', '=', 0)
            ]
            lines = self.env['account.move.line'].search(domain)
            rec.update({
                'available_balance': abs(sum(lines.mapped('amount_residual')))
            })
