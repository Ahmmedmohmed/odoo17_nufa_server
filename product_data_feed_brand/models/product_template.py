from odoo import api, fields, models
from odoo.tools.misc import str2bool


class ProductTemplate(models.Model):
    _inherit = "product.template"

    feed_brand_id = fields.Many2one(comodel_name='product.data.feed.brand', string='Product Brand')
    feed_brand_is_visible = fields.Boolean(compute='_compute_feed_brand_is_visible')

    @api.depends('feed_brand_id')
    def _compute_feed_brand_is_visible(self):
        is_visible = not str2bool(
            self.env['ir.config_parameter'].sudo().get_param('product_data_feed_brand.feed_brand_invisible', False)
        )
        for product in self:
            product.feed_brand_is_visible = is_visible
