# -*- coding: utf-8 -*-

from odoo import api, fields, models, _



class ResCompany(models.Model):
    _inherit = 'res.company'


    location_dest_id = fields.Many2one('stock.location', string='Destination Location')
    picking_type_id  = fields.Many2one('stock.picking.type', string='Operation Type')