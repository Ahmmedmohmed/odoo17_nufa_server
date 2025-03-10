from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    financial_status = fields.Char(string="Financial Status",
                                   help="Financial status of the order"
                                   )

