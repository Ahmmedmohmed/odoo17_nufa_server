from odoo import models, fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    signature_received = fields.Char(string="Signature Received", help="Person who received  the items")
    signature_delivered = fields.Char(string="Signature Delivered By", help="Person who delivered the items")
    received_phone = fields.Char(string="Phone Received", help="Phone number of the person who received")
    delivered_phone = fields.Char(string="Phone Delivered", help="Phone number of the person who delivered")
