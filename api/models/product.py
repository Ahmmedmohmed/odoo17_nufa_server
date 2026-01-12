from odoo import api, fields, models
from odoo.addons.test_convert.tests.test_env import field


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    avg_rating = fields.Float(
        string='Average Rating'
    )
    top = fields.Boolean(
        string='Top'
    )

    price_after_discount = fields.Float(string='Price after discount')

    ar_name = fields.Char(string='Arabic Name')
    ar_description = fields.Text(string='Arabic Description')
    is_appointment_service = fields.Boolean(string='Appointment Service')



class PosCombo(models.Model):
    _inherit = 'pos.combo'

    ar_name = fields.Char(string='Arabic Name')
    ar_desc = fields.Text(string='Arabic Description')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model
    def create(self, vals):
        order_line = super(SaleOrderLine, self).create(vals)
        if order_line.product_id:
            order_line._onchange_product_id()

        return order_line

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Override to apply price_after_discount if defined."""
        for line in self:
            print("discount%%%%%%%%%%%%%%")
            if line.product_id:
                product_tmpl = line.product_id.product_tmpl_id
                if product_tmpl.price_after_discount:
                    line.price_unit = product_tmpl.price_after_discount
                else:
                    line.price_unit = line.product_id.list_price

class ProductProduct(models.Model):
    _inherit = 'product.product'

    avg_rating = fields.Float(
        string='Average Rating'
    )
    top = fields.Boolean(
        string='Top'
    )

    price_after_discount = fields.Float(string='Price after discount')

    ar_name = fields.Char(string='Arabic Name')
    ar_description = fields.Text(string='Arabic Description')