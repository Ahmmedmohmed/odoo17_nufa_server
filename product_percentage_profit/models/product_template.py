from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.template"

    percentage_profit = fields.Float(string="Percentage Profit", help="Profit percentage to be added to cost price")

    @api.depends('standard_price', 'percentage_profit')
    def _compute_list_price(self):
        for product in self:
            if product.standard_price and product.percentage_profit:
                product.list_price = product.standard_price * (1 + product.percentage_profit / 100)
            else:
                product.list_price = product.standard_price

    list_price = fields.Float(compute='_compute_list_price', store=True, string="Sale Price")