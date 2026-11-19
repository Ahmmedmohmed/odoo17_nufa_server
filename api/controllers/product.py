import json
from odoo import http
from odoo.http import request, Response
import logging
from urllib.parse import urlencode
from werkzeug.datastructures import LanguageAccept
import math
import base64
from io import BytesIO
from odoo import api, fields, models, _
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


def _get_product_link(product_template):
    """
    Generate shareable website link for product/service/combo.
    Returns URL in format: https://domain/shop/product/<template_id>
    """
    try:
        base_url = request.httprequest.host_url.rstrip('/')
        template_id = product_template.id
        # Use Odoo's standard shop URL pattern
        return f"{base_url}/shop/product/{template_id}"
    except Exception as e:
        _logger.warning(f"Failed to generate product link: {e}")
        return None


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
        Fetch products by category with location-based warehouse detection,
        automatic translation from Headers, Real-time Average Rating,
        and Promotional Offers integration.
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            # تحويل اللغة ar/en إلى أكواد أودو القياسية
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع (Warehouse) بناءً على الموقع ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo calculation error in category API: {str(e)}")

            # المستودع النهائي (الموقع له الأولوية)
            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز الإعدادات الأساسية ---
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))

            Category = request.env['product.category'].sudo().with_context(lang=lang)
            category = Category.browse(category_id)
            if not category.exists():
                return self._json({'error': 'Category not found', 'category_id': category_id}, status=404)

            domain = [('sale_ok', '=', True)]
            if include_children:
                domain.append(('product_tmpl_id.categ_id', 'child_of', category_id))
            else:
                domain.append(('product_tmpl_id.categ_id', '=', category_id))

            # تمرير اللغة والمستودع في الـ Context
            Product = request.env['product.product'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            if final_warehouse_id:
                try:
                    final_warehouse_id = int(final_warehouse_id)
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

                t_name = self._pt_name(tpl, lang) if hasattr(self, '_pt_name') else (
                        getattr(tpl, 'ar_name', None) or tpl.name)
                t_desc = self._pt_desc(tpl, lang) if hasattr(self, '_pt_desc') else (
                        getattr(tpl, 'ar_description', None) or tpl.description)
                v_name = self._pp_name(p, lang) if hasattr(self, '_pp_name') else p.display_name

                # 🚀 --- حساب متوسط التقييم الحقيقي ---
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', tpl.id),
                    ('state', '!=', 'rejected')
                ])

                total_reviews = len(reviews)
                avg_rating = 0.0

                if total_reviews > 0:
                    total_score = sum(r.rating for r in reviews if 1 <= r.rating <= 5)
                    avg_rating = total_score / total_reviews

                # 🌟 فحص العروض الترويجية (بدون دوال خارجية) لتجنب الخطأ
                raw_desc = tpl.description_sale or ""
                offer_desc = raw_desc.strip()
                has_offer = bool(offer_desc)

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

                    'avg_rating': round(avg_rating, 2),

                    # === تم تعديل أسماء حقول العروض لتتناسق مع باقي الـ Endpoints 🎁 ===
                    'has_reward': has_offer,
                    'reward_description': offer_desc if has_offer else None,

                    'top': bool(getattr(tpl, 'top', False)),
                    'main_image_url': main_img_url,
                    'gallery_urls': gallery_urls,
                    'link': _get_product_link(tpl),
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
                'detected_lang': lang,
                'detected_warehouse': final_warehouse_id
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
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def products_general(self, **kwargs):
        """
        Unified Endpoint for Products & Services.
        """
        try:
            # --- 1. استخراج الـ Headers واللغة ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, 'en_US')

            # --- 2. الموقع الجغرافي والـ Context ---
            auto_warehouse_id = None
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0), ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except:
                    pass

            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')
            ctx = {'lang': lang, 'force_company': request.env.company.id}

            if final_warehouse_id:
                try:
                    f_wh_id = int(final_warehouse_id)
                    ctx.update({'warehouse': f_wh_id, 'warehouse_id': f_wh_id})
                except:
                    pass
            else:
                internal_locs = request.env['stock.location'].sudo().search([('usage', '=', 'internal')])
                ctx.update({'location': internal_locs.ids})

            # --- 🔥 جلب مكافآت الولاء مرة واحدة لتحسين الأداء 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            template_rewards = {}
            category_rewards = {}
            global_reward_desc = ""

            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                # 1. المنتجات المحددة
                if rule.product_ids:
                    for tmpl_id in rule.product_ids.mapped('product_tmpl_id').ids:
                        template_rewards[tmpl_id] = desc

                # 2. الفئات المحددة
                if getattr(rule, 'product_category_id', False):
                    category_rewards[rule.product_category_id.id] = desc

                # 3. العروض العامة
                if not rule.product_ids and not getattr(rule, 'product_category_id', False):
                    domain_rule = getattr(rule, 'product_domain', '[]')
                    if domain_rule == '[]' or not domain_rule:
                        global_reward_desc = desc

            # --- 3. دالة معالجة البيانات ---
            def _prepare_product_data(t_obj):
                t = t_obj.with_context(**ctx)
                variants = t.product_variant_ids.with_context(**ctx)
                total_qty = sum(float(v.qty_available or 0.0) for v in variants)

                def _get_description(obj):
                    return (obj.description_sale or
                            obj.description or
                            getattr(obj, 'website_description', "") or
                            "").strip()

                t_gallery = []
                if hasattr(t, 'product_template_image_ids'):
                    for img in t.product_template_image_ids:
                        t_gallery.append(f"{base_url}/api/image/product.image/{img.id}/image_1920")

                variants_payload = []
                for v in variants:
                    v_discount = getattr(v, 'price_after_discount', 0.0)
                    if not v_discount or v_discount <= 0:
                        v_discount = getattr(t, 'price_after_discount', 0.0)

                    v_gallery = []
                    if hasattr(v, 'product_variant_image_ids'):
                        for v_img in v.product_variant_image_ids:
                            v_gallery.append(f"{base_url}/api/image/product.image/{v_img.id}/image_1920")

                    variants_payload.append({
                        'id': v.id,
                        'name': v.display_name,
                        'description': _get_description(v) or _get_description(t),
                        'qty': float(v.qty_available or 0.0),
                        'price': float(t.list_price or 0.0),
                        'price_after_discount': float(v_discount or 0.0),
                        'gallery_urls': v_gallery,
                        'attributes': [{'attribute': p.attribute_id.name, 'value': p.name}
                                       for p in (
                                           v.product_template_attribute_value_ids if 'product_template_attribute_value_ids' in v._fields else [])],
                        'barcode': v.barcode,
                    })

                # 🚀 --- حساب إحصائيات التقييمات وجلب التعليقات ---
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id),
                    ('state', '!=', 'rejected')
                ], order='create_date desc')

                total_reviews = len(reviews)
                avg_rating = 0.0
                rating_percentages = {'5_star': 0.0, '4_star': 0.0, '3_star': 0.0, '2_star': 0.0, '1_star': 0.0}

                recent_reviews_list = []

                if total_reviews > 0:
                    total_score = 0
                    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

                    for r in reviews:
                        if 1 <= r.rating <= 5:
                            counts[r.rating] += 1
                            total_score += r.rating

                        avatar_url = f"{base_url}/web/image/res.partner/{r.partner_id.id}/avatar_128" if r.partner_id.image_128 else ""

                        recent_reviews_list.append({
                            'review_id': r.id,
                            'reviewer_name': r.partner_id.name,
                            'reviewer_image': avatar_url,
                            'rating': r.rating,
                            'comment': r.comment if r.state == 'approved' else None,
                            'date': r.create_date.strftime('%Y-%m-%d %H:%M:%S') if r.create_date else "",
                            'status': r.state
                        })

                    avg_rating = total_score / total_reviews

                    rating_percentages = {
                        '5_star': round((counts[5] / total_reviews) * 100, 1),
                        '4_star': round((counts[4] / total_reviews) * 100, 1),
                        '3_star': round((counts[3] / total_reviews) * 100, 1),
                        '2_star': round((counts[2] / total_reviews) * 100, 1),
                        '1_star': round((counts[1] / total_reviews) * 100, 1),
                    }

                # 🔥 فحص استحقاق المكافأة الفعلي (Loyalty Rewards)
                reward_desc = ""
                if t.id in template_rewards:
                    reward_desc = template_rewards[t.id]
                elif t.categ_id and t.categ_id.id in category_rewards:
                    reward_desc = category_rewards[t.categ_id.id]
                elif global_reward_desc:
                    reward_desc = global_reward_desc

                reward_desc = reward_desc.strip()
                has_reward = bool(reward_desc)

                # 🚀 التعديل الجديد: فصل مصدر القسم بناءً على نوع المنتج
                if t.detailed_type == 'service':
                    # لو المنتج عبارة عن خدمة، اقرأ من أقسام نقطة البيع
                    category_name = t.pos_categ_ids[0].name if hasattr(t, 'pos_categ_ids') and t.pos_categ_ids else None
                else:
                    # لو المنتج عادي (مخزني أو استهلاكي)، اقرأ من أقسام المخازن العادية
                    category_name = t.categ_id.display_name if t.categ_id else None

                res = {
                    'id': t.id,
                    'name': t.name,
                    'description': _get_description(t),
                    'qty': total_qty,
                    'price': float(t.list_price or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'detailed_type': t.detailed_type,

                    # === تم التحديث لقراءة المتغير الجديد بناءً على الشرط ===
                    'category': category_name,

                    'main_image_url': f"{base_url}/api/image/product.template/{t.id}/image_1920" if t.image_1920 else None,
                    'gallery_urls': t_gallery,
                    'top': bool(getattr(t, 'top', False)),

                    # === توحيد الحقول لترجع وصف الخصم الفعلي أو null ===
                    'has_reward': has_reward,
                    'reward_description': reward_desc if has_reward else None,

                    'review_statistics': {
                        'total_reviews': total_reviews,
                        'average_rating': round(avg_rating, 2),
                        'percentages': rating_percentages
                    },
                    'recent_reviews': recent_reviews_list[:5],
                    'variants': variants_payload,
                }

                # منطق الخدمات والـ Combo
                if t.detailed_type == 'service':
                    first_v = variants[0] if variants else False
                    lines = getattr(first_v, 'appointment_package_line_ids', []) if first_v else []
                    appointment_data = []
                    for line in lines:
                        line_prod = line.product_id.with_context(lang=lang)
                        appointment_data.append({
                            'package_line_id': line.id,
                            'name': line_prod.name,
                            'description': _get_description(line_prod),
                            'main_image_url': f"{base_url}/api/image/product.product/{line_prod.id}/image_1920" if line_prod.image_1920 else None,
                            'service_slot_inside': line.service_slot_inside,
                            'service_slot_outside': line.service_slot_outside,
                            'service_price_inside': line.service_price_inside,
                            'service_price_outside': line.service_price_outside,
                        })

                    if len(appointment_data) > 1:
                        res['detailed_type'] = 'combo'
                        res['appointment_package_lines'] = appointment_data
                    elif len(appointment_data) == 1:
                        res.update(appointment_data[0])

                return res

            # --- 4. التنفيذ والبحث ---
            product_id = kwargs.get('product_id')
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))

            if product_id:
                try:
                    p_id = int(product_id)
                    # 🚀 البحث في product.template الأول
                    target_tpl = request.env['product.template'].sudo().browse(p_id)

                    if not target_tpl.exists():
                        # لو ملقاهوش كـ Template، ندور في الـ Variant احتياطي
                        target_variant = request.env['product.product'].sudo().browse(p_id)
                        if target_variant.exists():
                            target_tpl = target_variant.product_tmpl_id

                    if not target_tpl.exists():
                        return self._json({'error': 'Product not found'}, status=404)

                    return self._json({'product': _prepare_product_data(target_tpl), 'status': 'success'}, status=200)
                except:
                    return self._json({'error': 'Invalid ID'}, status=400)
            else:
                TplModel = request.env['product.template'].sudo().with_context(**ctx)
                domain = [('sale_ok', '=', True), ('active', '=', True)]
                q = (kwargs.get('q') or '').strip()
                if q:
                    domain += ['|', ('name', 'ilike', q), ('barcode', 'ilike', q)]

                total = TplModel.search_count(domain)
                templates = TplModel.search(domain, limit=limit, offset=offset, order='id asc')

                data = [_prepare_product_data(t) for t in templates]

                return self._json({
                    'paging': {'total': total, 'count': len(data), 'limit': limit, 'offset': offset},
                    'products': data,
                    'status': 'success'
                }, status=200)

        except Exception as e:
            _logger.exception("products_general failed")
            return self._json({'error': str(e)}, status=500)

    def _get_distance(self, lat1, lon1, lat2, lon2):
        """Haversine formula to calculate distance between two points on Earth."""
        import math
        R = 6371  # Earth radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @http.route(
        '/api/products/top',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_top(self, **kwargs):
        """
        Top products (by avg_rating) with location-based warehouse detection
        and automatic translation context, using Real-time Review Calculation
        and Promotional Offers integration.
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع بناءً على الموقع الجغرافي ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat = float(header_lat)
                    u_lng = float(header_lng)

                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])

                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp

                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error: {str(e)}")

            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز الإعدادات الأساسية للـ API ---
            limit = int(kwargs.get('limit', 3))
            min_rating = float(kwargs.get('min_rating', 0.0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')

            Tpl = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            if final_warehouse_id:
                try:
                    final_warehouse_id = int(final_warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            # --- 4. بناء الـ Domain والبحث ---
            domain = [
                ('sale_ok', '=', True),
                ('active', '=', True),
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

            templates = Tpl.search(domain, order='name asc')

            # --- 5. الدوال الداخلية ---
            def _variant_ptav_lines(variant):
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
                kv = {}
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        if len(al.value_ids) == 1:
                            attr = al.attribute_id
                            v = al.value_ids[0]
                            if attr and v:
                                kv[attr.name] = v.name
                return kv

            # --- 6. تجميع البيانات النهائية والحساب الحقيقي للتقييم 🚀 ---
            data = []
            for t in templates:
                # 🚀 حساب التقييم الحقيقي من الداتابيز مباشرة
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id),
                    ('state', '!=', 'rejected')
                ])

                total_reviews = len(reviews)
                real_avg_rating = 0.0

                if total_reviews > 0:
                    total_score = sum(r.rating for r in reviews if 1 <= r.rating <= 5)
                    real_avg_rating = total_score / total_reviews

                # تطبيق فلتر min_rating بناءً على التقييم الحقيقي
                if real_avg_rating < min_rating:
                    continue

                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
                gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []

                # 🌟 فحص العروض الترويجية (لو فاضي يرجع None عشان تترجم لـ null في الـ JSON)
                raw_desc = t.description_sale or ""
                offer_desc = raw_desc.strip()
                has_offer = bool(offer_desc)

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
                    'avg_rating': round(real_avg_rating, 2),
                    'top': getattr(t, 'top', None),
                    'main_image_url': main_img_url,
                    'gallery': gallery,
                    'link': _get_product_link(t),

                    # === الحقول الخاصة بالعروض 🎁 ===
                    'has_reward': has_offer,
                    'reward_description': offer_desc if has_offer else None,

                    'variants': variants_payload,
                })

            # ترتيب البيانات بناءً على التقييم الحقيقي التنازلي، ثم الاسم
            data = sorted(data, key=lambda x: (-x.get('avg_rating', 0), x.get('name', '')))

            # تطبيق الـ Limit بعد الترتيب الصحيح
            total = len(data)
            data = data[:limit]

            # --- 7. الرد النهائي ---
            resp = {
                'filters': {
                    'min_rating': min_rating,
                    'limit': limit,
                    'category_id': category_id,
                    'include_children': bool(include_children and category_id),
                    'warehouse_id': final_warehouse_id,
                    'lang': raw_lang,
                },
                'count': len(data),
                'total_matching_products': total,
                'products': data,
            }
            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_top failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    # @http.route(
    #     '/api/services/top',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def services_top(self, **kwargs):
    #     """
    #     Top services only (detailed_type = 'service')
    #     """
    #     try:
    #         lang = (kwargs.get('lang') or 'en').lower()
    #         limit = int(kwargs.get('limit', 3))
    #         min_rating = float(kwargs.get('min_rating', 0.0))
    #         category_id = kwargs.get('category_id')
    #         include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
    #         warehouse_id = kwargs.get('warehouse_id')
    #
    #         Tpl = request.env['product.template'].sudo()
    #
    #         domain = [
    #             ('sale_ok', '=', True),
    #             ('active', '=', True),
    #             ('avg_rating', '>=', min_rating),
    #             ('detailed_type', '=', 'service'),
    #         ]
    #
    #         if category_id:
    #             try:
    #                 category_id = int(category_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid category_id'}, status=400)
    #
    #             if include_children:
    #                 domain.append(('categ_id', 'child_of', category_id))
    #             else:
    #                 domain.append(('categ_id', '=', category_id))
    #
    #         templates = Tpl.search(domain, limit=limit, order='avg_rating desc, name asc')
    #         total = len(templates)
    #
    #         data = []
    #         for t in templates:
    #             total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
    #
    #             main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
    #             gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
    #
    #             t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
    #             t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description
    #
    #             data.append({
    #                 'template_id': t.id,
    #                 'name': t_name,
    #                 'description': t_desc,
    #                 'detailed_type': t.detailed_type,
    #                 'category': t.categ_id.display_name if t.categ_id else None,
    #                 'price': float(t.list_price or 0.0),
    #                 'currency': t.currency_id.name if t.currency_id else None,
    #                 'avg_rating': float(t.avg_rating or 0.0),
    #                 'main_image_url': main_img_url,
    #                 'gallery': gallery,
    #             })
    #
    #         data = sorted(data, key=lambda x: (-x.get('avg_rating', 0), x.get('name', '')))
    #
    #         return self._json({
    #             'filters': {
    #                 'min_rating': min_rating,
    #                 'limit': limit,
    #                 'category_id': category_id,
    #                 'include_children': include_children,
    #                 'lang': lang,
    #             },
    #             'count': total,
    #             'products': data,
    #         })
    #
    #     except Exception as e:
    #         _logger.exception("services_top failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    def _prepare_service_payload(self, t, lang):
        """ Centralized helper to format product.template as a Service JSON object """
        # 1. Image Logic
        main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
        gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
        gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

        # 2. Variants and Service Packages logic
        variants_payload = []
        service_packages = []
        total_qty = 0

        for v in t.product_variant_ids:
            total_qty += v.qty_available
            variants_payload.append({
                'id': v.id,
                'name': self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name,
                'barcode': v.barcode,
                'qty': float(v.qty_available or 0.0),
                'uom': v.uom_id.name if v.uom_id else t.uom_id.name,
                'product_image_url': self._main_image_url(v) if hasattr(self, '_main_image_url') else None,
            })

            # Pull packages from the variant
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

        # 3. 🚀 POS Category Translation (جلب قسم نقطة البيع بدل القسم العادي)
        localized_category = None
        if getattr(t, 'pos_categ_ids', False) and t.pos_categ_ids:
            pos_cat = t.pos_categ_ids[0]  # جلب أول قسم POS مربوط بالخدمة
            # معالجة ذكية للغة عشان تقبل ar أو ar_001
            if lang in ('ar', 'ar_001'):
                localized_category = pos_cat.ar_name if getattr(pos_cat, 'ar_name', None) else pos_cat.name
            else:
                localized_category = pos_cat.name

        # Force fetch the field to ensure it's not a lazy-loading issue
        price_val = getattr(t, 'list_price', 0.0)
        # Ensure we get the actual value, even if it's stored as 0 in some records
        discounted_price = getattr(t, 'price_after_discount', 0.0)

        # If your logic requires that price_after_discount should never be 0
        # (i.e., if no discount, it should equal list_price), add this:
        if not discounted_price or discounted_price == 0:
            discounted_price = price_val

        return {
            'id': t.id,
            'name': self._pt_name(t, lang),
            'description': self._pt_desc(t, lang),
            'detailed_type': getattr(t, 'detailed_type', None),
            'category': localized_category,  # 🚀 هيرجع اسم قسم الـ POS مترجم!
            'price': float(getattr(t, 'list_price', 0.0)),
            'price_after_discount': float(discounted_price or 0.0),
            'currency': t.currency_id.name if t.currency_id else None,
            'qty': float(total_qty),
            'avg_rating': float(getattr(t, 'avg_rating', 0.0)),
            'top': bool(getattr(t, 'top', False)),
            'main_image_url': main_img_url,
            'gallery_urls': gallery_urls,
            'link': _get_product_link(t),
            'variants': variants_payload,
            'service_packages': service_packages,
        }
    # kabir commented
    # @http.route(
    #     '/api/services/top',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def services_top(self, **kwargs):
    #     """
    #     Top services only (detailed_type = 'service') 
    #     Including price_after_discount
    #     """
    #     try:
    #         lang = (kwargs.get('lang') or 'en').lower()

    #         limit = kwargs.get('limit', None)
    #         min_rating = kwargs.get('min_rating', None)

    #         category_id = kwargs.get('category_id')
    #         include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
    #         warehouse_id = kwargs.get('warehouse_id')

    #         Tpl = request.env['product.template'].sudo()

    #         domain = [
    #             ('sale_ok', '=', True),
    #             ('active', '=', True),
    #             ('detailed_type', '=', 'service'),
    #         ]

    #         if min_rating:
    #             try:
    #                 min_rating = float(min_rating)
    #                 domain.append(('avg_rating', '>=', min_rating))
    #             except ValueError:
    #                 return self._json({'error': 'Invalid min_rating value'}, status=400)

    #         if category_id:
    #             try:
    #                 category_id = int(category_id)
    #             except ValueError:
    #                 return self._json({'error': 'Invalid category_id'}, status=400)

    #             if include_children:
    #                 domain.append(('categ_id', 'child_of', category_id))
    #             else:
    #                 domain.append(('categ_id', '=', category_id))

    #         templates = Tpl.search(domain, limit=limit, order='avg_rating desc, name asc') if limit else Tpl.search(
    #             domain, order='avg_rating desc, name asc')
    #         total = len(templates)

    #         data = []
    #         for t in templates:
    #             # Logic for images and translations
    #             main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
    #             gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
    #             t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
    #             t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description

    #             # Added price_after_discount logic
    #             # Using getattr to safely check for the field on the model
    #             price_discounted = getattr(t, 'price_after_discount', 0.0)

    #             data.append({
    #                 'template_id': t.id,
    #                 'name': t_name,
    #                 'description': t_desc,
    #                 'detailed_type': t.detailed_type,
    #                 'category': t.categ_id.display_name if t.categ_id else None,
    #                 'price': float(t.list_price or 0.0),
    #                 'price_after_discount': float(price_discounted or 0.0), # Added Key
    #                 'currency': t.currency_id.name if t.currency_id else None,
    #                 'avg_rating': float(t.avg_rating or 0.0),
    #                 'main_image_url': main_img_url,
    #                 'gallery': gallery,
    #             })

    #         data = sorted(data, key=lambda x: (-x.get('avg_rating', 0), x.get('name', '')))

    #         return self._json({
    #             'filters': {
    #                 'min_rating': min_rating,
    #                 'limit': limit,
    #                 'category_id': category_id,
    #                 'include_children': include_children,
    #                 'lang': lang,
    #             },
    #             'count': total,
    #             'products': data,
    #         })

    #     except Exception as e:
    #         _logger.exception("services_top failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
        
    # @http.route(
    #     '/api/products/search',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def products_search(self, **kwargs):
    #     """
    #     Search products and return grouped product.templates with rich fields and variant lines.
    #
    #     Query params:
    #       - q: string (required; search keyword)
    #       - limit: int (default 50)       # applies to the number of templates returned
    #       - offset: int (default 0)
    #       - warehouse_id: int (optional; compute qty per warehouse)
    #       - lang: 'ar' or 'en' (default 'en')
    #     """
    #     try:
    #         query = kwargs.get('q')
    #         if not query:
    #             return self._json({'error': 'Missing search query param `q`'}, status=400)
    #
    #         lang = (kwargs.get('lang') or 'en').lower()
    #         limit = int(kwargs.get('limit', 50))
    #         offset = int(kwargs.get('offset', 0))
    #         warehouse_id = kwargs.get('warehouse_id')
    #
    #         Product = request.env['product.product'].sudo()
    #         Template = request.env['product.template'].sudo()
    #         if warehouse_id:
    #             try:
    #                 warehouse_id = int(warehouse_id)
    #                 Product = Product.with_context(warehouse=warehouse_id)
    #                 Template = Template.with_context(warehouse=warehouse_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid warehouse_id'}, status=400)
    #
    #         domain = [
    #             ('sale_ok', '=', True),
    #             '|', '|', '|',
    #             ('name', 'ilike', query),
    #             ('ar_name', 'ilike', query),
    #             ('product_tmpl_id.categ_id.name', 'ilike', query),
    #             ('barcode', 'ilike', query),
    #         ]
    #
    #         found_products = Product.search(domain, order='id')
    #         found_templates = found_products.mapped('product_tmpl_id')
    #         total_templates = len(found_templates)
    #         templates = found_templates[offset: offset + limit]
    #
    #         def _variant_ptav_lines(variant):
    #             """Selected PTAVs for a variant: [{'ptav_id','attribute_id','attribute','value_id','value'}]."""
    #             out = []
    #             if 'product_template_attribute_value_ids' in variant._fields:
    #                 for ptav in variant.product_template_attribute_value_ids:
    #                     attr = getattr(ptav, 'attribute_id', False)
    #                     val = getattr(ptav, 'product_attribute_value_id', False)
    #                     out.append({
    #                         'ptav_id': ptav.id,
    #                         'attribute_id': attr.id if attr else None,
    #                         'attribute': attr.name if attr else None,
    #                         'value_id': val.id if val else None,
    #                         'value': val.name if val else getattr(ptav, 'name', None),
    #                     })
    #             return out
    #
    #         def _variant_attributes_kv_from_ptav(variant):
    #             """Simple {'Color': 'Red', ...} only from PTAVs."""
    #             kv = {}
    #             if 'product_template_attribute_value_ids' in variant._fields:
    #                 for ptav in variant.product_template_attribute_value_ids:
    #                     attr = getattr(ptav, 'attribute_id', False)
    #                     val = getattr(ptav, 'product_attribute_value_id', False)
    #                     key = (attr and attr.name) or None
    #                     value = (val and val.name) or getattr(ptav, 'name', None)
    #                     if key:
    #                         kv[key] = value
    #             return kv
    #
    #         def _template_attribute_lines_all_values(tmpl):
    #             """
    #             Fallback for templates with no PTAVs on variants:
    #             [{
    #               'attribute_id', 'attribute',
    #               'values': [{'value_id','value'}, ...]
    #             }]
    #             """
    #             lines = []
    #             if 'attribute_line_ids' in tmpl._fields:
    #                 for al in tmpl.attribute_line_ids:
    #                     attr = al.attribute_id
    #                     vals = [{'value_id': v.id, 'value': v.name} for v in al.value_ids]
    #                     lines.append({
    #                         'attribute_id': attr.id if attr else None,
    #                         'attribute': attr.name if attr else None,
    #                         'values': vals,
    #                     })
    #             return lines
    #
    #         def _attributes_kv_from_singletons(tmpl):
    #             """
    #             If an attribute has exactly one possible value on the template,
    #             expose it as a default in attributes_kv.
    #             """
    #             kv = {}
    #             if 'attribute_line_ids' in tmpl._fields:
    #                 for al in tmpl.attribute_line_ids:
    #                     if len(al.value_ids) == 1:
    #                         attr = al.attribute_id
    #                         v = al.value_ids[0]
    #                         if attr and v:
    #                             kv[attr.name] = v.name
    #             return kv
    #
    #         results = []
    #         for t in templates:
    #             total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
    #
    #             main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
    #             gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
    #
    #             variants_payload = []
    #             for v in t.product_variant_ids:
    #                 v_name = self._pp_name(v, lang) if hasattr(self, '_pp_name') else v.display_name
    #                 v_img = self._main_image_url(v) if hasattr(self, '_main_image_url') else None
    #
    #                 ptav_lines = _variant_ptav_lines(v)
    #                 kv = _variant_attributes_kv_from_ptav(v)
    #
    #                 is_configurable = False
    #                 if not ptav_lines:
    #                     tmpl_lines = _template_attribute_lines_all_values(t)
    #                     ptav_lines = tmpl_lines
    #                     kv = _attributes_kv_from_singletons(t)
    #                     is_configurable = any((len(l.get('values', [])) > 1) for l in tmpl_lines)
    #
    #                 variants_payload.append({
    #                     'id': v.id,
    #                     'name': v_name,
    #                     'qty': float(v.qty_available or 0.0),
    #                     'product_image_url': v_img,
    #                     'attributes_kv': kv,
    #                     'lines': ptav_lines,
    #                     'is_configurable': is_configurable,
    #                 })
    #
    #             t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
    #             t_desc = self._pt_desc(t, lang) if hasattr(self, '_pt_desc') else t.description
    #
    #             results.append({
    #                 'template_id': t.id,
    #                 # 'model': 'product.template',
    #
    #                 'name': t_name,
    #                 # 'description': t_desc,
    #
    #                 'detailed_type': getattr(t, 'detailed_type', None),
    #                 'category': t.categ_id.display_name if t.categ_id else None,
    #
    #                 'price': float(getattr(t, 'list_price', 0.0) or 0.0),
    #                 'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
    #
    #                 'main_image_url': main_img_url,
    #             })
    #
    #         resp = {
    #             'query': query,
    #             'paging': {
    #                 'total': total_templates,
    #                 'count': len(results),
    #                 'limit': limit,
    #                 'offset': offset,
    #             },
    #             'results': results,
    #         }
    #         return self._json(resp, status=200)
    #
    #     except Exception as e:
    #         _logger.exception("products_search failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
    @http.route(
        '/api/products/search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def products_search(self, **kwargs):
        """
        Search products with location-based warehouse detection,
        automatic translation from Headers, Real-time Ratings,
        and Promotional Offers integration.
        """
        try:
            query = kwargs.get('q')
            if not query:
                return self._json({'error': 'Missing search query param `q`'}, status=400)

            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            # توحيد اللغة (ar -> ar_001, en -> en_US)
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع بناءً على الموقع الجغرافي ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location search error: {str(e)}")

            # المستودع النهائي (الأولوية للموقع الجغرافي)
            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز الـ Environment مع اللغة والمستودع ---
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))

            # تمرير الـ Context لضمان ترجمة النتائج وحساب الكميات صح
            Product = request.env['product.product'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            if final_warehouse_id:
                try:
                    final_warehouse_id = int(final_warehouse_id)
                except Exception:
                    return self._json({'error': 'Invalid warehouse_id'}, status=400)

            # --- 4. بناء الـ Domain والبحث ---
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

            # --- 5. الدوال الداخلية ---
            def _variant_ptav_lines(variant):
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
                kv = {}
                if 'attribute_line_ids' in tmpl._fields:
                    for al in tmpl.attribute_line_ids:
                        if len(al.value_ids) == 1:
                            attr = al.attribute_id
                            v = al.value_ids[0]
                            if attr and v:
                                kv[attr.name] = v.name
                return kv

            # --- 6. تجميع النتائج ---
            results = []
            for t in templates:
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)
                main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None

                is_combo = any(getattr(v, 'is_appointment_package', False) for v in t.product_variant_ids)
                detailed_type = 'combo' if is_combo else getattr(t, 'detailed_type', None)

                # 🚀 --- حساب متوسط التقييم الحقيقي ---
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id),
                    ('state', '!=', 'rejected')
                ])
                total_reviews = len(reviews)
                avg_rating = 0.0
                if total_reviews > 0:
                    total_score = sum(r.rating for r in reviews if 1 <= r.rating <= 5)
                    avg_rating = total_score / total_reviews

                # 🌟 --- فحص العروض والمكافآت (بدون دوال خارجية) ---
                raw_desc = t.description_sale or ""
                reward_desc = raw_desc.strip()
                has_reward = bool(reward_desc)

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
                        'qty': float(v.qty_available or 0.0),
                        'product_image_url': v_img,
                        'attributes_kv': kv,
                        'lines': ptav_lines,
                        'is_configurable': is_configurable,
                    })

                t_name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name

                # 🚀 التعديل هنا: تحديد القسم الصحيح (POS للخدمات، وعادي للمنتجات)
                if detailed_type == 'service':
                    category_name = t.pos_categ_ids[0].name if hasattr(t, 'pos_categ_ids') and t.pos_categ_ids else None
                else:
                    category_name = t.categ_id.display_name if t.categ_id else None

                results.append({
                    'template_id': t.id,
                    'name': t_name,
                    'detailed_type': detailed_type,

                    # === تم وضع القسم المظبوط والترجمة هتم أوتوماتيك من أودو ===
                    'category': category_name,

                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),

                    # إضافة التقييم والمكافآت هنا 👇
                    'avg_rating': round(avg_rating, 2),
                    'has_reward': has_reward,
                    'reward_description': reward_desc if has_reward else None,

                    'main_image_url': main_img_url,
                    'variants': variants_payload
                })

            # --- 7. الرد النهائي ---
            resp = {
                'query': query,
                'paging': {
                    'total': total_templates,
                    'count': len(results),
                    'limit': limit,
                    'offset': offset,
                },
                'results': results,
                'detected_lang': lang,
                'detected_warehouse': final_warehouse_id
            }
            return self._json(resp, status=200)

        except Exception as e:
            _logger.exception("products_search failed")
            return self._json(
                {'error': 'Internal server error', 'details': str(e)},
                status=500
            )

    @http.route(
        '/api/products/advanced_search',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def advanced_products_search(self, **kwargs):
        """
        البحث المتقدم مع دعم الموقع الجغرافي والترجمة من الـ Headers.
        يدعم الفلترة بالأسعار، التقييم، التصنيفات، والخصومات (Loyalty Rewards).
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            # توحيد اللغة (ar -> ar_001, en -> en_US)
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع بناءً على الموقع الجغرافي ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error in advanced search: {str(e)}")

            # --- 3. تجهيز الإعدادات والـ Context ---
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            q = kwargs.get('q')
            min_price = kwargs.get('min_price')
            max_price = kwargs.get('max_price')
            rating = kwargs.get('rating')
            category_id = kwargs.get('category_id')
            is_discount = str(kwargs.get('is_discount', '0')) in ('1', 'true', 'yes')

            # تمرير اللغة والمستودع في الـ Context لضمان ترجمة النصوص ودقة الأسعار والكميات
            Template = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            # --- 4. بناء الـ Domain ---
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

            if category_id:
                try:
                    ids = [int(x) for x in str(category_id).split(',')]
                    # 🚀 التعديل هنا: البحث بـ AND مع باقي الفلاتر، بس بيجيب المنتج لو تابع لقسم مخازن "أو" قسم نقطة بيع
                    domain += ['|', ('categ_id', 'in', ids), ('pos_categ_ids', 'in', ids)]
                except:
                    return self._json({'error': 'Invalid category_id format'}, status=400)

            if rating:
                domain.append(('avg_rating', '>=', int(rating)))

            # --- 5. البحث والمعالجة ---
            templates = Template.search(domain)

            # معالجة فلتر الخصم (لأن سعر بعد الخصم غالباً حقل محسوب Computed)
            if is_discount:
                templates = templates.filtered(
                    lambda t: t.price_after_discount and t.price_after_discount < t.list_price)

            total = len(templates)
            templates = templates[offset: offset + limit]

            # --- 🔥 6. جلب مكافآت الولاء (Loyalty Rewards) مرة واحدة بره الـ Loop للحفاظ على الأداء 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            template_rewards = {}
            category_rewards = {}
            global_reward_desc = ""

            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                # 1. المنتجات المحددة
                if rule.product_ids:
                    for tmpl_id in rule.product_ids.mapped('product_tmpl_id').ids:
                        template_rewards[tmpl_id] = desc

                # 2. الفئات المحددة
                if getattr(rule, 'product_category_id', False):
                    category_rewards[rule.product_category_id.id] = desc

                # 3. العروض العامة
                if not rule.product_ids and not getattr(rule, 'product_category_id', False):
                    domain_rule = getattr(rule, 'product_domain', '[]')
                    if domain_rule == '[]' or not domain_rule:
                        global_reward_desc = desc

            # --- 7. بناء الرد النهائي ---
            results = []
            for t in templates:
                # الـ Context بيخلي الأسماء والأسعار تطلع صح حسب لغة ومكان العميل
                name = self._pt_name(t, lang) if hasattr(self, '_pt_name') else t.name
                img = self._main_image_url(t) if hasattr(self, '_main_image_url') else None

                # 🎯 فحص استحقاق المكافأة للمنتج الحالي من نظام الولاء
                reward_desc = ""
                if t.id in template_rewards:
                    reward_desc = template_rewards[t.id]
                elif t.categ_id and t.categ_id.id in category_rewards:
                    reward_desc = category_rewards[t.categ_id.id]
                elif global_reward_desc:
                    reward_desc = global_reward_desc

                reward_desc = reward_desc.strip()
                has_reward = bool(reward_desc)

                if t.detailed_type == 'service':
                    category_name = t.pos_categ_ids[0].name if hasattr(t, 'pos_categ_ids') and t.pos_categ_ids else None
                else:
                    category_name = t.categ_id.display_name if t.categ_id else None

                results.append({
                    "id": t.id,
                    "name": name,
                    "price": float(t.list_price or 0.0),
                    "price_after_discount": float(t.price_after_discount or t.list_price or 0.0),

                    "category": category_name,

                    "detailed_type": t.detailed_type,
                    "rating": float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    "is_discount": bool(t.price_after_discount and t.price_after_discount < t.list_price),
                    "main_image_url": img,

                    "has_reward": has_reward,
                    "reward_description": reward_desc if has_reward else None
                })

            return self._json({
                "paging": {
                    "total": total,
                    "count": len(results),
                    "limit": limit,
                    "offset": offset,
                },
                "results": results,
                "detected_lang": raw_lang,
                "detected_warehouse": final_warehouse_id
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
        # إضافة الهيدرز الجديدة (lang, latitude, longitude) للقائمة المسموحة
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, lang, latitude, longitude'
        }
        return request.make_response(status=200, headers=headers)

    @http.route('/api/categories', type='http', auth='public', methods=['GET'], csrf=False)
    def categories_list(self, **kwargs):
        try:
            # === استخراج الـ Headers وتحديد اللغة ===
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)
            # ========================================================

            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))

            Cat = request.env['pos.category'].sudo().with_context(lang=lang)

            # 🚀 التعديل المطلوب: ضفنا شرط ('is_appointment_category', '=', True)
            domain = [('id', '!=', 1), ('name', 'not ilike', 'All'),('name', 'not ilike', 'Package'),('name', 'not ilike', 'بكج'), ('is_appointment_category', '=', True)]

            # التأكد من ترتيب الحقول الموجودة
            order_fields = [f for f in ['parent_left', 'name', 'id'] if f in Cat._fields]
            order = ', '.join(order_fields) or 'id'

            total = Cat.search_count(domain)
            cats = Cat.search(domain, limit=limit, offset=offset, order=order)

            base_url = request.httprequest.host_url.rstrip('/')
            data = []

            for c in cats:
                img_url = None
                # 🚀 التعديل هنا: غيرنا img لـ image_128 عشان تطابق اسم الحقل الحقيقي
                if getattr(c, "image_128", False):
                    img_url = f"{base_url}/api/public/image/pos.category/{c.id}/image_128"

                loc_name = c.ar_name if (raw_lang == 'ar' and getattr(c, 'ar_name', None)) else c.name
                loc_desc = getattr(c, 'ar_description', '') if (raw_lang == 'ar') else getattr(c, 'description', '')

                data.append({
                    "id": c.id,
                    "name": loc_name,
                    "description": loc_desc,
                    "parent_id": c.parent_id.id if c.parent_id else None,
                    "image_url": img_url,
                    "lang": raw_lang,
                })

            return self._json({
                "paging": {"total": total, "count": len(data), "limit": limit, "offset": offset},
                "categories": data,
                "detected_lang": raw_lang
            }, status=200)

        except Exception as e:
            _logger.exception("categories_list failed")
            return self._json({"error": str(e)}, status=500)
    def _image_url(self, model, rec_id, field, unique=None):
        """Return clean image URL without ?v= parameter."""
        base = request.httprequest.host_url.rstrip('/')
        return f"{base}/web/image/{model}/{rec_id}/{field}"

    @http.route('/api/categories/<int:category_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def category_get(self, category_id, **kwargs):
        """
        جلب تفاصيل تصنيف واحد مع دعم الترجمة التلقائية بناءً على الهيدرز.
        """
        try:
            # --- 1. استخراج اللغة وتوحيدها ---
            # بنقرأ الـ lang من الهيدر أو الـ URL لضمان المرونة للمبرمج
            header_lang = request.httprequest.headers.get('lang')
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()

            # تحويل الاختصارات (ar, en) لأكواد أودو (ar_001, en_US)
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. جلب البيانات باللغة المطلوبة ---
            # استخدام with_context يضمن أن حقل name سيرجع باللغة المحددة فوراً
            Cat = request.env['product.category'].sudo().with_context(lang=lang)
            c = Cat.browse(category_id)

            if not c.exists():
                return self._json({'error': 'Category not found', 'category_id': category_id}, status=404)

            # --- 3. معالجة رابط الصورة ---
            # استخدام unique لمنع الـ Caching في المتصفح عند تحديث الصورة
            dt = c.write_date or c.create_date
            unique = dt.strftime('%Y%m%d%H%M%S') if dt else None

            # التأكد من وجود الدالة _image_url في الكنترولر أو استخدام المسار الافتراضي
            img_url = None
            if hasattr(self, '_image_url') and c.img:
                img_url = self._image_url('product.category', c.id, 'img', unique=unique)
            elif c.img:
                # مسار بديل لو الدالة مش موجودة في الـ Self
                base_url = request.httprequest.host_url.rstrip('/')
                img_url = f"{base_url}/api/public/image/product.category/{c.id}/img?unique={unique}"

            # --- 4. الرد النهائي ---
            return self._json({
                'id': c.id,
                'name': c.name,  # هيرجع مترجم تلقائياً (عربي أو إنجليزي)
                'ar_name': getattr(c, 'ar_name', None),  # للحفاظ على التوافق مع الكود القديم
                'parent_id': c.parent_id.id if c.parent_id else None,
                'image_url': img_url,
                'detected_lang': raw_lang  # عشان مبرمج الموبايل يتأكد إن الهيدر وصل صح
            }, status=200)

        except Exception as e:
            _logger.exception("category_get failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route('/api/categories', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_categories(self, **kwargs):
        """
        Allow CORS and custom headers (lang, latitude, longitude)
        for categories API calls.
        """
        # إضافة الهيدرز الجديدة للقائمة المسموحة
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, lang, latitude, longitude'
        }
        # استخدام request.make_response لضمان التوافق مع أودو 17
        return request.make_response(status=200, headers=headers)

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
        try:
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])

                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp

                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error: {str(e)}")

            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            Tpl = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            tmpl = Tpl.browse(template_id)
            if not tmpl.exists():
                return self._json({'error': 'Product template not found', 'id': template_id}, status=404)

            # 🚀 حساب متوسط التقييم
            reviews = request.env['product.review'].sudo().search([
                ('product_id', '=', tmpl.id),
                ('state', '!=', 'rejected')
            ])
            total_reviews = len(reviews)
            avg_rating = 0.0
            if total_reviews > 0:
                total_score = sum(r.rating for r in reviews if 1 <= r.rating <= 5)
                avg_rating = total_score / total_reviews

            # --- 🔥 جلب المكافأة الحقيقية من نظام الولاء (Loyalty Rewards) 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            reward_desc = ""
            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                # جلب وصف الجائزة الفعلي
                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                applies = False
                # 1. هل العرض مخصص لمنتجات محددة؟
                if hasattr(rule, 'product_ids') and rule.product_ids:
                    if tmpl.id in rule.product_ids.mapped('product_tmpl_id').ids:
                        applies = True
                # 2. هل العرض مخصص لتصنيف محدد؟ (استخدام الاسم الصحيح product_category_id)
                elif hasattr(rule, 'product_category_id') and rule.product_category_id:
                    if tmpl.categ_id and tmpl.categ_id.id == rule.product_category_id.id:
                        applies = True
                # 3. هل العرض عام على كل المتجر؟
                else:
                    domain = getattr(rule, 'product_domain', '[]')
                    if domain == '[]' or not domain:
                        applies = True

                if applies:
                    reward_desc = desc
                    break

            has_reward = bool(reward_desc)

            # --- 4. معالجة البيانات ---
            total_qty = sum(float(v.qty_available or 0.0) for v in tmpl.product_variant_ids)
            main_img_url = self._main_image_url(tmpl)
            gallery = self._template_gallery(tmpl)

            variants_payload = []
            for v in tmpl.product_variant_ids:
                v = v.with_context(lang=lang)
                attrs = []
                if 'product_template_attribute_value_ids' in v._fields:
                    for ptav in v.product_template_attribute_value_ids:
                        attr = ptav.attribute_id if hasattr(ptav, 'attribute_id') else False
                        val = getattr(ptav, 'product_attribute_value_id', False)
                        attrs.append({
                            'ptav_id': ptav.id,
                            'attribute_id': attr.id if attr else None,
                            'attribute': attr.name if attr else None,
                            'value_id': val.id if val else None,
                            'value': val.name if val else getattr(ptav, 'name', None),
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
                'avg_rating': round(avg_rating, 2),
                'top': getattr(tmpl, 'top', None),
                'main_image_url': main_img_url,
                'gallery': gallery,

                # === الحقول الخاصة بالمكافآت من الموديول الفعلي 🎁 ===
                'has_reward': has_reward,
                'reward_description': reward_desc if has_reward else None,

                'variants': variants_payload,
                'detected_lang': raw_lang,
                'detected_warehouse': final_warehouse_id
            }

            return self._json(payload, status=200)

        except Exception as e:
            _logger.exception("product_template_get failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
    @http.route('/api/products/combos', type='http', auth='public', methods=['GET'], csrf=False)
    def products_combos(self, **kwargs):
        """
        List combo products with location-based warehouse detection,
        multi-language support from Headers, and Loyalty Rewards detection.
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            # توحيد اللغة (ar -> ar_001, en -> en_US)
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع بناءً على الموقع الجغرافي ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error in combos: {str(e)}")

            # المستودع النهائي (الأولوية للموقع الجغرافي)
            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز الإعدادات والـ Context ---
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            type_value = (kwargs.get('type_value') or 'combo').strip()

            # تمرير اللغة والمستودع في الـ Context
            Tpl = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            if 'detailed_type' not in Tpl._fields:
                return self._json({'error': "Field 'detailed_type' not found on product.template"}, status=400)

            # --- 4. بناء الـ Domain والبحث ---
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

            # --- 5. معالجة البيانات وبناء الـ Response ---
            data = []
            for t in templates:
                main_img_url = self._main_image_url(t)
                gallery = self._template_gallery(t)

                # الكمية محسوبة بناءً على المستودع الأقرب في الـ Context
                qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                # 🎯 فحص العروض والمكافآت (تم التوحيد مع باقي الـ Endpoints)
                raw_desc = t.description_sale or ""
                reward_description = raw_desc.strip()
                has_reward = bool(reward_description)

                combo_list = []
                if 'combo_ids' in t._fields:
                    for c in t.combo_ids:
                        c = c.with_context(lang=lang)
                        prod, tmpl = self._resolve_product_and_template(c)
                        used_lines_field, lines = self._pick_lines_field(c)

                        lines_payload = []
                        for ln in lines:
                            ln = ln.with_context(lang=lang)
                            ln_prod, ln_tmpl = self._resolve_product_and_template(ln)
                            if not tmpl and ln_tmpl:
                                tmpl = ln_tmpl

                            line_image_url = self._main_image_url(ln_prod) or self._main_image_url(ln_tmpl)
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

                # إضافة المنتج النهائي للقائمة شامل حقول المكافآت الجديدة
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
                    'avg_rating': getattr(t, 'avg_rating', 0.0),
                    'main_image_url': main_img_url,
                    'gallery': gallery,

                    # === الحقول الخاصة بالمكافآت 🎁 ===
                    'has_reward': has_reward,
                    'reward_description': reward_description if has_reward else None,

                    'combo_items': combo_list,
                })

            import math
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
                    'warehouse_id': final_warehouse_id,
                    'type_value': type_value,
                },
                'pagination': pagination,
                'products_count': len(data),
                'products': data,
                'detected_lang': raw_lang,
                'detected_warehouse': final_warehouse_id
            }, status=200)

        except Exception as e:
            _logger.exception("products_combos failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
    # @http.route(
    #     '/api/services/combos/appointment',
    #     type='http', auth='public', methods=['GET'], csrf=False
    # )
    # def appointment_services_combos(self, **kwargs):
    #     """
    #     List appointment services where product.product.detailed_type = 'service' and associated appointment package lines.

    #     Query params:
    #       - limit: int (default 50)
    #       - offset: int (default 0)
    #       - branch_id: int (optional)
    #       - department_id: int (optional)
    #       - lang: 'ar' or 'en' (default 'en')
    #     """
    #     try:
    #         lang = kwargs.get('lang', 'en').lower()
    #         limit = int(kwargs.get('limit', 50))
    #         offset = int(kwargs.get('offset', 0))
    #         branch_id = kwargs.get('branch_id')
    #         department_id = kwargs.get('department_id')

    #         Prod = request.env['product.product'].sudo()

    #         domain = [
    #             ('detailed_type', '=', 'service'),
    #             ('active', '=', True),
    #             ('sale_ok', '=', True),
    #         ]

    #         if branch_id:
    #             domain.append(('branch_id', '=', branch_id))
    #         if department_id:
    #             domain.append(('department_id', '=', department_id))

    #         products = Prod.search(domain, limit=limit, offset=offset, order='name asc')
    #         total = Prod.search_count(domain)

    #         data = []
    #         for p in products:

    #             appointment_lines = p.appointment_package_line_ids
    #             # appointment_lines = p.appointment_package_line_ids.filtered(
    #             #     lambda line: line.branch_id == branch_id and line.department_id == department_id)

    #             service_data = []
    #             for line in appointment_lines:
    #                 service_data.append({
    #                     'package_line_id': line.id,
    #                     'product_id': line.product_id.id,
    #                     'name': line.product_id.name,
    #                     'branch_id': line.branch_id.id,
    #                     'department_id': line.department_id.id,
    #                     'service_slot_inside': line.service_slot_inside,
    #                     'service_slot_outside': line.service_slot_outside,
    #                     'service_price_inside': line.service_price_inside,
    #                     'service_price_outside': line.service_price_outside,
    #                     'currency_id': line.currency_id.id,
    #                 })

    #             data.append({
    #                 'product_id': p.id,
    #                 'name': p.name,
    #                 'description': p.description,
    #                 'appointment_lines': service_data,
    #             })

    #         pagination = {
    #             'total': total,
    #             'limit': limit,
    #             'offset': offset,
    #             'current_page': (offset // limit) + 1 if limit else 1,
    #             'total_pages': math.ceil(total / limit) if limit else 1,
    #         }

    #         return self._json({
    #             'filters': {
    #                 'limit': limit,
    #                 'offset': offset,
    #                 'branch_id': branch_id,
    #                 'department_id': department_id,
    #             },
    #             'pagination': pagination,
    #             'services_count': len(data),
    #             'services': data,
    #         }, status=200)

    #     except Exception as e:
    #         _logger.exception("appointment_services_combos failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route(
        '/api/services/combos/appointment',
        type='http', auth='public', methods=['GET'], csrf=False
    )
    def appointment_services_combos(self, **kwargs):
        """
        List appointment services with auto-detection of nearest branch,
        automatic translation from Headers, and Real-time Average Ratings.
        Merged with all original keys (pricing, details, gallery, filters).
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, 'en_US')

            # --- 2. تحديد أقرب فرع/شركة بناءً على الموقع الجغرافي ---
            auto_warehouse_id = None
            detected_company = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])

                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            detected_company = comp

                    if detected_company:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', detected_company.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error in appointments: {str(e)}")

            # --- 3. تجهيز الإعدادات والـ Context ---
            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            branch_id = kwargs.get('branch_id') or (detected_company.id if detected_company else None)
            department_id = kwargs.get('department_id')

            ProdModel = request.env['product.product'].sudo()
            Prod = ProdModel.with_context(
                lang=lang,
                warehouse=auto_warehouse_id or kwargs.get('warehouse_id')
            )

            # --- 🔥 جلب برامج الولاء النشطة مسبقاً ---
            today = fields.Date.today()
            active_programs = request.env['loyalty.program'].sudo().search([
                ('active', '=', True),
                ('program_type', 'in', ('promotion', 'coupons', 'loyalty')),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ])

            domain = [
                ('detailed_type', '=', 'service'),
                ('active', '=', True),
                ('sale_ok', '=', True),
                ('is_appointment_package', '=', True),
            ]

            if branch_id and 'branch_id' in ProdModel._fields:
                try:
                    domain.append(('branch_id', '=', int(branch_id)))
                except (ValueError, TypeError):
                    pass

            if department_id and 'department_id' in ProdModel._fields:
                try:
                    domain.append(('department_id', '=', int(department_id)))
                except (ValueError, TypeError):
                    pass

            products = Prod.search(domain, limit=limit, offset=offset, order='name asc')
            total = Prod.search_count(domain)

            data = []
            for p in products:
                t = p.product_tmpl_id.with_context(lang=lang)

                # 🚀 حساب التقييم
                combo_reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id), ('state', '!=', 'rejected')
                ])
                combo_avg_rating = sum(r.rating for r in combo_reviews if 1 <= r.rating <= 5) / len(
                    combo_reviews) if combo_reviews else 0.0

                # 🔥 فحص المكافآت (Loyalty Logic)
                reward_desc = ""
                for program in active_programs:
                    for rule in program.rule_ids:
                        is_product_match = not rule.product_ids or t.id in rule.product_ids.mapped(
                            'product_tmpl_id').ids
                        is_category_match = True
                        if getattr(rule, 'product_category_id', False):
                            is_category_match = t.categ_id.id == rule.product_category_id.id

                        if is_product_match and is_category_match and program.reward_ids:
                            reward_desc = program.reward_ids[0].description or program.reward_ids[0].name
                            break
                    if reward_desc: break

                has_reward = bool(reward_desc)

                # إعداد الصور والمعرض (كانت مفقودة في الجديد)
                main_img_url = self._main_image_url(t)
                gallery = getattr(self, '_template_gallery', lambda x: [])(t)  # حماية في حال الدالة مش موجودة

                appointment_lines = getattr(p, 'appointment_package_line_ids', [])
                service_data = []

                for line in appointment_lines:
                    line_prod = line.product_id.with_context(lang=lang)
                    line_tmpl = line_prod.product_tmpl_id.with_context(lang=lang)

                    # تقييم الخدمة الفرعية
                    line_reviews = request.env['product.review'].sudo().search([
                        ('product_id', '=', line_tmpl.id), ('state', '!=', 'rejected')
                    ])
                    line_avg_rating = sum(r.rating for r in line_reviews if 1 <= r.rating <= 5) / len(
                        line_reviews) if line_reviews else 0.0

                    service_data.append({
                        'package_line_id': line.id,
                        'product_id': line_prod.id,
                        'name': self._pp_name(line_prod, lang),

                        # === الحقول اللي رجعناها للخدمة الفرعية زي القديم بالمللي ===
                        'branch_id': line.branch_id.id if getattr(line, 'branch_id', False) else None,
                        'department_id': line.department_id.id if getattr(line, 'department_id', False) else None,
                        'service_slot_inside': getattr(line, 'service_slot_inside', 0.0),
                        'service_slot_outside': getattr(line, 'service_slot_outside', 0.0),
                        'service_price_inside': getattr(line, 'service_price_inside', 0.0),
                        'service_price_outside': getattr(line, 'service_price_outside', 0.0),
                        'currency_id': line.currency_id.id if getattr(line, 'currency_id', False) else None,

                        'avg_rating': round(line_avg_rating, 2),
                        'image_url': self._main_image_url(line_prod) or self._main_image_url(line_tmpl),
                    })

                data.append({
                    'product_id': p.id,
                    'template_id': t.id,
                    'name': self._pp_name(p, lang),

                    # === الحقول اللي رجعناها للباقة الأساسية زي القديم بالمللي ===
                    'top': getattr(t, 'top', False),
                    'description': getattr(self, '_pt_desc', lambda x, y: None)(t, lang) or p.description,
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(t.list_price or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0)),
                    'currency': t.currency_id.name if t.currency_id else None,
                    'product_type': t.type,
                    'detailed_type': getattr(t, 'detailed_type', t.type),

                    'avg_rating': round(combo_avg_rating, 2),

                    # حقول المكافآت الجديدة
                    'has_reward': has_reward,
                    'reward_description': reward_desc if has_reward else None,

                    # الصور
                    'main_image_url': main_img_url,
                    'gallery': gallery,
                    'appointment_lines': service_data,
                })

            import math
            pagination = {
                'total': total,
                'limit': limit,
                'offset': offset,
                'current_page': (offset // limit) + 1 if limit else 1,
                'total_pages': math.ceil(total / limit) if limit else 1,
            }

            # === الرد النهائي بنفس هيكل القديم بالظبط ===
            return self._json({
                'filters': {
                    'limit': limit,
                    'offset': offset,
                    'branch_id': branch_id,
                    'department_id': department_id,
                    'detected_lang': raw_lang,
                    'detected_warehouse': auto_warehouse_id,
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


    # # kabir commented
    # @http.route(
    #     '/api/services',
    #     type='http',
    #     auth='public',
    #     methods=['GET'],
    #     csrf=False
    # )
    # def services_list(self, **kwargs):
    #     """
    #     List service product templates (detailed_type = 'service') with associated service package details from product.product.

    #     Query params:
    #       - limit: int (default 50)
    #       - offset: int (default 0)
    #       - q: str (optional; search)
    #       - category_id: int (optional; filter by category)
    #       - include_children: 1/0 (default 0)
    #       - warehouse_id: int (optional)
    #       - lang: 'ar' or 'en' (header or query)
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

    #         if order_raw.lower().startswith('localized_name'):
    #             direction = 'desc' if order_raw.lower().endswith('desc') else 'asc'
    #             order = ('ar_name ' if lang == 'ar' else 'name ') + direction
    #         else:
    #             order = order_raw

    #         Tpl = request.env['product.template'].sudo()
    #         if warehouse_id:
    #             try:
    #                 warehouse_id = int(warehouse_id)
    #                 Tpl = Tpl.with_context(warehouse=warehouse_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid warehouse_id'}, status=400)

    #         domain = [
    #             ('is_appointment_service', '=', True),
    #             ('detailed_type', '=', 'service'),
    #             ('sale_ok', '=', True),
    #             ('active', '=', True),
    #         ]

    #         if category_id:
    #             try:
    #                 category_id = int(category_id)
    #             except Exception:
    #                 return self._json({'error': 'Invalid category_id'}, status=400)
    #             domain.append(('categ_id', 'child_of' if include_children else '=', category_id))

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

    #         total = Tpl.search_count(domain)
    #         templates = Tpl.search(domain, limit=limit, offset=offset, order=order)

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

    #         data = []
    #         for t in templates:
    #             total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

    #             main_img_url = self._main_image_url(t) if hasattr(self, '_main_image_url') else None
    #             gallery = self._template_gallery(t) if hasattr(self, '_template_gallery') else []
    #             gallery_urls = [g.get('url') for g in (gallery or []) if g.get('url')]

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

    #             service_packages = []
    #             for v in t.product_variant_ids:
    #                 if 'appointment_package_line_ids' in v._fields:
    #                     for line in v.appointment_package_line_ids:
    #                         service_packages.append({
    #                             'package_line_id': line.id,
    #                             'product_id': line.product_id.id,
    #                             'service_slot_inside': line.service_slot_inside,
    #                             'service_slot_outside': line.service_slot_outside,
    #                             'service_price_inside': line.service_price_inside,
    #                             'service_price_outside': line.service_price_outside,
    #                             'currency_id': line.currency_id.id,
    #                         })

    #             localized_category_name = (
    #                 (t.categ_id.ar_name if getattr(t.categ_id, 'ar_name', None) else t.categ_id.name)
    #                 if t.categ_id and lang == 'ar' else (t.categ_id.name if t.categ_id else None)
    #             )

    #             data.append({
    #                 'id': t.id,
    #                 'model': 'product.template',

    #                 'name': self._pt_name(t, lang),
    #                 'description': self._pt_desc(t, lang),

    #                 'detailed_type': getattr(t, 'detailed_type', None),  # service
    #                 'category': localized_category_name,

    #                 'price': float(getattr(t, 'list_price', 0.0) or 0.0),
    #                 'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
    #                 'currency': t.currency_id.name if t.currency_id else None,

    #                 'qty': total_qty,
    #                 'uom': t.uom_id.name if t.uom_id else None,
    #                 'barcode': t.barcode,

    #                 'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
    #                 'top': bool(getattr(t, 'top', False)),

    #                 'main_image_url': main_img_url,
    #                 'gallery_urls': gallery_urls,

    #                 'variants': variants_payload,
    #                 'service_packages': service_packages,  # Added service packages from product.product
    #             })

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

    #     except Exception as e:
    #         _logger.exception("services_list failed")
    #         return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)
    
    # @http.route('/api/services', type='http', auth='public', methods=['GET'], csrf=False)
    # def services_list(self, **kwargs):
    #     try:
    #         # 1. Parse Parameters
    #         lang = (kwargs.get('lang') or 'en').lower()
    #         limit = int(kwargs.get('limit', 10))
    #         offset = int(kwargs.get('offset', 0))
    #         category_id = kwargs.get('category_id')
    #         include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
    #         q = (kwargs.get('q') or '').strip()
    #
    #         Tpl = request.env['product.template'].sudo()
    #         Categ = request.env['product.category'].sudo()
    #
    #         # 2. Build Domain
    #         domain = [
    #             ('detailed_type', '=', 'service'),
    #             ('sale_ok', '=', True),
    #             ('active', '=', True)
    #         ]
    #
    #         if category_id:
    #             try:
    #                 category_id = int(category_id)
    #                 operator = 'child_of' if include_children else '='
    #                 domain.append(('categ_id', operator, category_id))
    #             except ValueError:
    #                 return self._json({'error': 'Invalid category_id format'}, status=400)
    #
    #         # Search Logic (Reference from your code)
    #         if q:
    #             domain += ['|', '|', ('name', 'ilike', q), ('barcode', 'ilike', q), ('default_code', 'ilike', q)]
    #
    #         # 3. Fetch Data
    #         templates = Tpl.search(domain, limit=limit, offset=offset, order='name asc')
    #         total = Tpl.search_count(domain)
    #
    #         # 4. Fetch Available Categories (Optional: for the UI filter bar)
    #         all_service_categories = Tpl.search([
    #             ('detailed_type', '=', 'service'),
    #             ('sale_ok', '=', True)
    #         ]).mapped('categ_id')
    #
    #         # Use a set to get unique categories from the products found
    #         # Note: if you use 'public_categ_ids', iterate through them
    #         category_data = [{
    #             'id': c.id,
    #             'name': (getattr(c, 'ar_name', c.name) or c.name).strip() if lang == 'ar' else c.name.strip(),
    #             'parent_id': c.parent_id.id if c.parent_id else None
    #         } for c in all_service_categories]
    #
    #         # 5. Prepare Payload
    #         # Mapping templates using your helper or manual dict
    #         data = [self._prepare_service_payload(t, lang) for t in templates]
    #
    #         return self._json({
    #             'paging': {
    #                 'total': total,
    #                 'count': len(data),
    #                 'limit': limit,
    #                 'offset': offset
    #             },
    #             'filters': {
    #                 'applied_category_id': category_id,
    #                 'search_query': q
    #             },
    #             #'categories': category_data, # List of categories for the frontend to display
    #             'services': data
    #         }, status=200)
    #
    #     except Exception as e:
    #         _logger.exception("services_list failed")
    #         return self._json({'error': str(e)}, status=500)

    @http.route('/api/services', type='http', auth='public', methods=['GET'], csrf=False)
    def services_list(self, **kwargs):
        try:
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location error in services: {str(e)}")

            limit = int(kwargs.get('limit', 10))
            offset = int(kwargs.get('offset', 0))
            category_id = kwargs.get('category_id')
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            q = (kwargs.get('q') or '').strip()

            Tpl = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=auto_warehouse_id or kwargs.get('warehouse_id')
            )

            # 🚀 التعديل هنا: الفلتر الذكي لاستبعاد خدمات السيستم والشحن
            domain = [
                ('detailed_type', '=', 'service'),
                ('sale_ok', '=', True),
                ('active', '=', True),

                # 1. فلتر السعر والصورة: يتجاهل أي خدمة مخفية سعرها صفر وملهاش صورة (زي poscommission)
                '|',
                ('list_price', '>', 0),
                ('image_1920', '!=', False),

                # 2. فلتر الشحن والتوصيل: استبعاد الكلمات دي من اسم الخدمة
                ('name', 'not ilike', 'شحن'),
                ('name', 'not ilike', 'توصيل'),
                ('name', 'not ilike', 'delivery'),
                ('name', 'not ilike', 'shipping'),
            ]

            if category_id:
                try:
                    category_id = int(category_id)
                    operator = 'child_of' if include_children else '='
                    # البحث في حقل أقسام نقطة البيع (pos_categ_ids)
                    domain.append(('pos_categ_ids', operator, category_id))
                except ValueError:
                    return self._json({'error': 'Invalid category_id format'}, status=400)

            if q:
                domain += [
                    '|', '|', '|',
                    ('name', 'ilike', q),
                    ('ar_name', 'ilike', q),
                    ('barcode', 'ilike', q),
                    ('default_code', 'ilike', q),
                ]

            templates = Tpl.search(domain, order='name asc')
            templates = templates.filtered(
                lambda t: not any(getattr(v, 'is_appointment_package', False) for v in t.product_variant_ids)
            )

            total = len(templates)
            templates = templates[offset: offset + limit]

            # --- 🔥 جلب مكافآت الولاء الحقيقية من الداتابيز بره الـ Loop 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            template_rewards = {}
            category_rewards = {}
            global_reward_desc = ""

            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                if hasattr(rule, 'product_ids') and rule.product_ids:
                    for tmpl_id in rule.product_ids.mapped('product_tmpl_id').ids:
                        template_rewards[tmpl_id] = desc
                # تم تصحيح الحقل لـ product_category_id
                if hasattr(rule, 'product_category_id') and rule.product_category_id:
                    category_rewards[rule.product_category_id.id] = desc

                if not getattr(rule, 'product_ids', False) and not getattr(rule, 'product_category_id', False):
                    domain_str = getattr(rule, 'product_domain', '[]')
                    if domain_str == '[]' or not domain_str:
                        global_reward_desc = desc

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url').strip('/')
            data = []

            for t in templates:
                service_data = self._prepare_service_payload(t, lang)

                # 🎯 تطبيق المكافأة على الخدمة من الـ Dictionaries
                reward_description = ""
                if t.id in template_rewards:
                    reward_description = template_rewards[t.id]
                elif t.categ_id and t.categ_id.id in category_rewards:
                    reward_description = category_rewards[t.categ_id.id]
                elif global_reward_desc:
                    reward_description = global_reward_desc

                service_data['has_reward'] = bool(reward_description)
                service_data['reward_description'] = reward_description if reward_description else None

                # إحصائيات التقييمات
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id),
                    ('state', '!=', 'rejected')
                ], order='create_date desc')

                total_reviews = len(reviews)
                avg_rating = 0.0
                rating_percentages = {'5_star': 0.0, '4_star': 0.0, '3_star': 0.0, '2_star': 0.0, '1_star': 0.0}
                recent_reviews_list = []

                if total_reviews > 0:
                    total_score = 0
                    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

                    for r in reviews:
                        if 1 <= r.rating <= 5:
                            counts[r.rating] += 1
                            total_score += r.rating

                        avatar_url = f"{base_url}/web/image/res.partner/{r.partner_id.id}/avatar_128" if r.partner_id.image_128 else ""
                        recent_reviews_list.append({
                            'review_id': r.id,
                            'reviewer_name': r.partner_id.name,
                            'reviewer_image': avatar_url,
                            'comment': r.comment if r.state == 'approved' else "",
                            'date': r.create_date.strftime('%Y-%m-%d %H:%M:%S') if r.create_date else "",
                            'status': r.state
                        })

                    avg_rating = total_score / total_reviews
                    rating_percentages = {
                        '5_star': round((counts[5] / total_reviews) * 100, 1),
                        '4_star': round((counts[4] / total_reviews) * 100, 1),
                        '3_star': round((counts[3] / total_reviews) * 100, 1),
                        '2_star': round((counts[2] / total_reviews) * 100, 1),
                        '1_star': round((counts[1] / total_reviews) * 100, 1),
                    }

                service_data['review_statistics'] = {
                    'total_reviews': total_reviews,
                    'average_rating': round(avg_rating, 2),
                    'percentages': rating_percentages
                }
                service_data['recent_reviews'] = recent_reviews_list[:5]

                data.append(service_data)

            return self._json({
                'paging': {
                    'total': total,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                },
                'filters': {
                    'applied_category_id': category_id,
                    'search_query': q,
                    'detected_lang': raw_lang,
                    'detected_warehouse': auto_warehouse_id or kwargs.get('warehouse_id'),
                },
                'services': data,
            }, status=200)

        except Exception as e:
            _logger.exception("services_list failed")
            return self._json({'error': str(e)}, status=500)

    @http.route('/api/services/top', type='http', auth='public', methods=['GET'], csrf=False)
    def services_top(self, **kwargs):
        """
        عرض الخدمات الأعلى تقييماً (النسخة المُحسنة المعتمدة على قاعدة البيانات)
        """
        try:
            # --- 1. استخراج الإضافات من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع (GPS) ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0), ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location error: {str(e)}")

            # --- 3. تجهيز الإعدادات والـ Context ---
            limit = int(kwargs.get('limit', 10))
            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            TplModel = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            # 🔥 الفلترة هنا بقت بتشترط إن التقييم يكون أكبر من صفر 🔥
            domain = [
                ('detailed_type', '=', 'service'),
                ('sale_ok', '=', True),
                ('active', '=', True),
                ('avg_rating', '>', 0.0)
            ]

            # 🔥 بنزود الـ Limit شوية في الداتابيز احتياطي عشان لو طردنا حاجة في بايثون 🔥
            templates = TplModel.search(domain, order='avg_rating desc', limit=limit + 5)

            # 🚀 التعديل الجذري: طرد الجيفت كارد بأي مسمى (مفرد، جمع، عربي، إنجليزي)
            forbidden_words = ['gift', 'هدية', 'هدايا']
            templates = templates.filtered(
                lambda t: t.name and not any(bad_word in t.name.lower() for bad_word in forbidden_words)
            )[:limit]

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url').strip('/')
            data = []

            # --- 4. تحضير البيانات لأفضل الخدمات فقط ---
            for t in templates:
                reviews = request.env['product.review'].sudo().search([
                    ('product_id', '=', t.id),
                    ('state', '!=', 'rejected')
                ], order='create_date desc')

                total_reviews = len(reviews)
                rating_percentages = {'5_star': 0.0, '4_star': 0.0, '3_star': 0.0, '2_star': 0.0, '1_star': 0.0}
                recent_reviews_list = []

                if total_reviews > 0:
                    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

                    for r in reviews:
                        if 1 <= r.rating <= 5:
                            counts[r.rating] += 1

                        avatar_url = f"{base_url}/web/image/res.partner/{r.partner_id.id}/avatar_128" if r.partner_id.image_128 else ""
                        recent_reviews_list.append({
                            'review_id': r.id,
                            'reviewer_name': r.partner_id.name,
                            'reviewer_image': avatar_url,
                            'rating': r.rating,
                            'comment': r.comment if r.state == 'approved' else "",
                            'date': r.create_date.strftime('%Y-%m-%d %H:%M:%S') if r.create_date else "",
                            'status': r.state
                        })

                    rating_percentages = {
                        '5_star': round((counts[5] / total_reviews) * 100, 1),
                        '4_star': round((counts[4] / total_reviews) * 100, 1),
                        '3_star': round((counts[3] / total_reviews) * 100, 1),
                        '2_star': round((counts[2] / total_reviews) * 100, 1),
                        '1_star': round((counts[1] / total_reviews) * 100, 1),
                    }

                payload = self._prepare_service_payload(t, lang)

                # جلب القسم من POS للخدمات وترجمته حسب الهيدر
                cat_obj = t.pos_categ_ids[0] if hasattr(t, 'pos_categ_ids') and t.pos_categ_ids else None
                if cat_obj:
                    payload['category'] = cat_obj.ar_name if (
                            raw_lang == 'ar' and getattr(cat_obj, 'ar_name', None)) else cat_obj.name
                else:
                    payload['category'] = None

                raw_desc = t.description_sale or ""
                reward_desc = raw_desc.strip()
                has_reward = bool(reward_desc)

                # بنقرا التقييم الجاهز من الموديل مباشرة
                payload['avg_rating'] = round(t.avg_rating, 2)
                payload['has_reward'] = has_reward
                payload['reward_description'] = reward_desc if has_reward else None

                payload['review_statistics'] = {
                    'total_reviews': total_reviews,
                    'average_rating': round(t.avg_rating, 2),
                    'percentages': rating_percentages
                }
                payload['recent_reviews'] = recent_reviews_list[:5]

                data.append(payload)

            return self._json({
                'count': len(data),
                'services': data,
                'detected_lang': raw_lang,
                'detected_warehouse': final_warehouse_id
            }, status=200)

        except Exception as e:
            _logger.exception("services_top failed")
            return self._json({'error': str(e)}, status=500)
    @http.route('/api/storable_products', type='http', auth='public', methods=['GET'], csrf=False)
    def storable_products_list(self, **kwargs):
        """
        قائمة المنتجات المخزنية:
        - دعم كشف المستودع جغرافياً.
        - توحيد حقول العروض والمكافآت لتصبح (has_reward & reward_description) فقط.
        """
        try:
            # --- 1. استخراج الإضافات واللغة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد المستودع الأقرب جغرافياً ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location error: {str(e)}")

            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز الـ Context ---
            ctx = {'lang': lang, 'force_company': request.env.company.id}
            if final_warehouse_id:
                try:
                    f_wh_id = int(final_warehouse_id)
                    ctx.update({'warehouse': f_wh_id, 'warehouse_id': f_wh_id})
                except:
                    pass
            else:
                internal_locs = request.env['stock.location'].sudo().search([('usage', '=', 'internal')])
                ctx.update({'location': internal_locs.ids})

            limit = int(kwargs.get('limit', 50))
            offset = int(kwargs.get('offset', 0))
            include_children = str(kwargs.get('include_children', '0')).lower() in ('1', 'true', 'yes')
            category_id = kwargs.get('category_id')
            q = (kwargs.get('q') or '').strip()
            order = 'avg_rating desc NULLS LAST, name asc'
            in_stock = str(kwargs.get('in_stock', '0')).lower() in ('1', 'true', 'yes')

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            TplModel = request.env['product.template'].sudo().with_context(**ctx)

            # --- 4. بناء الـ Domain وجلب برامج الولاء النشطة ---
            # 🚀 التعديل المطلوب: استبعاد قاطع وصريح لأي منتج نوعه "خدمة" (Service)
            domain = [
                ('detailed_type', '=', 'product'),
                ('detailed_type', '!=', 'service'),
                ('type', '!=', 'service'),
                ('sale_ok', '=', True),
                ('active', '=', True)
            ]

            today = fields.Date.today()
            active_programs = request.env['loyalty.program'].sudo().search([
                ('active', '=', True),
                ('program_type', 'in', ('promotion', 'coupons', 'loyalty')),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ])

            if category_id:
                try:
                    category_id = int(category_id)
                    domain.append(('categ_id', 'child_of' if include_children else '=', category_id))
                except:
                    pass

            if q:
                domain += ['|', '|', '|', ('name', 'ilike', q),
                           ('ar_name', 'ilike', q) if 'ar_name' in TplModel._fields else ('name', 'ilike', q),
                           ('barcode', 'ilike', q), ('default_code', 'ilike', q)]

            total = TplModel.search_count(domain)
            templates = TplModel.search(domain, limit=limit, offset=offset, order=order)

            # --- 🔥 جلب مكافآت الولاء بالأسماء الصحيحة (product_category_id) 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            template_rewards = {}
            category_rewards = {}
            global_reward_desc = ""

            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                # 1. المنتجات المحددة
                if rule.product_ids:
                    for tmpl_id in rule.product_ids.mapped('product_tmpl_id').ids:
                        template_rewards[tmpl_id] = desc

                # 2. الفئات المحددة
                if getattr(rule, 'product_category_id', False):
                    category_rewards[rule.product_category_id.id] = desc

                # 3. العروض العامة
                if not rule.product_ids and not getattr(rule, 'product_category_id', False):
                    domain_rule = getattr(rule, 'product_domain', '[]')
                    if domain_rule == '[]' or not domain_rule:
                        global_reward_desc = desc

            # --- 5. معالجة بيانات المنتجات ---
            data = []
            for t in templates:
                variants = t.product_variant_ids.with_context(**ctx)
                total_qty = sum(float(v.qty_available or 0.0) for v in variants)

                if in_stock and total_qty <= 0:
                    continue

                # 🔍 فحص العروض العامة للمنتج
                offer_details = ""
                for program in active_programs:
                    for rule in program.rule_ids:
                        is_product_match = not rule.product_ids or t.id in rule.product_ids.mapped(
                            'product_tmpl_id').ids
                        is_category_match = True
                        if getattr(rule, 'product_category_id', False):
                            is_category_match = t.categ_id.id == rule.product_category_id.id

                        if is_product_match and is_category_match:
                            offer_details = program.name
                            break
                    if offer_details: break

                # 🎯 فحص استحقاق المكافأة (Rewards)
                reward_desc = ""
                if t.id in template_rewards:
                    reward_desc = template_rewards[t.id]
                elif t.categ_id and t.categ_id.id in category_rewards:
                    reward_desc = category_rewards[t.categ_id.id]
                elif global_reward_desc:
                    reward_desc = global_reward_desc

                # 🚀 توحيد الوصف (لو فيه مكافأة هياخدها، ولو مفيش هياخد اسم العرض، ولو مفيش خالص هيفضل فاضي)
                final_reward_description = reward_desc or offer_details
                final_has_reward = bool(final_reward_description)

                gallery_urls = []
                if hasattr(t, 'product_template_image_ids'):
                    for img_line in t.product_template_image_ids:
                        gallery_urls.append(f"{base_url}/api/image/product.image/{img_line.id}/image_1920")

                variants_payload = []
                for v in variants:
                    v_discount = getattr(v, 'price_after_discount', 0.0)
                    if not v_discount or v_discount <= 0:
                        v_discount = getattr(t, 'price_after_discount', 0.0)

                    variants_payload.append({
                        'id': v.id,
                        'name': v.display_name,
                        'qty': float(v.qty_available or 0.0),
                        'price': float(t.list_price),
                        'price_after_discount': float(v_discount or 0.0),
                        'attributes': [
                            {'attribute': ptav.attribute_id.name, 'value': ptav.product_attribute_value_id.name}
                            for ptav in getattr(v, 'product_template_attribute_value_ids', [])
                        ],
                        'barcode': v.barcode,
                    })

                data.append({
                    'id': t.id,
                    'name': t.name,
                    'qty': total_qty,
                    'price': float(t.list_price),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),

                    # === تم التوحيد هنا فقط 🎁 ===
                    'has_reward': final_has_reward,
                    'reward_description': final_reward_description if final_has_reward else None,

                    'category': t.categ_id.display_name if t.categ_id else None,
                    'main_image_url': self._main_image_url(t) if hasattr(self, '_main_image_url') else None,
                    'gallery_urls': gallery_urls,
                    'variants': variants_payload,
                })

            return self._json({
                'filters': {
                    'warehouse_id': final_warehouse_id,
                    'detected_warehouse': auto_warehouse_id,
                    'lang': raw_lang
                },
                'paging': {'total': total, 'limit': limit, 'offset': offset},
                'products': data,
                'status': 'success'
            }, status=200)

        except Exception as e:
            _logger.exception("storable_products_list failed")
            return self._json({'error': str(e)}, status=500)

    @http.route('/api/services/similar', type='json', auth='public', methods=['POST'], csrf=False)
    def similar_services(self, **kwargs):
        """
        جلب البكجات المخصصة بناءً على مطابقة الاسم.
        تم توحيد مسار الصور مع باقي الـ APIs ليعتمد على ir.config_parameter.
        توحيد حقول المكافآت (has_reward & reward_description) لتقرأ من موديول الولاء وترجع null لو فارغة.
        """
        try:
            body = request.dispatcher.jsonrequest
            service_id = body.get('service_id')

            if not service_id:
                return {'status': 'error', 'message': 'Missing service_id in body'}

            # 1. إعدادات اللغة والروابط
            header_lang = request.httprequest.headers.get('lang', 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(header_lang, 'en_US')

            # 🚀 التعديل هنا: جلب الـ base_url بنفس طريقة storable_products_list
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # 2. تحديد المنتج والاسم بناءً على الـ ID المبعوث
            product_tmpl = request.env['product.template'].sudo().browse(int(service_id))
            if not product_tmpl.exists():
                product_variant = request.env['product.product'].sudo().browse(int(service_id))
                if product_variant.exists():
                    product_tmpl = product_variant.product_tmpl_id

            if not product_tmpl.exists():
                return {'status': 'error', 'message': 'Service not found'}

            target_name = product_tmpl.name

            # --- 🔥 جلب المكافأة/الخصم الحقيقي من نظام الولاء 🔥 ---
            active_rules = request.env['loyalty.rule'].sudo().with_context(lang=lang).search([
                ('program_id.active', '=', True)
            ])

            reward_desc = ""
            for rule in active_rules:
                program = rule.program_id
                if not program.reward_ids:
                    continue

                # جلب وصف الجائزة الفعلي
                desc = getattr(program.reward_ids[0], 'description', '') or program.reward_ids[0].name

                applies = False
                # 1. هل العرض مخصص لمنتجات محددة؟
                if hasattr(rule, 'product_ids') and rule.product_ids:
                    if product_tmpl.id in rule.product_ids.mapped('product_tmpl_id').ids:
                        applies = True
                # 2. هل العرض مخصص لتصنيف محدد؟ (استخدام product_category_id)
                elif getattr(rule, 'product_category_id', False):
                    if product_tmpl.categ_id and product_tmpl.categ_id.id == rule.product_category_id.id:
                        applies = True
                # 3. هل العرض عام على كل المتجر؟
                elif not rule.product_ids and not getattr(rule, 'product_category_id', False):
                    domain_rule = getattr(rule, 'product_domain', '[]')
                    if domain_rule == '[]' or not domain_rule:
                        applies = True

                if applies:
                    reward_desc = desc
                    break

            reward_desc = reward_desc.strip()
            has_reward = bool(reward_desc)

            # 3. البحث عن كل الـ Variants (الخدمات) اللي ليها نفس الاسم
            all_matching_variants = request.env['product.product'].sudo().search([('name', '=', target_name)])

            # 4. البحث في جدول أسطر البكجات (appointment.package.line)
            package_lines = request.env['appointment.package.line'].sudo().search([
                ('product_id', 'in', all_matching_variants.ids)
            ])

            # جلب البكجات الفريدة المرتبطة
            parent_packages = package_lines.sudo().mapped('product_pack_id').with_context(lang=lang)

            if not parent_packages:
                return {
                    'status': 'success',
                    'data': {'packages': []},
                    'has_reward': has_reward,
                    'reward_description': reward_desc if has_reward else None
                }

            package_payload = []
            for pkg in parent_packages:
                all_lines = request.env['appointment.package.line'].sudo().search([('product_pack_id', '=', pkg.id)])
                items = []
                for line in all_lines:
                    p_v = line.product_id.with_context(lang=lang)

                    # 🚀 التعديل هنا: استخدام /api/public/image بدلاً من /web/image
                    item_img_url = None
                    if p_v.image_1920:
                        item_img_url = f"{base_url}/api/public/image/product.product/{p_v.id}/image_1920"
                    elif p_v.product_tmpl_id.image_1920:
                        item_img_url = f"{base_url}/api/public/image/product.template/{p_v.product_tmpl_id.id}/image_1920"

                    items.append({
                        'service_id': p_v.id,
                        'name': p_v.name,
                        'price_inside': float(line.service_price_inside or 0.0),
                        'price_outside': float(line.service_price_outside or 0.0),
                        'slot_inside': line.service_slot_inside,
                        'slot_outside': line.service_slot_outside,
                        'image_url': item_img_url
                    })

                # 🚀 التعديل هنا: استخدام /api/public/image بدلاً من /web/image
                main_img_url = None
                if pkg.product_tmpl_id.image_1920:
                    main_img_url = f"{base_url}/api/public/image/product.template/{pkg.product_tmpl_id.id}/image_1920"

                package_payload.append({
                    'package_variant_id': pkg.id,
                    'name': pkg.with_context(lang=lang).display_name,
                    'total_price': float(pkg.list_price or 0.0),
                    'items': items,
                    'main_image_url': main_img_url
                })

            return {
                'status': 'success',
                'data': {
                    'queried_id': service_id,
                    'matched_name': target_name,
                    'packages': package_payload
                },
                'has_reward': has_reward,
                'reward_description': reward_desc if has_reward else None
            }

        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    @http.route(
        '/api/products/similar_by_tags',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def similar_products_by_tags(self, **kwargs):
        """
        جلب المنتجات المتشابهة بناءً على الوسوم (Tags) مع دعم الموقع واللغة.
        """
        try:
            # --- 1. استخراج الإضافات الجديدة من الـ Headers ---
            header_lang = request.httprequest.headers.get('lang')
            header_lat = request.httprequest.headers.get('latitude')
            header_lng = request.httprequest.headers.get('longitude')
            product_id = request.httprequest.headers.get('Product-Id') or request.httprequest.headers.get('product-id')

            if not product_id:
                return self._json({'error': 'Missing Product-Id header'}, status=400)

            try:
                product_id = int(product_id)
            except Exception:
                return self._json({'error': 'Invalid Product-Id'}, status=400)

            # توحيد اللغة (ar -> ar_001, en -> en_US)
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- 2. تحديد أقرب مستودع ---
            auto_warehouse_id = None
            if header_lat and header_lng:
                try:
                    u_lat, u_lng = float(header_lat), float(header_lng)
                    companies = request.env['res.company'].sudo().search([
                        ('partner_latitude', '!=', 0),
                        ('partner_longitude', '!=', 0)
                    ])
                    nearest_comp = None
                    min_dist = float('inf')
                    for comp in companies:
                        dist = self._get_distance(u_lat, u_lng, comp.partner_latitude, comp.partner_longitude)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_comp = comp
                    if nearest_comp:
                        wh = request.env['stock.warehouse'].sudo().search([('company_id', '=', nearest_comp.id)],
                                                                          limit=1)
                        auto_warehouse_id = wh.id if wh else None
                except Exception as e:
                    _logger.error(f"Geo-location calculation error: {str(e)}")

            final_warehouse_id = auto_warehouse_id or kwargs.get('warehouse_id')

            # --- 3. تجهيز البيئة ---
            Tpl = request.env['product.template'].sudo().with_context(
                lang=lang,
                warehouse=final_warehouse_id
            )

            target = Tpl.browse(product_id)
            if not target.exists():
                return self._json({'error': 'Product not found'}, status=404)

            # 🔥 استخراج وتجهيز المكافأة للمنتج الأساسي (توحيد اللوجيك)
            raw_target_reward = target.description_sale or ""
            target_reward_desc = raw_target_reward.strip()
            target_has_reward = bool(target_reward_desc)

            # استخراج الـ Tags
            tag_ids = target.product_tag_ids.ids
            if not tag_ids:
                return self._json({
                    'message': 'Product has no tags, cannot find similar products',
                    'similar_products': [],
                    'has_reward': target_has_reward,
                    'reward_description': target_reward_desc if target_has_reward else None
                }, status=200)

            # --- 4. البحث عن المتشابهات ---
            Similar = Tpl.search([
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

            # --- 5. تحضير البيانات النهائية ---
            data = []
            for t in similar_products:
                t = t.with_context(lang=lang, warehouse=final_warehouse_id)
                total_qty = sum(float(v.qty_available or 0.0) for v in t.product_variant_ids)

                # 🔥 استخراج المكافأة للمنتج المشابه (توحيد اللوجيك)
                raw_t_reward = t.description_sale or ""
                t_reward_desc = raw_t_reward.strip()
                t_has_reward = bool(t_reward_desc)

                gallery_urls = []
                if hasattr(self, '_template_gallery'):
                    gallery = self._template_gallery(t) or []
                    gallery_urls = [g.get('url') for g in gallery if g.get('url')]

                data.append({
                    'id': t.id,
                    'name': self._pt_name(t, lang),
                    'description': self._pt_desc(t, lang),
                    'category': t.categ_id.display_name if t.categ_id else None,
                    'price': float(getattr(t, 'list_price', 0.0) or 0.0),
                    'price_after_discount': float(getattr(t, 'price_after_discount', 0.0) or 0.0),
                    'qty': total_qty,
                    'avg_rating': float(getattr(t, 'avg_rating', 0.0) or 0.0),
                    'main_image_url': self._main_image_url(t) if hasattr(self, '_main_image_url') else None,
                    'gallery_urls': gallery_urls,

                    # === تم التوحيد هنا ===
                    'has_reward': t_has_reward,
                    'reward_description': t_reward_desc if t_has_reward else None
                })

            return self._json({
                'product_id': target.id,
                'product_name': self._pt_name(target, lang),
                'count': len(data),
                'similar_products': data,
                'has_reward': target_has_reward,
                'reward_description': target_reward_desc if target_has_reward else None,
                'detected_lang': raw_lang,
                'detected_warehouse': final_warehouse_id
            }, status=200)

        except Exception as e:
            _logger.exception("similar_products_by_tags failed")
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)


    ##git all varrint

    @http.route('/api/product/get_variants', type='http', auth='public', methods=['POST'], csrf=False)
    def api_get_product_variants(self, **kwargs):
        """
        استلام template_id من الـ Body وإرجاع كافة الـ Variants المرتبطة.
        Body JSON: {"template_id": 123}
        """
        try:
            # 1. قراءة البيانات من الـ Body
            raw_data = request.httprequest.data or b"{}"
            body = json.loads(raw_data.decode("utf-8"))
            template_id = body.get('template_id')

            if not template_id:
                return self._json({'error': 'template_id is required in body'}, status=400)

            # 2. البحث عن القالب في أودو 17
            Template = request.env['product.template'].sudo().browse(int(template_id))
            if not Template.exists():
                return self._json({'error': 'Product template not found'}, status=404)

            # 3. تجميع بيانات الـ Variants
            variants_list = []
            for variant in Template.product_variant_ids:

                # جلب الخصائص المحددة لكل Variant (مثل اللون والمقاس)
                attribute_values = []
                for ptav in variant.product_template_attribute_value_ids:
                    attribute_values.append({
                        'attribute_id': ptav.attribute_id.id,
                        'attribute_name': ptav.attribute_id.name,
                        'value_id': ptav.product_attribute_value_id.id,
                        'value_name': ptav.name
                    })

                # إضافة بيانات الـ Variant للقائمة
                variants_list.append({
                    'product_id': variant.id,  # الـ ID الحقيقي اللي هيتحط في الكارت
                    'template_id': Template.id,
                    'display_name': variant.display_name,
                    'price': float(variant.lst_price or Template.list_price),
                    'price_after_discount': float(
                        getattr(variant, 'price_after_discount', 0.0) or getattr(Template, 'price_after_discount',
                                                                                 0.0)),
                    'qty_available': float(variant.qty_available),
                    'barcode': variant.barcode,
                    'image_url': self._main_image_url(variant) if variant.image_1920 else self._main_image_url(
                        Template),
                    'attributes': attribute_values
                })

            # 4. الرد النهائي
            return self._json({
                'status': 'success',
                'template_name': Template.name,
                'variants_count': len(variants_list),
                'variants': variants_list
            }, status=200)

        except Exception as e:
            _logger.error("Error in api_get_product_variants: %s", str(e))
            return self._json({'error': 'Internal server error', 'details': str(e)}, status=500)

    @http.route('/api/product_categories', type='http', auth='public', methods=['GET'], csrf=False)
    def product_categories_list(self, **kwargs):
        try:
            import logging
            _logger = logging.getLogger(__name__)

            # === استخراج الـ Headers وتحديد اللغة بمرونة ===
            # قراءة الهيدر مع مراعاة أن بعض التطبيقات ترسله بحرف كبير
            header_lang = request.httprequest.headers.get('lang') or request.httprequest.headers.get('Lang')

            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, 'en_US')  # الافتراضي إنجليزي لو مش عربي
            # ========================================================

            limit = int(kwargs.get('limit', 100))
            offset = int(kwargs.get('offset', 0))

            # تمرير الـ lang في الـ context يضمن عمل ترجمات أودو الافتراضية
            Cat = request.env['product.category'].sudo().with_context(lang=lang)

            domain = []
            # التأكد من ترتيب الحقول الموجودة
            order_fields = [f for f in ['parent_path', 'parent_left', 'name', 'id'] if f in Cat._fields]
            order = ', '.join(order_fields) or 'id'

            cats = Cat.search(domain, order=order)

            base_url = request.httprequest.host_url.rstrip('/')
            data = []

            for c in cats:
                # 1. 🔥 تحديد اسم القسم ووصفه بذكاء حسب اللغة 🔥
                if raw_lang == 'ar':
                    # لو عربي: نبحث عن الحقل المخصص، وإلا نأخذ الأساسي
                    loc_name = getattr(c, 'ar_name', False) or c.name
                    loc_desc = getattr(c, 'ar_description', False) or c.description or ""
                else:
                    # لو إنجليزي: نبحث عن الحقل المخصص en_name (لو موجود)، وإلا نأخذ الأساسي المُترجم
                    loc_name = getattr(c, 'en_name', False) or c.name
                    loc_desc = getattr(c, 'en_description', False) or c.description or ""

                # تحويل القيم إلى نص صريح (String) لتجنب أخطاء False عند استخدام الدوال النصية
                loc_name = str(loc_name) if loc_name else ""
                loc_desc = str(loc_desc) if loc_desc else ""

                # 🚀 فلترة جديدة: استبعاد قسم "الكل" أو "All" نهائياً
                if loc_name.strip().lower() in ['all', 'الكل']:
                    continue

                # 🔥 فلترة 1: استبعاد القسم لو اسمه أقل من 4 حروف
                if not loc_name or len(loc_name.strip()) < 4:
                    continue

                # 🔥 فلترة 2: إحصاء عدد المنتجات
                storable_count = request.env['product.template'].sudo().search_count([
                    ('categ_id', 'child_of', c.id),
                    ('detailed_type', '!=', 'service')
                ])

                service_count = request.env['product.template'].sudo().search_count([
                    ('categ_id', 'child_of', c.id),
                    ('detailed_type', '=', 'service')
                ])

                if storable_count == 0 or storable_count < service_count:
                    continue

                img_url = None
                if getattr(c, "image_128", False):
                    img_url = f"{base_url}/api/public/image/product.category/{c.id}/image_128"

                data.append({
                    "id": c.id,
                    "name": loc_name,
                    "description": loc_desc,
                    "parent_id": c.parent_id.id if getattr(c, 'parent_id', False) else None,
                    "image_url": img_url,
                    "lang": raw_lang,
                })

            # تطبيق الـ Limit والـ Offset
            paginated_data = data[offset:offset + limit]

            return self._json({
                "paging": {
                    "total": len(data),
                    "count": len(paginated_data),
                    "limit": limit,
                    "offset": offset
                },
                "categories": paginated_data,
                "detected_lang": raw_lang
            }, status=200)

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.exception("product_categories_list failed")
            return self._json({"error": str(e)}, status=500)