import json
from odoo import http
from odoo.http import request, Response
import logging
from urllib.parse import urlencode
from werkzeug.datastructures import LanguageAccept
import math
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)

from werkzeug.datastructures import LanguageAccept


def _norm_lang(raw):
    lang = (raw or '').strip().lower()
    return 'ar' if lang.startswith('ar') else 'en'


def _get_lang(kwargs=None):
    h = request.httprequest.headers

    raw = (h.get('X-Lang') or h.get('x-lang') or
           h.get('Lang') or h.get('lang'))
    if raw:
        chosen = _norm_lang(raw)
        _logger.info("Lang resolve | header=%r -> %s", raw, chosen)
        return chosen

    qp = (kwargs or {}).get('lang') or request.params.get('lang')
    if qp:
        chosen = _norm_lang(qp)
        _logger.info("Lang resolve | query=%r -> %s", qp, chosen)
        return chosen

    try:
        al: LanguageAccept = request.httprequest.accept_languages
        best = al.best_match(['ar', 'en']) if al else None
        chosen = _norm_lang(best or 'en')
    except Exception:
        chosen = 'en'

    _logger.info("Lang resolve | fallback Accept-Language -> %s", chosen)
    return chosen


class PublicImageAPI(http.Controller):

    @http.route('/api/public/image/<string:model>/<int:rec_id>/<string:field>', type='http', auth='public',
                methods=['GET'], csrf=False)
    def public_image(self, model, rec_id, field, **kwargs):
        """
        Public endpoint to serve binary image fields without ACL checks.
        Example: /api/public/image/product.template/47/image_1920
        """
        try:
            rec = request.env[model].sudo().browse(rec_id)
            if not rec.exists():
                return request.not_found()

            if field not in rec._fields or not getattr(rec, field):
                return request.not_found()

            data = base64.b64decode(getattr(rec, field))
            return request.make_response(
                data,
                headers=[
                    ('Content-Type', 'image/png'),
                    ('Cache-Control', 'public, max-age=86400'),
                ]
            )
        except Exception as e:
            return request.make_response(f"Error: {e}", [('Content-Type', 'text/plain')])


class ProductCategoryAPI(http.Controller):

    @http.route(
        '/api/products/by_category/<int:category_id>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_by_category(self, category_id, **kwargs):
        """
        Query params:
          - include_children: 1/0 (default 0)
          - limit: int (default 100)
          - offset: int (default 0)
          - warehouse_id: int (optional; compute qty per warehouse)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))
            warehouse_id = kwargs.get('warehouse_id')

            Category = request.env['product.category'].sudo()
            category = Category.browse(category_id)
            if not category.exists():
                return self._json({'error': 'Category not found', 'category_id': category_id}, status=404)

            domain = [('sale_ok', '=', True)]
            if include_children:
                domain.append(('product_tmpl_id.categ_id', 'child_of', category_id))
            else:
                domain.append(('product_tmpl_id.categ_id', '=', category_id))

            Product = request.env['product.product'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Product = Product.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            total = Product.search_count(domain)
            products = Product.search(domain, limit=limit, offset=offset, order='id')

            data = []
            for p in products:
                tpl = p.product_tmpl_id

                t_main = self._main_image_url(tpl) if hasattr(self, '_main_image_url') else None
                v_main = self._main_image_url(p) if hasattr(self, '_main_image_url') else None
                main_img_url = t_main or v_main

                gallery_urls = []
                if hasattr(self, '_template_gallery'):
                    gallery = self._template_gallery(tpl) or []
                    gallery_urls = [g.get('url') for g in gallery if g.get('url')]
                product_main_image_url = v_main
                lang = (kwargs.get('lang') or 'en').lower()
                t_name = self._pt_name(tpl, lang) if hasattr(self, '_pt_name') else (
                        getattr(tpl, 'ar_name', None) or tpl.name)
                t_desc = self._pt_desc(tpl, lang) if hasattr(self, '_pt_desc') else (
                        getattr(tpl, 'ar_description', None) or tpl.description)
                v_name = self._pp_name(p, lang) if hasattr(self, '_pp_name') else p.display_name

                data.append({
                    'id': p.id,
                    'name': v_name,
                    'barcode': p.barcode,
                    'uom': p.uom_id.name if p.uom_id else None,
                    'qty': float(p.qty_available or 0.0),
                    'product_type': p.type,
                    'template_id': tpl.id,
                    'template_name': t_name,
                    'description': t_desc,
                    'ar_name': getattr(tpl, 'ar_name', None),
                    'ar_description': getattr(tpl, 'ar_description', None),
                    'detailed_type': getattr(tpl, 'detailed_type', None),
                    'category': tpl.categ_id.display_name if tpl.categ_id else None,
                    'price': float(getattr(tpl, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(tpl, 'price_after_discount', 0.0) or 0.0),
                    'currency': tpl.currency_id.name if tpl.currency_id else None,
                    'avg_rating': float(getattr(tpl, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(tpl, 'top', False)),
                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,
                    'company_id': p.company_id.name if p.company_id else None,
                })

            resp = {
                'category': {
                    'id': category.id,
                    'name': category.display_name,
                    'include_children': include_children,
                },
                'paging': {
                    'total': total,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                },
                'products': data,
            }
            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_by_category failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)


    # @http.route(
    #     '/api/products/general',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def products_general(self, **kwargs):
    #     """
    #     General Products Endpoint
    #     Returns ALL products OR specific product if product_id is provided.
    #
    #     Query params:
    #       - product_id: int (optional)
    #       - limit: int (default 100)
    #       - offset: int (default 0)
    #       - warehouse_id: int (optional)
    #       - lang: 'ar' or 'en' (default 'en')
    #     """
    #     try:
    #         lang = (kwargs.get('lang') or 'en').lower()
    #         limit = int(kwargs.get('limit', 100))
    #         offset = int(kwargs.get('offset', 0))
    #         warehouse_id = kwargs.get('warehouse_id')
    #         product_id = kwargs.get('product_id')
    #
    #         Product = request.env['product.product'].sudo()
    #
    #         if warehouse_id:
    #             try:
    #                 warehouse_id = int(warehouse_id)
    #                 Product = Product.with_context(warehouse=warehouse_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid warehouse_id'}, status=400)
    #
    #
    #         domain = [('sale_ok', '=', True)]
    #
    #         if product_id:
    #             try:
    #                 domain.append(('id', '=', int(product_id)))
    #                 limit = 1
    #                 offset = 0
    #             except Exception:
    #                 return self._json({'error': 'Invalid product_id'}, status=400)
    #
    #         total = Product.search_count(domain)
    #         products = Product.search(domain, limit=limit, offset=offset, order='id')
    #
    #         data = []
    #         for p in products:
    #             tpl = p.product_tmpl_id
    #
    #             t_main = self._main_image_url(tpl) if hasattr(self, '_main_image_url') else None
    #             v_main = self._main_image_url(p) if hasattr(self, '_main_image_url') else None
    #             main_img_url = t_main or v_main
    #
    #             gallery_urls = []
    #             if hasattr(self, '_template_gallery'):
    #                 gallery = self._template_gallery(tpl) or []
    #                 gallery_urls = [g.get('url') for g in gallery if g.get('url')]
    #
    #             t_name = self._pt_name(tpl, lang) if hasattr(self, '_pt_name') else (
    #                     getattr(tpl, 'ar_name', None) or tpl.name)
    #             t_desc = self._pt_desc(tpl, lang) if hasattr(self, '_pt_desc') else (
    #                     getattr(tpl, 'ar_description', None) or tpl.description)
    #
    #             v_name = self._pp_name(p, lang) if hasattr(self, '_pp_name') else p.display_name
    #
    #             data.append({
    #                 'id': p.id,
    #                 'name': v_name,
    #                 'barcode': p.barcode,
    #                 'uom': p.uom_id.name if p.uom_id else None,
    #                 'qty': float(p.qty_available or 0.0),
    #
    #                 'product_type': p.type,
    #                 'template_id': tpl.id,
    #                 'template_name': t_name,
    #                 'description': t_desc,
    #
    #                 'ar_name': getattr(tpl, 'ar_name', None),
    #                 'ar_description': getattr(tpl, 'ar_description', None),
    #
    #                 'detailed_type': getattr(tpl, 'detailed_type', None),
    #                 'category': tpl.categ_id.display_name if tpl.categ_id else None,
    #
    #                 'price': float(getattr(tpl, 'list_price', 0.0) or 0.0),
    #                 'price_after_discount': float(getattr(tpl, 'price_after_discount', 0.0) or 0.0),
    #                 'currency': tpl.currency_id.name if tpl.currency_id else None,
    #
    #                 'avg_rating': float(getattr(tpl, 'avg_rating', 0.0) or 0.0),
    #                 'top': bool(getattr(tpl, 'top', False)),
    #
    #                 'main_image_url': main_img_url,
    #                 'gallery_urls': gallery_urls,
    #
    #                 'company_id': p.company_id.name if p.company_id else None,
    #             })
    #
    #         resp = {
    #             'paging': {
    #                 'total': total,
    #                 'count': len(data),
    #                 'limit': limit,
    #                 'offset': offset,
    #             },
    #             'products': data,
    #         }
    #
    #         return self._json(resp, status=200)
    #
    #     except Exception as e:
    #         _logger.exception("products_general failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/products/general',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_general(self, **kwargs):
        """
        General Products Endpoint
        Returns ALL products OR specific product if product_id is provided.

        Query params:
          - product_id: int (optional)
          - limit: int (default 100)
          - offset: int (default 0)
          - warehouse_id: int (optional)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))
            warehouse_id = kwargs.get('warehouse_id')
            product_id = kwargs.get('product_id')

            Product = request.env['product.product'].sudo()

            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Product = Product.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [('sale_ok', '=', True)]

            if product_id:
                try:
                    domain.append(('id', '=', int(product_id)))
                    limit = 1
                    offset = 0
                except Exception:
                    return self._json({'error': 'Invalid product_id'}, status=400)

            total = Product.search_count(domain)
            products = Product.search(domain, limit=limit, offset=offset, order='id')

            data = []
            for p in products:
                tpl = p.product_tmpl_id

                # ================= Images =================
                t_main = self._main_image_url(tpl) if hasattr(self, '_main_image_url') else None
                v_main = self._main_image_url(p) if hasattr(self, '_main_image_url') else None
                main_img_url = t_main or v_main

                gallery_urls = []
                if hasattr(self, '_template_gallery'):
                    gallery = self._template_gallery(tpl) or []
                    gallery_urls = [g.get('url') for g in gallery if g.get('url')]

                # ================= Names & Descriptions =================
                t_name = self._pt_name(tpl, lang) if hasattr(self, '_pt_name') else (
                        getattr(tpl, 'ar_name', None) or tpl.name)

                t_desc = self._pt_desc(tpl, lang) if hasattr(self, '_pt_desc') else (
                        getattr(tpl, 'ar_description', None) or tpl.description)

                v_name = self._pp_name(p, lang) if hasattr(self, '_pp_name') else p.display_name

                # ================= Appointment Packages (ONLY services) =================
                appointment_package_lines = []

                if getattr(tpl, 'detailed_type', None) == 'service':
                    for line in p.appointment_package_line_ids:
                        appointment_package_lines.append({
                            'package_line_id': line.id,
                            'product_id': line.product_id.id,
                            'name': line.product_id.name,
                            'branch_id': line.branch_id.id if line.branch_id else None,
                            'department_id': line.department_id.id if line.department_id else None,
                            'service_slot_inside': line.service_slot_inside,
                            'service_slot_outside': line.service_slot_outside,
                            'service_price_inside': line.service_price_inside,
                            'service_price_outside': line.service_price_outside,
                            'currency_id': line.currency_id.id if line.currency_id else None,
                        })

                # ================= Response Object =================
                data.append({
                    'id': p.id,
                    'name': v_name,
                    'barcode': p.barcode,
                    'uom': p.uom_id.name if p.uom_id else None,
                    'qty': float(p.qty_available or 0.0),

                    'product_type': p.type,
                    'template_id': tpl.id,
                    'template_name': t_name,
                    'description': t_desc,

                    'ar_name': getattr(tpl, 'ar_name', None),
                    'ar_description': getattr(tpl, 'ar_description', None),

                    'detailed_type': getattr(tpl, 'detailed_type', None),
                    'category': tpl.categ_id.display_name if tpl.categ_id else None,

                    'price': float(getattr(tpl, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(tpl, 'price_after_discount', 0.0) or 0.0),
                    'currency': tpl.currency_id.name if tpl.currency_id else None,

                    'avg_rating': float(getattr(tpl, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(tpl, 'top', False)),

                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,

                    'appointment_package_lines': appointment_package_lines,

                    'company_id': p.company_id.name if p.company_id else None,
                })

            resp = {
                'paging': {
                    'total': total,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                },
                'products': data,
            }

            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_general failed")
            return self._json(
                {'error': 'Internal server error', 'details': str(e)},
                status=500
            )

    @http.route(
        '/api/products/top',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_top(self, **kwargs):
        """
        Top products (by avg_rating), mirroring /api/product_template/<id> fields and
        returning variant attribute lines. If a variant has no PTAVs selected,
        we fallback to template attribute lines and include all possible values.

        Query params:
          - limit: int (default 3)
          - min_rating: float (default 0.0)
          - category_id: int (optional; filter by category)
          - include_children: 1/0 (default 0)
          - warehouse_id: int (optional)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 3))
            min_rating = float(kwargs.get('min_rating', 0.0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            warehouse_id = kwargs.get('warehouse_id')

            Tpl = request.env['product.template'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [
                ('sale_ok', '=', True),
                ('active', '=', True),
                ('avg_rating', '>=', min_rating),
                ('detailed_type', '=', 'product'),

            ]
            if category_id:
                try:
                    category_id = int(category_id)
                except Exception:
                    return self._json({'error': 'Invalid category_id'}, status=400)
                if include_children:
                    domain.append(('categ_id', 'child_of', category_id))
                else:
                    domain.append(('categ_id', '=', category_id))

            templates = Tpl.search(domain, limit=limit, order='avg_rating desc, name asc')
            total = len(templates)

            def _variant_ptav_lines(variant):
                """Selected PTAVs for a variant: [{'ptav_id','attribute_id','attribute','value_id','value'}]."""
                out = []
                if 'product_template_attribute_value_ids' in variant._fields:
                    for ptav in variant.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        out.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'value_id': val.id if val else None,
                            'value': val.name if val else getattr(ptav, 'name', None),
                        })
                return out

            def _variant_attributes_kv_from_ptav(variant):
                """Simple {'Color': 'Red', ...} only from PTAVs."""
                kv = {}
                if 'product_template_attribute_value_ids' in variant._fields:
                    for ptav in variant.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        key = (attr and attr.name) or None
                        value = (val and val.name) or getattr(ptav, 'name', None)
                        if key:
                            kv[key] = value
                return kv

            def _template_attribute_lines_all_values(tmpl):
                """
                Fallback for templates with no PTAVs on variants:
                [{
                  'attribute_id', 'attribute',
                  'values': [{'value_id','value'}, ...]
                }]
                """
                lines = []
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        attr = al.attribute_id
                        vals = []
                        for v in al.value_ids:
                            vals.append({'value_id': v.id, 'value': v.name})
                        lines.append({
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'values': vals,
                        })
                return lines

            def _attributes_kv_from_singletons(tmpl):
                """
                If an attribute has exactly one possible value on the template,
                expose it as a default in attributes_kv.
                """
                kv = {}
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        if len(al.value_ids) == 1:
                            attr = al.attribute_id
                            v = al.value_ids[0]
                            if attr and v:
                                kv[attr.name] = v.name
                return kv

            data = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []

                variants_payload = []
                for v in t.product_variant_ids:
                    v_name = self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name
                    v_img = self._main_image_url(v) if hasattr(self, '_main_image_url') else None

                    ptav_lines = _variant_ptav_lines(v)
                    kv = _variant_attributes_kv_from_ptav(v)

                    is_configurable = False
                    if not ptav_lines:
                        tmpl_lines = _template_attribute_lines_all_values(t)
                        ptav_lines = tmpl_lines
                        kv = _attributes_kv_from_singletons(t)
                        is_configurable = any((len(l.get('values', [])) > 1) for l in tmpl_lines)

                    variants_payload.append({
                        'id': v.id,
                        'name': v_name,
                        'barcode': v.barcode,
                        'qty': float(v.qty_available or 0.0),
                        'uom': v.uom_id.name if v.uom_id else (t.uom_id.name if t.uom_id else None),
                        'product_image_url': v_img,
                        'attributes_kv': kv,
                        'lines': ptav_lines,
                        'is_configurable': is_configurable,
                    })

                t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
                t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description

                data.append({
                    'template_id': t.id,
                    'model': 'product.template',

                    'name': t_name,
                    'description': t_desc,

                    'detailed_type': getattr(t, 'detailed_type', None),
                    'category': t.categ_id.display_name if t.categ_id else None,

                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,

                    'qty': total_qty,
                    'uom': t.uom_id.name if t.uom_id else None,
                    'barcode': t.barcode,
                    'avg_rating': float(t.avg_rating or 0.0),
                    'top': getattr(t, 'top', None),

                    'main_image_url': main_img_url,
                    'gallery': gallery,

                    'variants': variants_payload,
                })

            data = sorted(data, key=lambda x: (-x.get('avg_rating', 0), x.get('name', '')))


            resp = {
                'filters': {
                    'min_rating': min_rating,
                    'limit': limit,
                    'category_id': category_id,
                    'include_children': bool(include_children and category_id),
                    'warehouse_id': warehouse_id,
                    'lang': lang,
                },
                'count': total,
                'products': data,
            }
            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_top failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/services/top',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def services_top(self, **kwargs):
        """
        Top services only (detailed_type = 'service')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 3))
            min_rating = float(kwargs.get('min_rating', 0.0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            warehouse_id = kwargs.get('warehouse_id')

            Tpl = request.env['product.template'].sudo()

            domain = [
                ('sale_ok', '=', True),
                ('active', '=', True),
                ('avg_rating', '>=', min_rating),
                ('detailed_type', '=', 'service'),
            ]

            if category_id:
                try:
                    category_id = int(category_id)
                except Exception:
                    return self._json({'error': 'Invalid category_id'}, status=400)

                if include_children:
                    domain.append(('categ_id', 'child_of', category_id))
                else:
                    domain.append(('categ_id', '=', category_id))

            templates = Tpl.search(domain, limit=limit, order='avg_rating desc, name asc')
            total = len(templates)

            data = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []

                t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
                t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description

                data.append({
                    'template_id': t.id,
                    'name': t_name,
                    'description': t_desc,
                    'detailed_type': t.detailed_type,
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(t.list_price or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,
                    'avg_rating': float(t.avg_rating or 0.0),
                    'main_image_url': main_img_url,
                    'gallery': gallery,
                })

            data = sorted(data, key=lambda x: (-x.get('avg_rating', 0), x.get('name', '')))

            return self._json({
                'filters': {
                    'min_rating': min_rating,
                    'limit': limit,
                    'category_id': category_id,
                    'include_children': include_children,
                    'lang': lang,
                },
                'count': total,
                'products': data,
            })

        except Exception as e:
            _logger.exception("services_top failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/products/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_search(self, **kwargs):
        """
        Search products and return grouped product.templates with rich fields and variant lines.

        Query params:
          - q: string (required; search keyword)
          - limit: int (default 50)       # applies to the number of templates returned
          - offset: int (default 0)
          - warehouse_id: int (optional; compute qty per warehouse)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            query = kwargs.get('q')
            if not query:
                return self._json({'error': 'Missing search query param `q`'}, status=400)

            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            warehouse_id = kwargs.get('warehouse_id')

            Product = request.env['product.product'].sudo()
            Template = request.env['product.template'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Product = Product.with_context(warehouse=warehouse_id)
                    Template = Template.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [
                ('sale_ok', '=', True),
                '|', '|', '|',
                ('name', 'ilike', query),
                ('ar_name', 'ilike', query),
                ('product_tmpl_id.categ_id.name', 'ilike', query),
                ('barcode', 'ilike', query),
            ]

            found_products = Product.search(domain, order='id')
            found_templates = found_products.mapped('product_tmpl_id')
            total_templates = len(found_templates)
            templates = found_templates[offset: offset + limit]

            def _variant_ptav_lines(variant):
                """Selected PTAVs for a variant: [{'ptav_id','attribute_id','attribute','value_id','value'}]."""
                out = []
                if 'product_template_attribute_value_ids' in variant._fields:
                    for ptav in variant.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        out.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'value_id': val.id if val else None,
                            'value': val.name if val else getattr(ptav, 'name', None),
                        })
                return out

            def _variant_attributes_kv_from_ptav(variant):
                """Simple {'Color': 'Red', ...} only from PTAVs."""
                kv = {}
                if 'product_template_attribute_value_ids' in variant._fields:
                    for ptav in variant.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        key = (attr and attr.name) or None
                        value = (val and val.name) or getattr(ptav, 'name', None)
                        if key:
                            kv[key] = value
                return kv

            def _template_attribute_lines_all_values(tmpl):
                """
                Fallback for templates with no PTAVs on variants:
                [{
                  'attribute_id', 'attribute',
                  'values': [{'value_id','value'}, ...]
                }]
                """
                lines = []
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        attr = al.attribute_id
                        vals = [{'value_id': v.id, 'value': v.name} for v in al.value_ids]
                        lines.append({
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'values': vals,
                        })
                return lines

            def _attributes_kv_from_singletons(tmpl):
                """
                If an attribute has exactly one possible value on the template,
                expose it as a default in attributes_kv.
                """
                kv = {}
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        if len(al.value_ids) == 1:
                            attr = al.attribute_id
                            v = al.value_ids[0]
                            if attr and v:
                                kv[attr.name] = v.name
                return kv

            results = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []

                variants_payload = []
                for v in t.product_variant_ids:
                    v_name = self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name
                    v_img = self._main_image_url(v) if hasattr(self, '_main_image_url') else None

                    ptav_lines = _variant_ptav_lines(v)
                    kv = _variant_attributes_kv_from_ptav(v)

                    is_configurable = False
                    if not ptav_lines:
                        tmpl_lines = _template_attribute_lines_all_values(t)
                        ptav_lines = tmpl_lines
                        kv = _attributes_kv_from_singletons(t)
                        is_configurable = any((len(l.get('values', [])) > 1) for l in tmpl_lines)

                    variants_payload.append({
                        'id': v.id,
                        'name': v_name,
                        # 'barcode': v.barcode,
                        'qty': float(v.qty_available or 0.0),
                        # 'uom': v.uom_id.name if v.uom_id else (t.uom_id.name if t.uom_id else None),
                        'product_image_url': v_img,
                        'attributes_kv': kv,
                        'lines': ptav_lines,
                        'is_configurable': is_configurable,
                    })

                t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
                t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description

                results.append({
                    'template_id': t.id,
                    # 'model': 'product.template',

                    'name': t_name,
                    # 'description': t_desc,

                    'detailed_type': getattr(t, 'detailed_type', None),
                    'category': t.categ_id.display_name if t.categ_id else None,

                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    # 'currency': t.currency_id.name if t.currency_id else None,

                    # 'qty': total_qty,
                    # 'uom': t.uom_id.name if t.uom_id else None,
                    # 'barcode': t.barcode,
                    # 'avg_rating': float(t.avg_rating or 0.0),
                    # 'top': getattr(t, 'top', None),

                    'main_image_url': main_img_url,
                    # 'gallery': gallery,

                    # 'variants': variants_payload,
                })

            resp = {
                'query': query,
                'paging': {
                    'total': total_templates,
                    'count': len(results),
                    'limit': limit,
                    'offset': offset,
                },
                'results': results,
            }
            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_search failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/products/advanced_search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def advanced_products_search(self, **kwargs):
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))

            q = kwargs.get('q')
            min_price = kwargs.get('min_price')
            max_price = kwargs.get('max_price')
            rating = kwargs.get('rating')
            category_id = kwargs.get('category_id')
            is_discount = str(kwargs.get('is_discount', '0')) in ('1', 'true', 'yes')

            Template = request.env['product.template'].sudo()

            # -------------------------
            # BUILD DOMAIN
            # -------------------------
            domain = [('sale_ok', '=', True)]

            if q:
                domain += ['|', '|',
                           ('name', 'ilike', q),
                           ('ar_name', 'ilike', q),
                           ('barcode', 'ilike', q),
                           ]

            if min_price:
                domain.append(('list_price', '>=', float(min_price)))

            if max_price:
                domain.append(('list_price', '<=', float(max_price)))

            # Category filter
            if category_id:
                try:
                    ids = [int(x) for x in str(category_id).split(',')]
                    domain.append(('categ_id', 'in', ids))
                except:
                    return self._json({'error': 'Invalid category_id format'}, status=400)

            # Rating filter
            if rating:
                domain.append(('avg_rating', '>=', int(rating)))

            # -------------------------
            # SEARCH
            # -------------------------
            templates = Template.search(domain)

            # Handle discount filter in Python (cannot be in domain)
            if is_discount:
                templates = templates.filtered(
                    lambda t: t.price_after_discount and t.price_after_discount < t.list_price)

            total = len(templates)
            templates = templates[offset: offset + limit]

            # -------------------------
            # BUILD RESPONSE
            # -------------------------
            results = []
            for t in templates:
                name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
                img = self._main_image_url(t) if hasattr(self, '_main_image_url') else None

                results.append({
                    "id": t.id,
                    "name": name,
                    "price": float(t.list_price or 0.0),
                    "price_after_discount": float(t.price_after_discount or t.list_price or 0.0),
                    "category": t.categ_id.display_name if t.categ_id else None,
                    "detailed_type": t.detailed_type,
                    "rating": float(t.avg_rating or 0.0),
                    "is_discount": bool(t.price_after_discount and t.price_after_discount < t.list_price),
                    "main_image_url": img,
                })

            return self._json({
                "paging": {
                    "total": total,
                    "count": len(results),
                    "limit": limit,
                    "offset": offset,
                },
                "results": results
            })

        except Exception as e:
            _logger.exception("advanced_products_search failed")
            return self._json({'error': 'Internal error', 'details': str(e)}, status=500)




    def _json(self, payload, status=200):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept-Language, X-Lang, Lang, lang'
        }
        return Response(
            json.dumps(payload, ensure_ascii=False, default=str),
            status=status,
            mimetype='application/json',
            headers=headers
        )

    @http.route(
        '/api/products/search',
        type='http',
        auth='public',
        methods=['OPTIONS'],
        csrf=False
    )
    def options_products_search(self, **kwargs):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
        return Response(status=200, headers=headers)

    @http.route('/api/categories', type='http', auth='public', methods=['GET'], csrf=False)
    def categories_list(self, **kwargs):
        """
        Reads language from headers:
          - X-Lang: 'ar' or 'en' (preferred)
          - Accept-Language: standard header, picks best of ['ar','en']
        Query params:
          - limit: int (default 100)
          - offset: int (default 0)
        """
        try:
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))
            lang = _get_lang(kwargs)

            Cat = request.env['product.category'].sudo()
            order_fields = [f for f in ['parent_left', 'name', 'id'] if f in Cat._fields]
            order = ', '.join(order_fields) or 'id'

            total = Cat.search_count([])
            cats = Cat.search([], limit=limit, offset=offset, order=order)

            base_url = request.httprequest.host_url.rstrip('/')
            data = []

            for c in cats:
                img_url = None
                if getattr(c, "img", False):
                    img_url = f"{base_url}/api/public/image/product.category/{c.id}/img"

                loc_name = c.ar_name if (lang == 'ar' and getattr(c, 'ar_name', None)) else c.name
                loc_desc = c.ar_description if (lang == 'ar' and getattr(c, 'ar_description', None)) else c.description

                data.append({
                    "id": c.id,
                    "name": loc_name,
                    "description": loc_desc,
                    "parent_id": c.parent_id.id if c.parent_id else None,
                    "image_url": img_url,
                    "lang": lang,
                })

            return self._json({
                "paging": {
                    "total": total,
                    "count": len(data),
                    "limit": limit,
                    "offset": offset,
                },
                "categories": data,
            }, status=200)

        except Exception as e:
            _logger.exception("categories_list failed")
            return self._json({"error": "Internal server error", "details": str(e)}, status=500)

    def _image_url(self, model, rec_id, field, unique=None):
        """Return clean image URL without ?v= parameter."""
        base = request.httprequest.host_url.rstrip('/')
        return f"{base}/web/image/{model}/{rec_id}/{field}"

    @http.route('/api/categories/<int:category_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def category_get(self, category_id, **kwargs):
        try:
            Cat = request.env['product.category'].sudo()
            c = Cat.browse(category_id)
            if not c.exists():
                return self._json({'error': 'Category not found', 'category_id': category_id}, status=404)

            dt = c.write_date or c.create_date
            unique = dt.strftime('%Y%m%d%H%M%S') if dt else None
            img_url = self._image_url('product.category', c.id, 'img', unique=unique) if c.img else None

            return self._json({
                'id': c.id,
                'name': c.name,
                'ar_name': c.ar_name,
                'parent_id': c.parent_id.id if c.parent_id else None,
                'image_url': img_url,
            }, status=200)
        except Exception as e:
            _logger.exception("category_get failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route('/api/categories', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_categories(self, **kwargs):
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
        return Response(status=200, headers=headers)

    def _resolve_product_and_template(self, rec):
        """Return (product.product or None, product.template or None) from a record
        that may have product_id, product_variant_id, or product_tmpl_id.
        """
        prod = tmpl = None
        if 'product_id' in rec._fields and rec.product_id:
            prod = rec.product_id
            tmpl = prod.product_tmpl_id
        elif 'product_variant_id' in rec._fields and rec.product_variant_id:
            prod = rec.product_variant_id
            tmpl = prod.product_tmpl_id
        elif 'product_tmpl_id' in rec._fields and rec.product_tmpl_id:
            tmpl = rec.product_tmpl_id
        return prod, tmpl

    def _pick_lines_field(self, combo_rec):
        """Detect the correct One2many field on the combo record that holds lines."""
        candidates = ['line_ids', 'combo_line_ids', 'item_ids', 'items_ids', 'product_line_ids']
        likely_models = {'pos.combo.line', 'pos.combo.item', 'pos.combo.products', 'pos.combo.lines'}
        for fname, field in combo_rec._fields.items():
            if getattr(field, 'type', None) == 'one2many':
                comodel = getattr(field, 'comodel_name', '')
                if comodel in likely_models and fname not in candidates:
                    candidates.append(fname)

        for fname in candidates:
            if fname in combo_rec._fields:
                lines = getattr(combo_rec, fname)
                if lines:
                    return fname, lines
        for fname, field in combo_rec._fields.items():
            if getattr(field, 'type', None) == 'one2many':
                lines = getattr(combo_rec, fname)
                if lines:
                    return fname, lines
        return None, combo_rec.browse([])  # empty

    def _main_image_url(self, rec):
        if not rec or 'image_1920' not in rec._fields or not rec.image_1920:
            return None
        base = request.httprequest.host_url.rstrip('/')
        return f"{base}/api/public/image/{rec._name}/{rec.id}/image_1920"

    def _template_gallery(self, tmpl):
        """Return gallery list (like your product.template gallery)."""
        out = []
        if not tmpl or 'img_ids' not in tmpl._fields:
            return out
        for g in tmpl.img_ids:
            if not g.img:
                continue
            gdt = g.write_date or g.create_date
            gunique = gdt.strftime('%Y%m%d%H%M%S') if gdt else None
            out.append({
                'id': g.id,
                'name': g.name,
                'url': self._image_url('product.template.img', g.id, 'img', unique=gunique)
            })
        return out

    def _is_ar(self, lang):
        return (lang or '').lower().startswith('ar')

    def _pt_name(self, tmpl, lang):
        """product.template name localized."""
        if not tmpl:
            return None
        if self._is_ar(lang) and 'ar_name' in tmpl._fields and tmpl.ar_name:
            return tmpl.ar_name
        return tmpl.name

    def _pt_desc(self, tmpl, lang):
        """product.template description localized (HTML-safe field)."""
        if not tmpl:
            return None
        if self._is_ar(lang) and 'ar_description' in tmpl._fields and tmpl.ar_description:
            return tmpl.ar_description
        return tmpl.description

    def _pp_name(self, prod, lang):
        """product.product display name localized via its template when Arabic."""
        if not prod:
            return None
        if self._is_ar(lang):
            tmpl = prod.product_tmpl_id
            if tmpl and 'ar_name' in tmpl._fields and tmpl.ar_name:
                return tmpl.ar_name
        return prod.display_name

    def _line_name(self, line, ln_prod, ln_tmpl, lang):
        """Prefer line's own localized name if present, else product/template."""
        if self._is_ar(lang) and 'ar_name' in line._fields and getattr(line, 'ar_name'):
            return line.ar_name
        if 'name' in line._fields and getattr(line, 'name'):
            if self._is_ar(lang) and ln_tmpl and 'ar_name' in ln_tmpl._fields and ln_tmpl.ar_name:
                return ln_tmpl.ar_name
            return line.name
        if ln_prod:
            return self._pp_name(ln_prod, lang)
        if ln_tmpl:
            return self._pt_name(ln_tmpl, lang)
        return None

    def _line_desc(self, line, ln_tmpl, lang):
        """Prefer line's own localized description if available, else template’s."""
        if self._is_ar(lang) and 'ar_description' in line._fields and getattr(line, 'ar_description'):
            return line.ar_description
        return self._pt_desc(ln_tmpl, lang) if ln_tmpl else None

    def _combo_name(self, combo, tmpl, lang):
        """
        Localized combo record name:
        - if lang=ar and combo.ar_name -> use it
        - else combo.name
        - fallback to localized template name if combo.name is empty
        """
        if not combo:
            return self._pt_name(tmpl, lang) if tmpl else None
        if self._is_ar(lang) and 'ar_name' in combo._fields and combo.ar_name:
            return combo.ar_name
        if getattr(combo, 'name', None):
            return combo.name
        return self._pt_name(tmpl, lang) if tmpl else None

    def _combo_desc(self, combo, tmpl, lang):
        """
        Localized combo description:
        - if lang=ar and combo.ar_desc -> use it
        - else fallback to localized template description
        """
        if combo and self._is_ar(lang) and 'ar_desc' in combo._fields and combo.ar_desc:
            return combo.ar_desc
        return self._pt_desc(tmpl, lang) if tmpl else None

    @http.route(
        '/api/product_template/<int:template_id>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def product_template_get(self, template_id, **kwargs):
        """
        Get a specific product template by ID.

        Query params:
          - warehouse_id: int (optional; compute qty per warehouse)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            warehouse_id = kwargs.get('warehouse_id')

            Tpl = request.env['product.template'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            tmpl = Tpl.browse(template_id)
            if not tmpl.exists():
                return self._json({'error': 'Product template not found', 'id': template_id}, status=404)

            total_qty = sum(float(v.qty_available or 0.0) for v in tmpl.product_variant_ids)

            main_img_url = self._main_image_url(tmpl)
            gallery = self._template_gallery(tmpl)

            variants_payload = []
            for v in tmpl.product_variant_ids:
                attrs = []
                if 'product_template_attribute_value_ids' in v._fields:
                    for ptav in v.product_template_attribute_value_ids:
                        attr = ptav.attribute_id if hasattr(ptav, 'attribute_id') else False
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        attr_name = attr.name if attr else None
                        val_name = val.name if val else (getattr(ptav, 'name', None))
                        attrs.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr_name,
                            'value_id': val.id if val else None,
                            'value': val_name,
                        })

                variants_payload.append({
                    'id': v.id,
                    'name': self._pp_name(v, lang),
                    'barcode': v.barcode,
                    'qty': float(v.qty_available or 0.0),
                    'uom': v.uom_id.name if v.uom_id else (tmpl.uom_id.name if tmpl.uom_id else None),
                    'product_image_url': self._main_image_url(v),
                    'attributes': attrs,
                })

            payload = {
                'id': tmpl.id,
                'model': 'product.template',

                'name': self._pt_name(tmpl, lang),
                'description': self._pt_desc(tmpl, lang),

                'detailed_type': getattr(tmpl, 'detailed_type', None),
                'category': tmpl.categ_id.display_name if tmpl.categ_id else None,

                'price': float(getattr(tmpl, 'list_price', 0.0) or 0.0),
                'price_after_discount': float(getattr(tmpl, 'price_after_discount', 0.0) or 0.0),
                'currency': tmpl.currency_id.name if tmpl.currency_id else None,

                'qty': total_qty,
                'uom': tmpl.uom_id.name if tmpl.uom_id else None,
                'barcode': tmpl.barcode,
                'avg_rating': getattr(tmpl, 'avg_rating', None),
                'top': getattr(tmpl, 'top', None),

                'main_image_url': main_img_url,
                'gallery': gallery,

                'variants': variants_payload,
            }

            return self._json(payload, status=200)

        except Exception as e:
            _logger.exception("product_template_get failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/products/combos',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def products_combos(self, **kwargs):
        """
        List combo products where product.template.detailed_type = 'combo'
        with main image URL and gallery URLs.

        Query params:
          - limit: int (default 50)
          - offset: int (default 0)
          - category_id: int (optional; filter by category)
          - include_children: 1/0 (default 0; only when category_id provided)
          - warehouse_id: int (optional; compute qty per warehouse)
          - type_value: str (default 'combo')
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            warehouse_id = kwargs.get('warehouse_id')
            type_value = (kwargs.get('type_value') or 'combo').strip()

            Tpl = request.env['product.template'].sudo()
            if 'detailed_type' not in Tpl._fields:
                return self._json({'error': "Field 'detailed_type' not found on product.template"}, status=400)

            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [
                ('detailed_type', '=', type_value),
                ('sale_ok', '=', True),
                ('active', '=', True),
            ]

            if category_id:
                try:
                    category_id = int(category_id)
                except Exception:
                    return self._json({'error': 'Invalid category_id'}, status=400)

                if include_children:
                    domain.append(('categ_id', 'child_of', category_id))
                else:
                    domain.append(('categ_id', '=', category_id))

            templates = Tpl.search(domain, limit=limit, offset=offset, order='name asc')
            total = Tpl.search_count(domain)

            data = []
            for t in templates:
                dt = t.write_date or t.create_date
                unique = dt.strftime('%Y%m%d%H%M%S') if dt else None

                main_img_url = self._main_image_url(t)
                gallery = self._template_gallery(t)

                qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                combo_list = []
                if 'combo_ids' in t._fields:
                    for c in t.combo_ids:
                        prod, tmpl = self._resolve_product_and_template(c)

                        used_lines_field, lines = self._pick_lines_field(c)

                        lines_payload = []
                        for ln in lines:
                            ln_prod, ln_tmpl = self._resolve_product_and_template(ln)
                            if not tmpl and ln_tmpl:
                                tmpl = ln_tmpl

                            line_image_url = self._main_image_url(ln_prod) or self._main_image_url(
                                ln_tmpl)
                            line_gallery = self._template_gallery(ln_tmpl) if ln_tmpl else []

                            lines_payload.append({
                                'line_id': ln.id,
                                'name': self._line_name(ln, ln_prod, ln_tmpl, lang),

                                'product_id': ln_prod.id if ln_prod else None,
                                'product_name': self._pp_name(ln_prod, lang) if ln_prod else (
                                    self._pt_name(ln_tmpl, lang) if ln_tmpl else None),
                                'product_template_id': ln_tmpl.id if ln_tmpl else None,
                                'avg_rating': ln_tmpl.avg_rating if ln_tmpl else None,
                                'product_template_description': self._line_desc(ln, ln_tmpl, lang),

                                'image_url': line_image_url,
                                'gallery': line_gallery,
                            })

                        tmpl_desc = self._combo_desc(c, tmpl, lang)

                        combo_list.append({
                            'id': c.id,
                            'name': self._combo_name(c, tmpl, lang),
                            'base_price': float(getattr(c, 'base_price', 0.0) or 0.0) if hasattr(c,
                                                                                                 'base_price') else None,
                            'product_id': prod.id if prod else None,
                            'product_template_id': tmpl.id if tmpl else None,
                            'product_template_description': tmpl_desc,
                            'rate': getattr(tmpl, 'avg_rating', None) if tmpl else None,
                            'product_image_url': self._main_image_url(prod) if prod else None,
                            'product_template_image_url': self._main_image_url(tmpl) if tmpl else None,
                            'product_template_gallery': self._template_gallery(tmpl) if tmpl else [],
                            'lines': lines_payload,
                        })

                data.append({
                    'template_id': t.id,
                    'name': self._pt_name(t, lang),
                    'top': t.top,
                    'description': self._pt_desc(t, lang),
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(t.list_price or 0.0),
                    'price_after_discount': float(t.price_after_discount or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,
                    'product_type': t.type,
                    'detailed_type': t.detailed_type,
                    'qty': qty,
                    'avg_rating': t.avg_rating,
                    'main_image_url': main_img_url,
                    'gallery': gallery,
                    'combo_items': combo_list,
                })

            pagination = {
                'total': total,
                'limit': limit,
                'offset': offset,
                'current_page': (offset // limit) + 1 if limit else 1,
                'total_pages': math.ceil(total / limit) if limit else 1,
            }

            return self._json({
                'filters': {
                    'limit': limit,
                    'offset': offset,
                    'category_id': category_id,
                    'include_children': bool(include_children and category_id),
                    'warehouse_id': warehouse_id,
                    'type_value': type_value,
                },
                'pagination': pagination,
                'products_count': len(data),
                'products': data,
            }, status=200)

        except Exception as e:
            _logger.exception("products_combos failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)


    @http.route(
        '/api/services/combos/appointment',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def appointment_services_combos(self, **kwargs):
        """
        List appointment services where product.product.detailed_type = 'service' and associated appointment package lines.

        Query params:
          - limit: int (default 50)
          - offset: int (default 0)
          - branch_id: int (optional)
          - department_id: int (optional)
          - lang: 'ar' or 'en' (default 'en')
        """
        try:
            lang = kwargs.get('lang', 'en').lower()
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            branch_id = kwargs.get('branch_id')
            department_id = kwargs.get('department_id')

            Prod = request.env['product.product'].sudo()

            domain = [
                ('detailed_type', '=', 'service'),
                ('active', '=', True),
                ('sale_ok', '=', True),
            ]

            if branch_id:
                domain.append(('branch_id', '=', branch_id))
            if department_id:
                domain.append(('department_id', '=', department_id))

            products = Prod.search(domain, limit=limit, offset=offset, order='name asc')
            total = Prod.search_count(domain)

            data = []
            for p in products:

                appointment_lines = p.appointment_package_line_ids
                # appointment_lines = p.appointment_package_line_ids.filtered(
                #     lambda line: line.branch_id == branch_id and line.department_id == department_id)

                service_data = []
                for line in appointment_lines:
                    service_data.append({
                        'package_line_id': line.id,
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'branch_id': line.branch_id.id,
                        'department_id': line.department_id.id,
                        'service_slot_inside': line.service_slot_inside,
                        'service_slot_outside': line.service_slot_outside,
                        'service_price_inside': line.service_price_inside,
                        'service_price_outside': line.service_price_outside,
                        'currency_id': line.currency_id.id,
                    })

                data.append({
                    'product_id': p.id,
                    'name': p.name,
                    'description': p.description,
                    'appointment_lines': service_data,
                })

            pagination = {
                'total': total,
                'limit': limit,
                'offset': offset,
                'current_page': (offset // limit) + 1 if limit else 1,
                'total_pages': math.ceil(total / limit) if limit else 1,
            }

            return self._json({
                'filters': {
                    'limit': limit,
                    'offset': offset,
                    'branch_id': branch_id,
                    'department_id': department_id,
                },
                'pagination': pagination,
                'services_count': len(data),
                'services': data,
            }, status=200)

        except Exception as e:
            _logger.exception("appointment_services_combos failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)



    # @http.route(
    #     '/api/services',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def services_list(self, **kwargs):
    #     """
    #     List service product templates (detailed_type = 'service').
    #
    #     Query params:
    #       - limit: int (default 50)
    #       - offset: int (default 0)
    #       - q: str (optional; search)
    #       - category_id: int (optional; filter by category)
    #       - include_children: 1/0 (default 0)
    #       - warehouse_id: int (optional)
    #       - lang: 'ar' or 'en' (header or query)  <-- يحدد المخرجات والبحث والترتيب
    #       - order: str (default 'name asc'; supports 'localized_name asc|desc')
    #     """
    #     try:
    #         lang = _get_lang(kwargs)
    #         limit = int(kwargs.get('limit', 50))
    #         offset = int(kwargs.get('offset', 0))
    #         include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
    #         category_id = kwargs.get('category_id')
    #         q = (kwargs.get('q') or '').strip()
    #         warehouse_id = kwargs.get('warehouse_id')
    #         order_raw = (kwargs.get('order') or 'name asc').strip()
    #
    #         if order_raw.lower().startswith('localized_name'):
    #             direction = 'desc' if order_raw.lower().endswith('desc') else 'asc'
    #             order = ('ar_name ' if lang == 'ar' else 'name ') + direction
    #         else:
    #             order = order_raw
    #
    #         Tpl = request.env['product.template'].sudo()
    #         if warehouse_id:
    #             try:
    #                 warehouse_id = int(warehouse_id)
    #                 Tpl = Tpl.with_context(warehouse=warehouse_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid warehouse_id'}, status=400)
    #
    #         domain = [
    #             ('is_appointment_service', '=', True),
    #             ('detailed_type', '=', 'service'),
    #             ('sale_ok', '=', True),
    #             ('active', '=', True),
    #         ]
    #
    #         if category_id:
    #             try:
    #                 category_id = int(category_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid category_id'}, status=400)
    #             domain.append(('categ_id', 'child_of' if include_children else '=', category_id))
    #
    #         if q:
    #             if lang == 'ar' and 'ar_name' in Tpl._fields:
    #                 domain += ['|', '|', '|', '|',
    #                            ('ar_name', 'ilike', q),
    #                            ('ar_description', 'ilike', q) if 'ar_description' in Tpl._fields else ('name', 'ilike',
    #                                                                                                    q),
    #                            ('name', 'ilike', q),
    #                            ('barcode', 'ilike', q),
    #                            ('default_code', 'ilike', q)]
    #             else:
    #                 domain += ['|', '|', '|',
    #                            ('name', 'ilike', q),
    #                            ('barcode', 'ilike', q),
    #                            ('default_code', 'ilike', q),
    #                            ('ar_name', 'ilike', q) if 'ar_name' in Tpl._fields else ('name', 'ilike', q)
    #                            ]
    #
    #         total = Tpl.search_count(domain)
    #         templates = Tpl.search(domain, limit=limit, offset=offset, order=order)
    #
    #         def _variant_attrs(v):
    #             attrs = []
    #             if 'product_template_attribute_value_ids' in v._fields:
    #                 for ptav in v.product_template_attribute_value_ids:
    #                     attr = getattr(ptav, 'attribute_id', False)
    #                     val = getattr(ptav, 'product_attribute_value_id', False)
    #                     attrs.append({
    #                         'ptav_id': ptav.id,
    #                         'attribute_id': attr.id if attr else None,
    #                         'attribute': attr.name if attr else None,
    #                         'value_id': val.id if val else None,
    #                         'value': val.name if val else getattr(ptav, 'name', None),
    #                     })
    #             return attrs
    #
    #         data = []
    #         for t in templates:
    #             total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
    #
    #             main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
    #             gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
    #             gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]
    #
    #             variants_payload = []
    #             for v in t.product_variant_ids:
    #                 variants_payload.append({
    #                     'id': v.id,
    #                     'name': self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name,
    #                     'barcode': v.barcode,
    #                     'qty': float(v.qty_available or 0.0),
    #                     'uom': v.uom_id.name if v.uom_id else (t.uom_id.name if t.uom_id else None),
    #                     'product_image_url': self._main_image_url(v) if hasattr(self, '_main_image_url') else None,
    #                     'attributes': _variant_attrs(v),
    #                 })
    #
    #             localized_category_name = (
    #                 (t.categ_id.ar_name if getattr(t.categ_id, 'ar_name', None) else t.categ_id.name)
    #                 if t.categ_id and lang == 'ar' else (t.categ_id.name if t.categ_id else None)
    #             )
    #
    #             data.append({
    #                 'id': t.id,
    #                 'model': 'product.template',
    #
    #                 'name': self._pt_name(t, lang),
    #                 'description': self._pt_desc(t, lang),
    #
    #                 'detailed_type': getattr(t, 'detailed_type', None),  # service
    #                 'category': localized_category_name,
    #
    #                 'price': float(getattr(t, 'list_price', 0.0) or 0.0),
    #                 'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
    #                 'currency': t.currency_id.name if t.currency_id else None,
    #
    #                 'qty': total_qty,
    #                 'uom': t.uom_id.name if t.uom_id else None,
    #                 'barcode': t.barcode,
    #
    #                 'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
    #                 'top': bool(getattr(t, 'top', False)),
    #
    #                 'main_image_url': main_img_url,
    #                 'gallery_urls': gallery_urls,
    #
    #                 'variants': variants_payload,
    #             })
    #
    #         return self._json({
    #             'filters': {
    #                 'q': q or None,
    #                 'category_id': category_id,
    #                 'include_children': bool(include_children and category_id),
    #                 'warehouse_id': warehouse_id,
    #                 'lang': lang,
    #                 'order': order,
    #             },
    #             'paging': {
    #                 'total': total,
    #                 'count': len(data),
    #                 'limit': limit,
    #                 'offset': offset,
    #             },
    #             'services': data,
    #         }, status=200)
    #
    #     except Exception as e:
    #         _logger.exception("services_list failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/services',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def services_list(self, **kwargs):
        """
        List service product templates (detailed_type = 'service') with associated service package details from product.product.

        Query params:
          - limit: int (default 50)
          - offset: int (default 0)
          - q: str (optional; search)
          - category_id: int (optional; filter by category)
          - include_children: 1/0 (default 0)
          - warehouse_id: int (optional)
          - lang: 'ar' or 'en' (header or query)
          - order: str (default 'name asc'; supports 'localized_name asc|desc')
        """
        try:
            lang = _get_lang(kwargs)
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            category_id = kwargs.get('category_id')
            q = (kwargs.get('q') or '').strip()
            warehouse_id = kwargs.get('warehouse_id')
            order_raw = (kwargs.get('order') or 'name asc').strip()

            if order_raw.lower().startswith('localized_name'):
                direction = 'desc' if order_raw.lower().endswith('desc') else 'asc'
                order = ('ar_name ' if lang == 'ar' else 'name ') + direction
            else:
                order = order_raw

            Tpl = request.env['product.template'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [
                ('is_appointment_service', '=', True),
                ('detailed_type', '=', 'service'),
                ('sale_ok', '=', True),
                ('active', '=', True),
            ]

            if category_id:
                try:
                    category_id = int(category_id)
                except Exception:
                    return self._json({'error': 'Invalid category_id'}, status=400)
                domain.append(('categ_id', 'child_of' if include_children else '=', category_id))

            if q:
                if lang == 'ar' and 'ar_name' in Tpl._fields:
                    domain += ['|', '|', '|', '|',
                               ('ar_name', 'ilike', q),
                               ('ar_description', 'ilike', q) if 'ar_description' in Tpl._fields else ('name', 'ilike',
                                                                                                       q),
                               ('name', 'ilike', q),
                               ('barcode', 'ilike', q),
                               ('default_code', 'ilike', q)]
                else:
                    domain += ['|', '|', '|',
                               ('name', 'ilike', q),
                               ('barcode', 'ilike', q),
                               ('default_code', 'ilike', q),
                               ('ar_name', 'ilike', q) if 'ar_name' in Tpl._fields else ('name', 'ilike', q)
                               ]

            total = Tpl.search_count(domain)
            templates = Tpl.search(domain, limit=limit, offset=offset, order=order)

            def _variant_attrs(v):
                attrs = []
                if 'product_template_attribute_value_ids' in v._fields:
                    for ptav in v.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        attrs.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'value_id': val.id if val else None,
                            'value': val.name if val else getattr(ptav, 'name', None),
                        })
                return attrs

            data = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
                gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

                variants_payload = []
                for v in t.product_variant_ids:
                    variants_payload.append({
                        'id': v.id,
                        'name': self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name,
                        'barcode': v.barcode,
                        'qty': float(v.qty_available or 0.0),
                        'uom': v.uom_id.name if v.uom_id else (t.uom_id.name if t.uom_id else None),
                        'product_image_url': self._main_image_url(v) if hasattr(self, '_main_image_url') else None,
                        'attributes': _variant_attrs(v),
                    })

                service_packages = []
                for v in t.product_variant_ids:
                    if 'appointment_package_line_ids' in v._fields:
                        for line in v.appointment_package_line_ids:
                            service_packages.append({
                                'package_line_id': line.id,
                                'product_id': line.product_id.id,
                                'service_slot_inside': line.service_slot_inside,
                                'service_slot_outside': line.service_slot_outside,
                                'service_price_inside': line.service_price_inside,
                                'service_price_outside': line.service_price_outside,
                                'currency_id': line.currency_id.id,
                            })

                localized_category_name = (
                    (t.categ_id.ar_name if getattr(t.categ_id, 'ar_name', None) else t.categ_id.name)
                    if t.categ_id and lang == 'ar' else (t.categ_id.name if t.categ_id else None)
                )

                data.append({
                    'id': t.id,
                    'model': 'product.template',

                    'name': self._pt_name(t, lang),
                    'description': self._pt_desc(t, lang),

                    'detailed_type': getattr(t, 'detailed_type', None),  # service
                    'category': localized_category_name,

                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,

                    'qty': total_qty,
                    'uom': t.uom_id.name if t.uom_id else None,
                    'barcode': t.barcode,

                    'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(t, 'top', False)),

                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,

                    'variants': variants_payload,
                    'service_packages': service_packages,  # Added service packages from product.product
                })

            return self._json({
                'filters': {
                    'q': q or None,
                    'category_id': category_id,
                    'include_children': bool(include_children and category_id),
                    'warehouse_id': warehouse_id,
                    'lang': lang,
                    'order': order,
                },
                'paging': {
                    'total': total,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                },
                'services': data,
            }, status=200)

        except Exception as e:
            _logger.exception("services_list failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)




    @http.route(
        '/api/storable_products',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def storable_products_list(self, **kwargs):
        """
        List storable product templates (detailed_type = 'product').

        Query params:
          - limit: int (default 50)
          - offset: int (default 0)
          - q: str (optional; search by name/ar_name/barcode/default_code)
          - category_id: int (optional; filter by category)
          - include_children: 1/0 (default 0; applies only when category_id provided)
          - warehouse_id: int (optional; compute qty per warehouse)
          - lang: 'ar' or 'en' (default 'en')
          - order: str (default 'name asc'; e.g. 'avg_rating desc, name asc')
          - in_stock: 1/0 (optional; if 1, only return templates with total qty > 0)
        """
        try:
            lang = (kwargs.get('lang') or 'en').lower()
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            category_id = kwargs.get('category_id')
            q = (kwargs.get('q') or '').strip()
            warehouse_id = kwargs.get('warehouse_id')
            # order = kwargs.get('order') or 'name asc'
            order = 'avg_rating desc NULLS LAST, name asc'

            in_stock = str(kwargs.get('in_stock', '0')).lower() in ('1', 'true', 'yes')

            Tpl = request.env['product.template'].sudo()
            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            domain = [
                ('detailed_type', '=', 'product'),
                ('sale_ok', '=', True),
                ('active', '=', True),
            ]

            if category_id:
                try:
                    category_id = int(category_id)
                except Exception:
                    return self._json({'error': 'Invalid category_id'}, status=400)
                if include_children:
                    domain.append(('categ_id', 'child_of', category_id))
                else:
                    domain.append(('categ_id', '=', category_id))

            if q:
                domain += ['|', '|', '|',
                           ('name', 'ilike', q),
                           ('ar_name', 'ilike', q) if 'ar_name' in Tpl._fields else ('name', 'ilike', q),
                           ('barcode', 'ilike', q),
                           ('default_code', 'ilike', q),
                           ]

            total = Tpl.search_count(domain)
            templates = Tpl.search(domain, limit=limit, offset=offset, order=order)

            def _variant_attrs(v):
                attrs = []
                if 'product_template_attribute_value_ids' in v._fields:
                    for ptav in v.product_template_attribute_value_ids:
                        attr = getattr(ptav, 'attribute_id', False)
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        attrs.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'value_id': val.id if val else None,
                            'value': val.name if val else getattr(ptav, 'name', None),
                        })
                return attrs

            data = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
                if in_stock and total_qty <= 1e-9:
                    continue

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
                gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

                variants_payload = []
                for v in t.product_variant_ids:
                    variants_payload.append({
                        'id': v.id,
                        'name': self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name,
                        'barcode': v.barcode,
                        'avg_rating': v.avg_rating,
                        'top': v.top,
                        'ar_name': v.ar_name,
                        'ar_description': v.ar_description,
                        'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                        # 'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                        'price_after_discount': v.price_after_discount,
                        'qty': float(v.qty_available or 0.0),
                        'uom': v.uom_id.name if v.uom_id else (t.uom_id.name if t.uom_id else None),
                        'product_image_url': self._main_image_url(v) if hasattr(self, '_main_image_url') else None,
                        'attributes': _variant_attrs(v),
                    })

                data.append({
                    'id': t.id,
                    'model': 'product.template',

                    'name': self._pt_name(t, lang) if hasattr(self, '_pt_name') else (
                            getattr(t, 'ar_name', None) or t.name),
                    'description': self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else (
                            getattr(t, 'ar_description', None) or t.description),

                    'detailed_type': getattr(t, 'detailed_type', None),  # 'product'
                    'category': t.categ_id.display_name if t.categ_id else None,

                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,

                    'qty': total_qty,
                    'uom': t.uom_id.name if t.uom_id else None,
                    'barcode': t.barcode,

                    'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(t, 'top', False)),

                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,

                    'ar_name': getattr(t, 'ar_name', None),
                    'ar_description': getattr(t, 'ar_description', None),

                    'variants': variants_payload,
                })

            return self._json({
                'filters': {
                    'q': q or None,
                    'category_id': category_id,
                    'include_children': bool(include_children and category_id),
                    'warehouse_id': warehouse_id,
                    'lang': lang,
                    'order': order,
                    'in_stock': in_stock,
                },
                'paging': {
                    'total': total,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                },
                'products': data,
            }, status=200)

        except Exception as e:
            _logger.exception("storable_products_list failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/services/similar',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def similar_services(self, **kwargs):
        """
        Find similar services based on combo packages that include the given service.
        Return localized names and descriptions dynamically (no ar_name/en_name duplication).
        """
        try:
            headers = request.httprequest.headers
            service_id = headers.get('Service-Id') or headers.get('service-id')
            if not service_id:
                return self._json({'error': 'Missing Service-Id header'}, status=400)

            try:
                service_id = int(service_id)
            except Exception:
                return self._json({'error': 'Invalid Service-Id'}, status=400)

            lang = _get_lang(kwargs)
            Tpl = request.env['product.template'].sudo()
            service = Tpl.browse(service_id)
            if not service.exists() or service.detailed_type != 'service':
                return self._json({'error': 'Service not found or not a service'}, status=404)

            ComboLine = request.env['pos.combo.line'].sudo()
            if 'product_tmpl_id' in ComboLine._fields:
                domain = [('product_tmpl_id', '=', service.id)]
            elif 'product_id' in ComboLine._fields:
                product_ids = service.product_variant_ids.ids
                domain = [('product_id', 'in', product_ids)]
            else:
                return self._json({'error': 'pos.combo.line has no product link field'}, status=500)

            combo_lines = ComboLine.search(domain)
            if not combo_lines:
                return self._json({
                    'message': 'No combos include this service',
                    'combos': [],
                    'similar_services': []
                }, status=200)

            combo_ids = combo_lines.mapped('combo_id').ids
            Combo = request.env['pos.combo'].sudo()
            combos = Combo.browse(combo_ids)

            all_lines = request.env['pos.combo.line'].browse()
            combo_payload = []

            for combo in combos:
                fname, lines = self._pick_lines_field(combo)
                if not lines:
                    continue

                items = []
                for ln in lines:
                    ln_prod, ln_tmpl = self._resolve_product_and_template(ln)
                    if not ln_tmpl:
                        continue

                    total_qty = sum(float(v.qty_available or 0.0) for v in ln_tmpl.product_variant_ids)
                    main_img_url = self._main_image_url(ln_tmpl)
                    gallery = self._template_gallery(ln_tmpl)
                    gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

                    items.append({
                        'id': ln_tmpl.id,
                        'name': self._pt_name(ln_tmpl, lang),
                        'description': self._pt_desc(ln_tmpl, lang),
                        'category': ln_tmpl.categ_id.display_name if ln_tmpl.categ_id else None,
                        'price': float(getattr(ln_tmpl, 'list_price', 0.0) or 0.0),
                        'price_after_discount': float(getattr(ln_tmpl, 'price_after_discount', 0.0) or 0.0),
                        'currency': ln_tmpl.currency_id.name if ln_tmpl.currency_id else None,
                        'qty': total_qty,
                        'uom': ln_tmpl.uom_id.name if ln_tmpl.uom_id else None,
                        'barcode': ln_tmpl.barcode,
                        'avg_rating': float(getattr(ln_tmpl, 'avg_rating', 0.0) or 0.0),
                        'top': bool(getattr(ln_tmpl, 'top', False)),
                        'main_image_url': main_img_url,
                        'gallery_urls': gallery_urls,
                    })

                combo_payload.append({
                    'id': combo.id,
                    'name': self._combo_name(combo, None, lang),
                    'description': self._combo_desc(combo, None, lang),
                    'price': float(getattr(combo, 'base_price', 0.0) or 0.0),
                    'currency': combo.currency_id.name if hasattr(combo, 'currency_id') else None,
                    'main_image_url': self._main_image_url(combo),
                    'items_count': len(items),
                    'items': items
                })

                all_lines |= lines

            related_products = all_lines.mapped('product_id')
            related_templates = related_products.mapped('product_tmpl_id')
            similar_services = related_templates.filtered(
                lambda s: s.detailed_type == 'service' and s.id != service.id
            )

            similar_payload = []
            for t in similar_services:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
                main_img_url = self._main_image_url(t)
                gallery = self._template_gallery(t)
                gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]
                similar_payload.append({
                    'id': t.id,
                    'name': self._pt_name(t, lang),
                    'description': self._pt_desc(t, lang),
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,
                    'qty': total_qty,
                    'uom': t.uom_id.name if t.uom_id else None,
                    'barcode': t.barcode,
                    'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(t, 'top', False)),
                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,
                })

            return self._json({
                'service_id': service.id,
                'service_name': self._pt_name(service, lang),
                'combos': combo_payload,
                'similar_services': similar_payload,
                'count': len(similar_payload),
                'lang': lang,
            }, status=200)

        except Exception as e:
            _logger.exception("similar_services failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/products/similar_by_tags',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def similar_products_by_tags(self, **kwargs):
        """
        Return products that share tags (product_tag_ids) with a given product.
        Reads Product-Id from headers.
        """
        try:
            headers = request.httprequest.headers
            product_id = headers.get('Product-Id') or headers.get('product-id')
            if not product_id:
                return self._json({'error': 'Missing Product-Id header'}, status=400)

            try:
                product_id = int(product_id)
            except Exception:
                return self._json({'error': 'Invalid Product-Id'}, status=400)

            lang = _get_lang(kwargs)
            warehouse_id = kwargs.get('warehouse_id')

            Tpl = request.env['product.template'].sudo()
            target = Tpl.browse(product_id)
            if not target.exists():
                return self._json({'error': 'Product not found'}, status=404)

            if warehouse_id:
                try:
                    warehouse_id = int(warehouse_id)
                    Tpl = Tpl.with_context(warehouse=warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            tag_ids = target.product_tag_ids.ids
            if not tag_ids:
                return self._json({
                    'message': 'Product has no tags, cannot find similar products',
                    'similar_products': []
                }, status=200)

            Similar = request.env['product.template'].sudo().search([
                ('id', '!=', target.id),
                ('product_tag_ids', 'in', tag_ids),
                ('sale_ok', '=', True),
                ('active', '=', True)
            ])

            products_with_score = []
            for s in Similar:
                common_tags = len(set(s.product_tag_ids.ids) & set(tag_ids))
                products_with_score.append((s, common_tags))

            products_with_score.sort(key=lambda x: x[1], reverse=True)
            similar_products = [p[0] for p in products_with_score[:20]]

            data = []
            for t in similar_products:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
                main_img_url = self._main_image_url(t)
                gallery = self._template_gallery(t)
                gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

                data.append({
                    'id': t.id,
                    'name': self._pt_name(t, lang),
                    'description': self._pt_desc(t, lang),
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'currency': t.currency_id.name if t.currency_id else None,
                    'qty': total_qty,
                    'uom': t.uom_id.name if t.uom_id else None,
                    'barcode': t.barcode,
                    'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    'top': bool(getattr(t, 'top', False)),
                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,
                    'shared_tags_count': len(set(t.product_tag_ids.ids) & set(tag_ids)),
                    'tags': [tag.name for tag in t.product_tag_ids],
                })

            return self._json({
                'product_id': target.id,
                'product_name': self._pt_name(target, lang),
                'count': len(data),
                'similar_products': data,
                'lang': lang,
            }, status=200)

        except Exception as e:
            _logger.exception("similar_products_by_tags failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
