# -*- coding: utf-8 -*-

from odoo import models, api, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    landed_cost_ids = fields.Many2many('stock.landed.cost', string='Landed Cost')


    def action_create_landed_cost(self):
        landed_cost_id = self.env['stock.landed.cost'].create({'date': fields.Date.today(), 'picking_ids': self.ids})
        self.landed_cost_ids = [(4, landed_cost_id.id)]


    def action_view_landed_cost(self):
        landed_cost_ids = self.mapped('landed_cost_ids')
        action = self.env['ir.actions.actions']._for_xml_id('stock_landed_costs.action_stock_landed_cost')
        action['domain'] = [('id', 'in', landed_cost_ids.ids)]
        return action