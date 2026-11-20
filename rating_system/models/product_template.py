from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    average_rating = fields.Float(string='Avg Rating', digits=(16, 1), store=True)
    rating_count = fields.Integer(string='Review Count', store=True)

    def _compute_average_rating(self):
        for product in self:
            ratings = self.env['service.rating'].search([
                ('product_id', '=', product.id),
                ('is_approved', '=', True)
            ])
            if ratings:
                # Direct math on float fields
                total = sum(r.rating_float for r in ratings)
                product.write({
                    'average_rating': total / len(ratings),
                    'rating_count': len(ratings)
                })
            else:
                product.write({'average_rating': 0.0, 'rating_count': 0})