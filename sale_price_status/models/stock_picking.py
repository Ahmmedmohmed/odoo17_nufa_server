from odoo import fields, models

class StockPicking(models.Model):
    _inherit = "stock.picking"

    financial_status = fields.Char(
        related="sale_id.financial_status",
        string="Financial Status",
        store=True,
        readonly=True
    )
