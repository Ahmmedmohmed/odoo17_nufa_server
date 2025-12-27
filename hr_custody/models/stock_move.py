# -*- coding: utf-8 -*-
from odoo import models, fields


class StockMove(models.Model):
    _inherit = "stock.move"

    custody_line_id = fields.Many2one("hr.custody.line", string="Custody Line", copy=False)


class StockCustody(models.Model):
    _inherit = 'stock.picking'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=False)

