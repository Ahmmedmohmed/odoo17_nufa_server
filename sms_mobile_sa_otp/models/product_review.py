# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductReview(models.Model):
    _name = 'product.review'
    _description = 'Product & Service Reviews'
    _order = 'create_date desc'

    # العلاقة هنا بتشاور على الـ Template
    product_id = fields.Many2one('product.template', string='Product / Service', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee (For Services)')

    rating = fields.Integer(string='Rating (1-5)', required=True)
    comment = fields.Text(string='Comment')

    state = fields.Selection([
        ('draft', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft')

    @api.constrains('rating')
    def _check_rating(self):
        for record in self:
            if record.rating < 1 or record.rating > 5:
                raise ValueError("Rating must be between 1 and 5")

    def action_approve(self):
        for record in self:
            record.state = 'approved'

    def action_reject(self):
        for record in self:
            record.state = 'rejected'


# 1. موديل الـ Template (هنا بنحط التقييمات عشان الـ API يقراها والعلاقة تكون صح)
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    review_ids = fields.One2many('product.review', 'product_id', string='Reviews')

    manual_rating = fields.Float(string='Manual/Fake Rating')
    avg_rating = fields.Float(
        string='Average Rating',
        compute='_compute_avg_rating',
        store=True  # مهم جداً للترتيب في الـ API
    )

    @api.depends('review_ids.rating', 'review_ids.state', 'manual_rating')
    def _compute_avg_rating(self):
        for template in self:
            if template.manual_rating > 0:
                template.avg_rating = template.manual_rating
            else:
                valid_reviews = template.review_ids.filtered(lambda r: r.state != 'rejected')
                if valid_reviews:
                    total_score = sum(valid_reviews.mapped('rating'))
                    template.avg_rating = total_score / len(valid_reviews)
                else:
                    template.avg_rating = 0.0


# 2. موديل الـ Variant (هنا بنسيب باقي حقول الموبايل الخاصة بالنسخ الفرعية)
class ProductProduct(models.Model):
    _inherit = 'product.product'

    top = fields.Boolean(string='Top')
    price_after_discount = fields.Float(string='Price after discount')
    ar_name = fields.Char(string='Arabic Name')
    ar_description = fields.Text(string='Arabic Description')