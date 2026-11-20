from odoo import http
from odoo.http import request

class RatingAPI(http.Controller):

    @http.route('/api/ratings/list', type='json', auth='public', methods=['POST'], csrf=False)
    def get_ratings(self, **kwargs):
        product_id = kwargs.get('product_id')
        product = request.env['product.template'].sudo().browse(product_id)
        
        if not product.exists():
            return {'error': 'Product not found'}

        # Get statistics
        raw_ratings = request.env['service.rating'].sudo().search([
            ('product_id', '=', product_id),
            ('is_approved', '=', True)
        ])
        
        stats = {str(i): 0 for i in range(1, 6)}
        for r in raw_ratings:
            star = int(round(r.rating_float or 0.0))
            if 1 <= star <= 5:
                stats[str(star)] += 1

        return {
            'average_rating': product.average_rating,
            'total_count': product.rating_count,
            'star_details': stats,
            'reviews': [{
                'customer': r.partner_id.name,
                'rating': r.rating_float,
                'comment': r.comment,
                'employee': r.employee_id.name if r.employee_id else False
            } for r in raw_ratings]
        }

    @http.route('/api/ratings/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def post_rating(self, **kwargs):
        vals = {
        'partner_id': request.env.user.partner_id.id,
        'product_id': kwargs.get('product_id'),
        'employee_id': kwargs.get('employee_id'),
        # Convert to string to match the Selection keys exactly
        'rating_float': float(kwargs.get('rating') or 0.0),
        'comment': kwargs.get('comment'),
        'is_approved': False
    }
        new_rating = request.env['service.rating'].sudo().create(vals)
        return {'status': 'success', 'id': new_rating.id}