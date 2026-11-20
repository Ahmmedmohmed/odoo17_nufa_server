from odoo import models, fields, api

class ServiceRating(models.Model):
    _name = 'service.rating'
    _description = 'Service and Product Ratings'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    product_id = fields.Many2one('product.template', string='Product/Service', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee')
    
    rating_float = fields.Float(string='Rating', digits=(16, 1), default=5.0)
    
    comment = fields.Text(string='Comment')
    is_approved = fields.Boolean(string='Approved', default=False)

    def write(self, vals):
        res = super(ServiceRating, self).write(vals)
        if 'is_approved' in vals or 'rating_float' in vals:
            self.product_id._compute_average_rating()
        return res

    @api.model
    def create(self, vals):
        res = super(ServiceRating, self).create(vals)
        # Recalculate if it was created as approved (unlikely based on your requirement)
        if res.is_approved:
            res.product_id._compute_average_rating()
        return res