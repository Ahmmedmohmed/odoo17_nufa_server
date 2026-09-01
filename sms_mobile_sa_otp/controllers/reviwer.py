# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import math
import jwt
import logging
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

def _json_err(msg, status=400):
    return Response(json.dumps({"status": "failed", "message": msg, "data": {}}),
                    status=status, content_type="application/json")

def _partner_from_token():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err("Authorization Bearer token is required", 401)
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner = request.env["res.partner"].sudo().browse(payload.get("partner_id"))
        if not partner.exists():
            return None, _json_err("Partner not found", 404)
        return partner, None
    except jwt.ExpiredSignatureError:
        return None, _json_err("Token has expired", 401)
    except jwt.InvalidTokenError:
        return None, _json_err("Invalid token", 401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err(str(e), 400)


class ReviewAPIController(http.Controller):

    # --- دالة مساعدة لتجهيز شكل التقييم (بتطبق شرط الإدارة وتجيب الصور) ---
    def _format_review(self, review):
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url').strip('/')

        # تجهيز رابط صورة العميل
        avatar_url = ""
        if review.partner_id.image_128:
            avatar_url = f"{base_url}/web/image/res.partner/{review.partner_id.id}/avatar_128"

        return {
            'review_id': review.id,
            'reviewer_name': review.partner_id.name,
            'reviewer_image': avatar_url,
            'rating': review.rating,
            # الشرط السحري: الكومنت يرجع فقط لو واخد Approved من الأدمن
            'comment': review.comment if review.state == 'approved' else "",
            'employee_name': review.employee_id.name if review.employee_id else None,
            'date': review.create_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': review.state  # اختياري، ممكن تشيلها لو مش عايز الموبايل يعرف الحالة
        }

    # --- دالة مساعدة جوه الكلاس للتحويل الذكي للـ ID ---
    def _get_template_id(self, p_id):
        """بتاخد الـ ID سواء كان Variant من الأوردر أو Template وتجيب الـ Template الصحيح"""
        variant = request.env['product.product'].sudo().browse(p_id)
        if variant.exists():
            return variant.product_tmpl_id.id
        return p_id

    # 1. Endpoint: تقييم منتج مخزني
    @http.route('/api/reviews/product', type='http', auth='public', methods=['POST'], csrf=False)
    def rate_stockable_product(self, **kw):
        partner, err_response = _partner_from_token()
        if err_response:
            return err_response

        data = json.loads(request.httprequest.data or '{}')
        raw_product_id = int(data.get('product_id', 0))

        # 🚀 التحويل الذكي: لو باعت ID من تفاصيل الأوردر هيتحول لـ Template صح
        product_tmpl_id = self._get_template_id(raw_product_id)

        product = request.env['product.template'].sudo().browse(product_tmpl_id)
        if not product.exists():
            return request.make_json_response(
                {'status': 'error', 'message': f'Product with ID {raw_product_id} not found.'},
                status=404
            )

        try:
            review = request.env['product.review'].sudo().create({
                'product_id': product_tmpl_id,  # بنسجل بالـ Template ID
                'partner_id': partner.id,
                'rating': int(data.get('rating')),
                'comment': data.get('comment', ''),
            })
            return request.make_json_response(
                {'status': 'success', 'message': 'Review submitted for approval.'}, status=201)
        except Exception as e:
            return request.make_json_response({'status': 'error', 'message': str(e)}, status=400)

    # 2. Endpoint: تقييم خدمة والموظف اللي عملها
    @http.route('/api/reviews/service', type='http', auth='public', methods=['POST'], csrf=False)
    def rate_service_employee(self, **kw):
        partner, err_response = _partner_from_token()
        if err_response:
            return err_response

        data = json.loads(request.httprequest.data or '{}')
        raw_product_id = int(data.get('product_id', 0))
        employee_id = int(data.get('employee_id', 0))

        # 🚀 التحويل الذكي
        product_tmpl_id = self._get_template_id(raw_product_id)

        product = request.env['product.template'].sudo().browse(product_tmpl_id)
        if not product.exists():
            return request.make_json_response(
                {'status': 'error', 'message': f'Service with ID {raw_product_id} not found.'}, status=404)

        if employee_id:
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                return request.make_json_response(
                    {'status': 'error', 'message': f'Employee with ID {employee_id} not found.'}, status=404)

        try:
            review = request.env['product.review'].sudo().create({
                'product_id': product_tmpl_id,
                'employee_id': employee_id,
                'partner_id': partner.id,
                'rating': int(data.get('rating')),
                'comment': data.get('comment', ''),
            })
            return request.make_json_response(
                {'status': 'success', 'message': 'Service review submitted for approval.'}, status=201)
        except Exception as e:
            return request.make_json_response({'status': 'error', 'message': str(e)}, status=400)

    # 3. Endpoint: تفاصيل المنتج (ترجع معاها آخر 5 تقييمات)
    @http.route('/api/product/details/<int:product_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_details(self, product_id, **kw):
        # 🚀 التحويل الذكي عشان لو الموبايل نادى الـ Endpoint بـ ID الأوردر
        product_tmpl_id = self._get_template_id(product_id)

        product = request.env['product.template'].sudo().browse(product_tmpl_id)
        if not product.exists():
            return request.make_json_response({'status': 'error', 'message': 'Product not found'}, status=404)

        recent_reviews = request.env['product.review'].sudo().search(
            [('product_id', '=', product.id)], limit=5, order='create_date desc'
        )

        formatted_reviews = [self._format_review(r) for r in recent_reviews]

        payload = {
            'status': 'success',
            'product_id': product.id,
            'product_name': product.name,
            # هنا ممكن تضيف باقي بيانات المنتج (السعر، الوصف، الخ)
            'latest_reviews': formatted_reviews
        }
        return request.make_json_response(payload, status=200)

    # 4. Endpoint: كل التقييمات لمنتج معين مع Pagination
    @http.route('/api/product/<int:product_id>/reviews', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_paginated_reviews(self, product_id, **kw):
        # 🚀 التحويل الذكي
        product_tmpl_id = self._get_template_id(product_id)

        page = int(kw.get('page', 1))
        limit = int(kw.get('limit', 10))
        offset = (page - 1) * limit

        ReviewModel = request.env['product.review'].sudo()
        domain = [('product_id', '=', product_tmpl_id)]  # بنبحث بـ Template ID

        reviews = ReviewModel.search(domain, offset=offset, limit=limit, order='create_date desc')
        total_count = ReviewModel.search_count(domain)

        formatted_reviews = [self._format_review(r) for r in reviews]

        payload = {
            'status': 'success',
            'pagination': {
                'current_page': page,
                'per_page': limit,
                'total_items': total_count,
                'total_pages': math.ceil(total_count / limit) if limit else 1
            },
            'reviews': formatted_reviews
        }
        return request.make_json_response(payload, status=200)