from odoo import http,fields
from odoo.http import request, Response
from odoo.tools import float_round
import jwt
import logging
import json
from datetime import datetime
import base64

from .api import _json_ok, _json_err, _t
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

_logger = logging.getLogger(__name__)
import pytz
import json
import jwt
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

def _partner_from_token():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err(_t("bearer_token_required", en="Authorization Bearer token is required", ar="رمز التفويض Bearer مطلوب"), status=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner_id = payload.get("partner_id")
        if not partner_id:
            return None, _json_err(_t("invalid_token_payload", en="Invalid token payload", ar="بيانات الرمز غير صالحة"), status=401)

        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("partner_not_found", status=404)

        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json_err("token_expired", status=401)
    except jwt.InvalidTokenError:
        return None, _json_err("invalid_token", status=401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err("server_error", status=400)


def _partner_or_device():
    """
    Get authenticated partner OR device_id for guest users.
    Returns: (partner, device_id, is_guest, error)
    - If authenticated: (partner, None, False, None)
    - If guest with device_id: (guest_partner, device_id, True, None)
    - If neither: (None, None, False, error)

    IMPORTANT: If a non-empty Bearer token is provided but is invalid/expired,
    returns an auth error immediately (does NOT fall through to guest mode).
    Only falls through to guest mode when NO token is provided (or token is empty).
    """
    # First try to get authenticated user
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:  # Non-empty token was explicitly provided
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                partner_id = payload.get("partner_id")
                if partner_id:
                    partner = request.env["res.partner"].sudo().browse(partner_id)
                    if partner.exists():
                        return partner, None, False, None
                # Token decoded but partner not found
                _logger.warning("Token valid but partner_id %s not found", partner_id)
                return None, None, False, _json_err(
                    _t("invalid_token_payload",
                       en="Invalid token payload",
                       ar="\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0631\u0645\u0632 \u063a\u064a\u0631 \u0635\u0627\u0644\u062d\u0629"), status=401)
            except jwt.ExpiredSignatureError:
                _logger.info("Bearer token expired, returning 401")
                return None, None, False, _json_err("token_expired", status=401)
            except jwt.InvalidTokenError:
                _logger.info("Bearer token invalid, returning 401")
                return None, None, False, _json_err("invalid_token", status=401)
            except Exception as e:
                _logger.exception("Token decode error: %s", e)
                return None, None, False, _json_err("server_error", status=400)
        # Empty token after "Bearer " - fall through to guest mode

    # No valid auth token provided - try device_id for guest user
    device_id = request.httprequest.headers.get("X-Device-ID")
    if not device_id:
        # Try from body
        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            device_id = body.get("device_id")
        except Exception:
            pass

    if device_id:
        # Get or create guest partner
        Partner = request.env["res.partner"].sudo()
        guest_partner = Partner.search([("email", "=", "guest@guest.local")], limit=1)
        if not guest_partner:
            guest_partner = Partner.create({
                "name": "Guest Customer",
                "email": "guest@guest.local",
                "is_company": False,
            })
        return guest_partner, device_id, True, None

    return None, None, False, _json_err("token_required", status=401)


def _get_or_create_cart(partner, device_id, is_guest, cart_type):
    """
    Get or create a cart (sale.order) for authenticated user or guest.
    """
    SaleOrder = request.env["sale.order"].sudo()

    if is_guest:
        # Search for guest cart by device_id
        order = SaleOrder.search([
            ("device_id", "=", device_id),
            ("is_guest_cart", "=", True),
            ("state", "=", "draft"),
            ("origin", "=", cart_type)
        ], limit=1)

        if not order:
            order = SaleOrder.create({
                "partner_id": partner.id,
                "device_id": device_id,
                "is_guest_cart": True,
                "state": "draft",
                "origin": cart_type,
            })
            _logger.info(f"Created new guest {cart_type} for device {device_id}")
    else:
        # Search for authenticated user's cart
        order = SaleOrder.search([
            ("partner_id", "=", partner.id),
            ("state", "=", "draft"),
            ("origin", "=", cart_type),
            ("is_guest_cart", "=", False)
        ], limit=1)

        if not order:
            order = SaleOrder.create({
                "partner_id": partner.id,
                "state": "draft",
                "origin": cart_type,
                "is_guest_cart": False,
            })
            _logger.info(f"Created new {cart_type} for partner {partner.id}")

    return order


def _build_item_data(line, base_url, partner=None):
    """
    Build a unified cart item dict for a sale.order.line.
    - Updated: Arabic description fallback to English if empty.
    - Standardized: Image logic (/api/public/image/).
    """
    product_tmpl = line.product_template_id.sudo()
    product_variant = line.product_id.sudo()

    # --- 1. معالجة الصور (بناءً على الستاندرد المعتمد) ---
    main_image_url = None
    if product_tmpl.sudo().image_1920:
        main_image_url = f"{base_url}/api/public/image/product.template/{product_tmpl.id}/image_1920"
    elif product_variant.sudo().image_1920:
        main_image_url = f"{base_url}/api/public/image/product.product/{product_variant.id}/image_1920"

    gallery_urls = []
    if hasattr(product_tmpl, 'product_template_image_ids'):
        for img in product_tmpl.product_template_image_ids.sudo():
            gallery_urls.append(f"{base_url}/api/public/image/product.image/{img.id}/image_1920")

    # --- 2. معالجة الوصف (التحسين المطلوب) ---
    # الوصف الإنجليزي الافتراضي
    description = product_tmpl.description_sale or ""

    # جلب الوصف العربي (من الفارينت أولاً ثم التيمبلت)
    ar_val = getattr(product_variant, 'ar_description', False) or getattr(product_tmpl, 'ar_description', None)

    # "المنطق الجديد": لو الوصف العربي ممسوح أو فاضي، نضع الوصف الإنجليزي مكانه
    ar_description = ar_val if ar_val else description

    # --- 3. استخراج مواصفات الفارينت ---
    variant_values = []
    if product_variant.product_template_attribute_value_ids:
        for attr_value in product_variant.product_template_attribute_value_ids:
            variant_values.append({
                "attribute": attr_value.attribute_id.name,
                "value": attr_value.name
            })
    variant_display_name = product_variant.display_name

    # --- 4. تحديد النوع (Combo vs Service) ---
    detailed_type = product_tmpl.detailed_type
    if detailed_type == 'service':
        if getattr(product_variant, 'is_appointment_package', False):
            detailed_type = 'combo'
        else:
            detailed_type = 'service'

    # --- 5. معالجة بيانات المواعيد والجدولة ---
    appointment_lines_data = []
    all_lines_scheduled = True
    appointment_details = None

    if detailed_type == 'combo' and hasattr(product_variant, 'appointment_package_line_ids'):
        package_lines = product_variant.appointment_package_line_ids.sudo()
        for al in package_lines:
            exists = request.env['appointment.management'].sudo().search_count([
                ('partner_id', '=', partner.id if partner else False),
                ('product_id', '=', al.product_id.id),
                ('state', '!=', '4')
            ])

            line_is_scheduled = True if exists > 0 else False
            if not line_is_scheduled:
                all_lines_scheduled = False

            service_image_url = None
            if al.product_id.sudo().image_1920:
                service_image_url = f"{base_url}/api/public/image/product.product/{al.product_id.id}/image_1920"

            appointment_lines_data.append({
                "package_line_id": al.id,
                "product_id": al.product_id.id,
                "name": al.product_id.name,
                "image_url": service_image_url,
                "branch_id": al.branch_id.id if al.branch_id else None,
                "is_scheduled": line_is_scheduled,
                "service_price_inside": al.service_price_inside,
                "service_slot_inside": al.service_slot_inside,
                "service_price_outside": al.service_price_outside,
                "service_slot_outside": al.service_slot_outside,
            })
        is_scheduled = all_lines_scheduled

    elif detailed_type == 'service':
        app = getattr(line, 'appointment_id', False)
        is_scheduled = bool(app)
        if app:
            appointment_details = {
                "id": app.id,
                "date": str(app.date) if app.date else None,
                "time": getattr(app, 'time', 0),
                "state": getattr(app, 'state', 'draft')
            }
    else:
        is_scheduled = False

    # --- 6. حساب الأسعار ---
    original_unit_price = float(product_tmpl.list_price or 0.0)
    price_after_discount = float(getattr(product_tmpl, 'price_after_discount', original_unit_price))
    current_unit_price = line.price_unit
    if 0 < price_after_discount < original_unit_price:
        current_unit_price = price_after_discount

    # --- 7. بناء الرد النهائي ---
    res = {
        "line_id": line.id,
        "product_variant": product_variant.id,
        "product_id": product_tmpl.id,
        "name": product_tmpl.name,
        "description": description,
        "ar_description": ar_description,  # سيحتوي على الإنجليزي في حال غياب العربي
        "variant_name": variant_display_name,
        "variant_values": variant_values,
        "qty": line.product_uom_qty,
        "price_unit": current_unit_price,
        "original_unit_price": original_unit_price,
        "price_subtotal": line.product_uom_qty * current_unit_price,
        "total_price": line.product_uom_qty * current_unit_price,
        "detailed_type": detailed_type,
        "is_scheduled": is_scheduled,
        "main_image_url": main_image_url,
        "gallery_urls": gallery_urls,
        "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
        "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
    }

    if detailed_type == 'combo':
        res["appointment_lines"] = appointment_lines_data
    elif detailed_type == 'service':
        res["appointment_details"] = appointment_details
        pkg_lines = product_variant.appointment_package_line_ids.sudo()
        if pkg_lines:
            first_service = pkg_lines[0]
            res.update({
                "service_slot_inside": first_service.service_slot_inside,
                "service_price_inside": first_service.service_price_inside,
                "branch_id": first_service.branch_id.id if first_service.branch_id else None,
            })

    return res


def _build_cart_response(order, base_url, partner=None):
    """
    Build a unified cart-level dict for a sale.order.
    - Separates reward/discount lines from actual products.
    - Separates delivery/pickup fees using Odoo's logical flags.
    - Accurately calculates total_qty and total_discount (Savings).
    """
    cart_items = []
    applied_discounts = []  # لستة جديدة لحفظ الخصومات بشكل مستقل
    total_qty = 0
    total_saving = 0
    delivery_amount = 0.0  # متغير لحفظ مصاريف الشحن / الاستلام

    # استخدام sudo لضمان الوصول للبيانات
    for line in order.order_line.sudo():

        # 🚀 1. اللوجيك الذكي لمعرفة ما إذا كان السطر عبارة عن خدمة توصيل/استلام
        is_delivery = getattr(line, 'is_delivery', False)

        # 🚀 2. اللوجيك الذكي لمعرفة ما إذا كان السطر خصم (مكافأة ولاء أو منتج بسعر سالب)
        is_reward = getattr(line, 'is_reward_line', False) or bool(getattr(line, 'reward_id', False))
        is_manual_discount = line.price_total < 0

        # --- معالجة الشحن والاستلام (استبعاد من قائمة المنتجات) ---
        if is_delivery:
            # هنضيف قيمتها للمتغير ده عشان نرجعه في الهيدر، ومش هنكمل اللوب عشان متنزلش كمنتج
            delivery_amount += line.price_total
            continue

        # --- معالجة الخصومات (وضعها في قائمة منفصلة) ---
        if is_reward or is_manual_discount:
            reward_type = 'discount'
            if getattr(line, 'reward_id', False):
                reward_type = line.reward_id.reward_type
            elif is_manual_discount and not is_reward:
                reward_type = 'manual_discount'

            applied_discounts.append({
                "line_id": line.id,
                "name": line.product_id.name,
                "description": line.name,
                "type": reward_type,
                "qty": line.product_uom_qty,
                "amount": abs(line.price_total),  # قيمة الخصم كقيمة موجبة للعرض
            })

            # إضافة قيمة هذا السطر لإجمالي التوفير
            total_saving += abs(line.price_total)
            continue

        # --- المنتجات الحقيقية المشتراة فقط ---
        item_data = _build_item_data(line, base_url, partner=partner)
        cart_items.append(item_data)

        # تحديث إجمالي الكمية في السلة للمنتجات الحقيقية فقط
        total_qty += line.product_uom_qty

        # حساب التوفير للسطر الحالي (في حالة وجود تخفيض مباشر على سعر الوحدة)
        orig_price = item_data.get('original_unit_price', line.price_unit)
        line_saving = (orig_price - line.price_unit) * line.product_uom_qty

        if line_saving > 0:
            total_saving += line_saving

    # --- بناء الرد النهائي للهيدر الخاص بالسلة ---
    return {
        "order_id": order.id,
        "cart_id": order.id,
        "origin": order.origin,
        "cart_type": order.origin,
        "state": order.state,
        "partner_id": order.partner_id.id if order.partner_id else None,
        "is_guest_cart": order.is_guest_cart,
        "device_id": order.device_id or None,

        # المنتجات العادية فقط اللي عدت من הפلاتر اللي فوق
        "items": cart_items,
        "lines": cart_items,

        # --- الخصومات المفصولة ---
        "discounts": applied_discounts,

        # 🚀 إضافة مصاريف الاستلام من الفرع / الشحن كحقل منفصل عشان الموبايل
        "delivery_fee": delivery_amount,

        # الأرقام والإحصائيات بناءً على المنتجات الفعلية فقط
        "total_items": len(cart_items),
        "item_count": len(cart_items),
        "total_qty": total_qty,

        # الحسابات المالية (مستخرجة مباشرة من طلب المبيعات في أودو شاملة كل شيء)
        "amount_untaxed": order.amount_untaxed,
        "subtotal": order.amount_untaxed,
        "amount_tax": order.amount_tax,
        "tax": order.amount_tax,
        "amount_total": order.amount_total,
        "total": order.amount_total,

        "currency": order.currency_id.name if order.currency_id else None,

        # الخصم الكلي ومؤشرات الخصم
        "discount": round(total_saving, 2),
        "total_saving": round(total_saving, 2),
        "has_discount": len(applied_discounts) > 0 or total_saving > 0
    }

class CartApiController(http.Controller):

    @http.route("/api/cart/add/product", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_cart_product(self, **kwargs):
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            # 🚀 1. استخراج اللغة لتحديد الترجمة وأسماء المنتجات
            is_ar = request.httprequest.headers.get('lang', 'en').lower() in ['ar', 'ar_001']
            odoo_lang = 'ar_001' if is_ar else 'en_US'

            raw = request.httprequest.data or b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return _json_err("بيانات غير صالحة (JSON غير صحيح)" if is_ar else "Invalid JSON payload", status=400)

            products = body.get("products", [])
            if not products:
                return _json_err("لم يتم تحديد أي منتجات" if is_ar else "No products provided", status=400)

            SaleOrderLine = request.env["sale.order.line"].sudo()
            order = _get_or_create_cart(partner, device_id, is_guest, "product_cart")

            for item in products:
                product_id = item.get("product_id")
                qty = float(item.get("qty", 1))

                if not product_id or qty <= 0:
                    continue

                # 🚀 2. جلب المنتج مع تثبيت لغة الموبايل
                product = request.env["product.product"].sudo().with_context(lang=odoo_lang).browse(product_id)

                if product.exists() and product.product_tmpl_id:
                    product_template = product.product_tmpl_id
                else:
                    product_template = request.env["product.template"].sudo().with_context(lang=odoo_lang).browse(
                        product_id)
                    if product_template.exists():
                        product = product_template.product_variant_ids[:1]
                        if not product:
                            continue
                    else:
                        continue

                if product_template.detailed_type == 'service':
                    continue

                is_storable = product_template.detailed_type == 'product'

                # 🚀 3. جلب الاسم المترجم بشكل صريح ومنع فقدان الترجمة
                product_global = product.sudo().with_company(order.company_id).with_context(
                    lang=odoo_lang,
                    warehouse=False,
                    location=False
                )
                product_name_clean = product_global.name or product_global.display_name

                # 🚀 4. [الحل الجذري للمخازن المتعددة الفروع/الشركات]: الاستعلام المباشر
                if is_storable:
                    # تم حذف شرط الشركة نهائياً ليتم سحب المخزون من كل المواقع في الصورة
                    quants = request.env['stock.quant'].sudo().search([
                        ('product_id', '=', product.id),
                        ('location_id.usage', '=', 'internal')
                    ])
                    # حساب الكمية الكلية (الموجود - المحجوز) لضمان الدقة المطلقة من كل الفروع
                    total_on_hand = sum(quants.mapped('quantity'))
                    total_reserved = sum(quants.mapped('reserved_quantity'))
                    actual_stock = total_on_hand - total_reserved

                    available_qty = actual_stock
                    _logger.info(
                        f"📦 PRODUCT {product.id} GLOBAL STOCK: On Hand = {total_on_hand}, Reserved = {total_reserved}, Final Available = {available_qty}")
                else:
                    available_qty = float('inf')

                # 🚀 5. التحقق من المخزون وتجهيز الرسائل المترجمة
                if is_storable and qty > available_qty:
                    if available_qty <= 0:
                        msg = f"عذراً، نفد المخزون من المنتج ({product_name_clean})" if is_ar else f"Sorry, out of stock for ({product_name_clean})"
                    else:
                        msg = f"المتاح {int(available_qty)} قطعة فقط من المنتج ({product_name_clean})" if is_ar else f"Only {int(available_qty)} units available for ({product_name_clean})"

                    return _json_err(
                        msg,
                        data={
                            "product_id": product_template.id,
                            "variant_id": product.id,
                            "product_name": product_name_clean,
                            "available_qty": available_qty,
                            "requested_qty": qty,
                        },
                        status=400
                    )

                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)
                price_unit = product_template.price_after_discount if getattr(product_template, "price_after_discount",
                                                                              0) > 0 else product.lst_price

                if existing_line:
                    new_qty = existing_line.product_uom_qty + qty

                    if is_storable and new_qty > available_qty:
                        remaining_qty = int(available_qty - existing_line.product_uom_qty)
                        if remaining_qty <= 0:
                            msg = f"أضفت كل الكمية المتاحة لسلتك من المنتج ({product_name_clean})" if is_ar else f"You added all available units for ({product_name_clean})"
                        else:
                            msg = f"المتبقي للإضافة {remaining_qty} قطعة فقط من المنتج ({product_name_clean})" if is_ar else f"Only {remaining_qty} units left to add for ({product_name_clean})"

                        return _json_err(
                            msg,
                            data={
                                "product_id": product_template.id,
                                "product_name": product_name_clean,
                                "available_qty": available_qty,
                                "existing_qty": existing_line.product_uom_qty,
                                "requested_additional_qty": qty,
                            },
                            status=400
                        )
                    existing_line.product_uom_qty = new_qty
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price_unit,
                        "name": product_name_clean,  # حفظ الاسم المترجم الصحيح
                    })

            order.message_post(body=f"Product cart updated via API at {datetime.now()}")
            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            cart_data = _build_cart_response(order, base_url, partner=partner)

            return _json_ok("تم تحديث السلة بنجاح" if is_ar else "Cart updated successfully", data=cart_data,
                            status=200)

        except Exception as e:
            _logger.exception("add_to_cart_product error: %s", e)
            msg_err = "حدث خطأ داخلي، يرجى المحاولة لاحقاً" if is_ar else "Internal server error"
            return _json_err(f"{msg_err}: {str(e)}", status=500)
    @http.route("/api/cart/add/service", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_cart_service(self, **kwargs):
        """
        Add 'service' or 'combo' products to user's service cart (draft Sale Order).
        Supports both authenticated users and guest users with device_id.
        Quantity is always set to 1.
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
        Body (JSON):
        {
            "products": [
                {"product_id": 123}
            ],
            "device_id": "optional_device_id" (alternative to header)
        }
        Response: Same structure as /api/cart/add/product
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return _json_err("Invalid JSON payload", status=400)

            # Accept both "products" and "services" keys for flexibility
            products = body.get("products", body.get("services", []))
            if not products:
                return _json_err("No products or services provided. Use 'products' or 'services' key.", status=400)

            SaleOrderLine = request.env["sale.order.line"].sudo()

            # Get or create cart using helper function
            order = _get_or_create_cart(partner, device_id, is_guest, "service_cart")

            for item in products:
                product_id = item.get("product_id")

                if not product_id:
                    continue

                # Try as product.template ID first, then fallback to product.product ID
                product_template = request.env["product.template"].sudo().browse(product_id)
                if product_template.exists():
                    product = product_template.product_variant_ids[:1] or product_template
                else:
                    # Fallback: try as product.product (variant) ID
                    product = request.env["product.product"].sudo().browse(product_id)
                    if not product.exists():
                        _logger.warning(f"Service/combo not found (tried template and variant): {product_id}")
                        continue
                    product_template = product.product_tmpl_id

                if product_template.detailed_type not in ("service", "combo"):
                    _logger.warning(f"Product {product_id} skipped (detailed_type={product_template.detailed_type})")
                    continue

                qty = 1
                # Use list_price from template as fallback (product.template has list_price, product.product has lst_price)
                price = getattr(product, 'lst_price', None) or product_template.list_price

                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)
                if existing_line:
                    existing_line.product_uom_qty = qty
                    # Reset is_scheduled to False when item is re-added/updated
                    existing_line.is_scheduled = False
                    _logger.info(f"Updated {product_template.type} {product.id} quantity to {qty}")
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price,
                        "name": product.display_name,
                        "is_scheduled": False,  # Default to False for new items
                    })
                    _logger.info(f"Added new {product_template.type} {product.id} to cart")

            order.message_post(body=f"Service/Combo cart updated via API at {datetime.now()}")

            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            cart_data = _build_cart_response(order, base_url, partner=partner)

            return _json_ok(
                "Service/Combo cart updated successfully",
                data=cart_data,
                status=200
            )

        except Exception as e:
            _logger.exception("add_to_cart_service error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/remove/<int:template_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def remove_cart_item(self, template_id, **kwargs):
        """
        Remove a specific product/service (by template_id) from all of the user's active draft carts.
        Supports both authenticated users and guest users with device_id.
        Also deletes related appointment records for service/combo products.
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            # Build search domain based on auth type
            if is_guest:
                orders = SaleOrder.search([
                    ("device_id", "=", device_id),
                    ("is_guest_cart", "=", True),
                    ("state", "=", "draft"),
                    ("origin", "in", ["product_cart", "service_cart"])
                ])
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("is_guest_cart", "=", False),
                    ("state", "=", "draft"),
                    ("origin", "in", ["product_cart", "service_cart"])
                ])

            if not orders:
                return _json_err("No active carts found", status=404)

            product_template = request.env["product.template"].sudo().browse(template_id)
            if not product_template.exists():
                return _json_err("Product template not found", status=404)

            variants = product_template.product_variant_ids
            if not variants:
                return _json_err("No variants found for this product template", status=404)

            variant_ids = variants.ids

            removed_items = []

            for order in orders:
                line = order.order_line.filtered(lambda l: l.product_id.id in variant_ids)

                if line:
                    # For service/combo products, delete related appointment records
                    # Only for authenticated users (guest uses shared partner, can't track appointments)
                    if not is_guest and product_template.detailed_type in ["service", "combo"]:
                        for variant in variants:
                            # Delete appointments for the main package/service
                            appointments = request.env['appointment.management'].sudo().search([
                                ('partner_id', '=', partner.id),
                                ('product_id', '=', variant.id),
                            ])
                            if appointments:
                                appointments.unlink()
                                _logger.info(f"Deleted {len(appointments)} appointment(s) for product {variant.id}")

                            # Delete appointments for sub-services in package
                            if hasattr(variant, 'appointment_package_line_ids'):
                                for package_line in variant.appointment_package_line_ids.sudo():
                                    sub_appointments = request.env['appointment.management'].sudo().search([
                                        ('partner_id', '=', partner.id),
                                        ('product_id', '=', package_line.product_id.id),
                                    ])
                                    if sub_appointments:
                                        sub_appointments.unlink()
                                        _logger.info(f"Deleted {len(sub_appointments)} appointment(s) for sub-service {package_line.product_id.id}")

                    line.unlink()
                    removed_items.append({
                        "order_id": order.id,
                        "removed_product": product_template.display_name,
                        "remaining_items": len(order.order_line),
                        "total_amount": order.amount_total,
                    })

                    _logger.info(
                        f"Removed product template {template_id} (variants {variant_ids}) from cart for partner {partner.id}, order {order.id}"
                    )

                    order.message_post(body=f"Product {template_id} removed via API at {datetime.now()}")

            if not removed_items:
                return _json_err("Product not found in any cart", status=404)

            return _json_ok(
                "Product removed successfully from all carts",
                data={
                    "removed_items": removed_items,
                },
                status=200
            )

        except Exception as e:
            _logger.exception("remove_cart_item error: %s", e)
            return _json_err(str(e), status=500)

    @http.route(['/api/image/<string:model>/<int:record_id>/<string:field>'], type='http', auth='public', csrf=False)
    def get_public_image(self, model, record_id, field, **kwargs):
        try:
            record = request.env[model].sudo().browse(record_id)
            if not record.exists():
                return request.not_found()

            image_data = getattr(record, field, False)
            if not image_data:
                return request.not_found()

            image_base64 = base64.b64decode(image_data)
            headers = [
                ('Content-Type', 'image/png'),
                ('Cache-Control', 'max-age=86400'),
            ]
            return request.make_response(image_base64, headers=headers)

        except Exception as e:
            _logger.exception("Image fetch error: %s", e)
            return request.make_response(b'', [('Content-Type', 'text/plain')])



    # @http.route(
    #     ["/api/cart", "/api/cart/<int:order_id>"],
    #     type="http",
    #     auth="public",
    #     methods=["GET"],
    #     csrf=False
    # )
    # def get_cart(self, order_id=None, **kwargs):
    #     """
    #     Get one or multiple draft carts for the authenticated user.
    #     Headers:
    #         Authorization: Bearer <access_token>
    #         X-Cart-Type: "product" or "service"
    #     URL:
    #         /api/cart                     → Get all draft carts
    #         /api/cart/<order_id>          → Get one specific cart by ID
    #         /api/cart?ids=7,6             → Get multiple carts by ID list
    #     """
    #     partner, err = _partner_from_token()
    #     if err:
    #         return err

    #     try:
    #         SaleOrder = request.env["sale.order"].sudo()
    #         base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")

    #         cart_type = request.httprequest.headers.get("X-Cart-Type", "").lower()

    #         origin_filter = []
    #         if cart_type == "product":
    #             origin_filter = ["product_cart"]
    #         elif cart_type == "service":
    #             origin_filter = ["service_cart"]
    #         else:
    #             origin_filter = ["product_cart", "service_cart"]

    #         ids_param = kwargs.get("ids")
    #         if ids_param:
    #             try:
    #                 order_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip().isdigit()]
    #             except Exception:
    #                 return _json_err("Invalid ids parameter format. Use comma-separated integers.", status=400)
    #         else:
    #             order_ids = []

    #         if order_id:
    #             orders = SaleOrder.browse([order_id])
    #         elif order_ids:
    #             orders = SaleOrder.browse(order_ids)
    #         else:
    #             orders = SaleOrder.search([
    #                 ("partner_id", "=", partner.id),
    #                 ("state", "=", "draft"),
    #                 ("origin", "in", origin_filter),
    #             ])

    #         orders = orders.exists().filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")

    #         if not orders:
    #             return _json_err("No draft carts found", status=404)

    #         def _build_cart_data(order):
    #             cart_items = []
    #             total_discount = 0

    #             for line in order.order_line.sudo():
    #                 product_tmpl = line.product_template_id.sudo()

    #                 if not product_tmpl.is_appointment_service and product_tmpl.detailed_type == "service":
    #                     total_discount += line.price_unit * line.product_uom_qty
    #                     #continue # Removed by Kabir to fix appoimnet service issues

    #                 main_image_url = (
    #                     f"{base_url}/api/image/product.template/{product_tmpl.id}/image_1920"
    #                     if product_tmpl.image_1920 else None
    #                 )

    #                 gallery_urls = []
    #                 if hasattr(product_tmpl, "img_ids"):
    #                     for img in product_tmpl.img_ids.sudo():
    #                         if img.img:
    #                             gallery_urls.append(
    #                                 f"{base_url}/api/image/product.template.img/{img.id}/img"
    #                             )

    #                 # cart_items.append({
    #                 #     "product_variant": line.product_id.id,
    #                 #     "product_id": product_tmpl.id,
    #                 #     "name": product_tmpl.display_name,
    #                 #     "qty": line.product_uom_qty,
    #                 #     "is_scheduled": line.is_scheduled,
    #                 #     "price_unit": line.price_unit,
    #                 #     "total_price": line.price_subtotal,
    #                 #     "tax_amount": sum(line.tax_id.sudo().mapped("amount")),
    #                 #     "description": product_tmpl.description,
    #                 #     "detailed_type": product_tmpl.detailed_type,
    #                 #     "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
    #                 #     "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
    #                 #     "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
    #                 #     "barcode": product_tmpl.barcode,
    #                 #     "avg_rating": product_tmpl.avg_rating,
    #                 #     "top": product_tmpl.top,
    #                 #     "main_image_url": main_image_url,
    #                 #     "gallery_urls": gallery_urls,
    #                 #     "ar_name": product_tmpl.ar_name,
    #                 #     "ar_description": product_tmpl.ar_description,
    #                 # })

    #                 # --- Appointment service lines (for services only) ---
    #                 appointment_lines_data = []
    #                 if product_tmpl.detailed_type == "service" and hasattr(line.product_id, 'appointment_package_line_ids'):
    #                     for al in line.product_id.appointment_package_line_ids.sudo():
    #                         appointment_lines_data.append({
    #                             "package_line_id": al.id,
    #                             "product_id": al.product_id.id,
    #                             "name": al.product_id.name,
    #                             "branch_id": al.branch_id.id,
    #                             "department_id": al.department_id.id,
    #                             "service_slot_inside": al.service_slot_inside,
    #                             "service_slot_outside": al.service_slot_outside,
    #                             "service_price_inside": al.service_price_inside,
    #                             "service_price_outside": al.service_price_outside,
    #                             "currency_id": al.currency_id.id,
    #                         })

    #                 cart_items.append({
    #                     "product_variant": line.product_id.id,
    #                     "product_id": product_tmpl.id,
    #                     "name": product_tmpl.name,
    #                     "qty": line.product_uom_qty,
    #                     "is_scheduled": line.is_scheduled,
    #                     "price_unit": line.price_unit,
    #                     "total_price": line.price_subtotal,
    #                     "tax_amount": sum(line.tax_id.sudo().mapped("amount")),
    #                     "description": product_tmpl.description,
    #                     "detailed_type": product_tmpl.detailed_type,
    #                     "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
    #                     "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
    #                     "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
    #                     "barcode": product_tmpl.barcode,
    #                     "avg_rating": product_tmpl.avg_rating,
    #                     "top": product_tmpl.top,
    #                     "main_image_url": main_image_url,
    #                     "gallery_urls": gallery_urls,
    #                     "ar_name": product_tmpl.ar_name,
    #                     "ar_description": product_tmpl.ar_description,
    #                     "appointment_lines": appointment_lines_data,
    #                 })

    #             return {
    #                 "order_id": order.id,
    #                 "origin": order.origin,
    #                 "state": order.state,
    #                 "partner_id": order.partner_id.id,
    #                 "items": cart_items,
    #                 "total_items": len(cart_items),
    #                 "amount_untaxed": order.amount_untaxed,
    #                 "amount_tax": order.amount_tax,
    #                 "amount_total": order.amount_total,
    #                 "discount": total_discount,
    #             }

    #         carts_data = [_build_cart_data(order) for order in orders]

    #         if not carts_data:
    #             return _json_err("No items found for this type", status=404)

    #         return _json_ok(
    #             "Carts fetched successfully",
    #             data={"count": len(carts_data), "orders": carts_data},
    #             status=200,
    #         )

    #     except Exception as e:
    #         _logger.exception("get_cart error: %s", e)
    #         return _json_err(str(e), status=500)
    @http.route(
        ["/api/cart", "/api/cart/<int:order_id>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False
    )
    def get_cart(self, order_id=None, **kwargs):
        """
        Get one or multiple draft carts for the authenticated user or guest.
        Supports both authenticated users and guest users with device_id.
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
            X-Cart-Type: "product" or "service" (optional, returns both if unset)
        URL:
            /api/cart                     → Get all draft carts
            /api/cart/<order_id>          → Get one specific cart by ID
            /api/cart?ids=7,6             → Get multiple carts by ID list
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        # --- بداية كود الترجمة المضاف ---
        header_lang = request.httprequest.headers.get('lang')
        raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
        lang_map = {'ar': 'ar_001', 'en': 'en_US'}
        odoo_lang = lang_map.get(raw_lang, 'en_US')
        # --- نهاية كود الترجمة المضاف ---

        try:
            # إضافة with_context(lang=odoo_lang) عشان الموديل يرجع الداتا مترجمة
            SaleOrder = request.env["sale.order"].sudo().with_context(lang=odoo_lang)
            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")

            # Determine which carts to fetch based on header
            # Check X-Cart-Type first, then 'type' header for compatibility
            cart_type = (
                    request.httprequest.headers.get("X-Cart-Type", "").strip().lower()
                    or request.httprequest.headers.get("type", "").strip().lower()
            )
            origin_filter = []
            if cart_type in ("product", "products", "product_cart"):
                origin_filter = ["product_cart"]
            elif cart_type in ("service", "services", "service_cart"):
                origin_filter = ["service_cart"]
            else:
                origin_filter = ["product_cart", "service_cart"]

            # Handle bulk ID fetching
            ids_param = kwargs.get("ids")
            if ids_param:
                try:
                    order_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip().isdigit()]
                except Exception:
                    return _json_err("Invalid ids parameter format.", status=400)
            else:
                order_ids = []

            # Fetch Orders
            if order_id:
                orders = SaleOrder.browse([order_id])
            elif order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                if is_guest:
                    orders = SaleOrder.search([
                        ("device_id", "=", device_id),
                        ("is_guest_cart", "=", True),
                        ("state", "=", "draft"),
                        ("origin", "in", origin_filter),
                    ])
                else:
                    orders = SaleOrder.search([
                        ("partner_id", "=", partner.id),
                        ("is_guest_cart", "=", False),
                        ("state", "=", "draft"),
                        ("origin", "in", origin_filter),
                    ])

            # Validation: Ensure they belong to the correct owner and are still in draft
            if is_guest:
                orders = orders.exists().filtered(
                    lambda o: o.device_id == device_id and o.is_guest_cart and o.state == "draft"
                )
            else:
                orders = orders.exists().filtered(
                    lambda o: o.partner_id.id == partner.id and not o.is_guest_cart and o.state == "draft"
                )

            if not orders:
                return _json_err("No draft carts found", status=404)

            carts_data = [_build_cart_response(order, base_url, partner=partner) for order in orders]

            return _json_ok(
                "Carts fetched successfully",
                data={"count": len(carts_data), "orders": carts_data},
                status=200,
            )

        except Exception as e:
            _logger.exception("get_cart error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/update", type="http", auth="public", methods=["PUT", "POST"], csrf=False)
    def update_cart_line(self, **kwargs):
        """
        Update quantity of a cart line.
        Supports both authenticated users and guest users with device_id.
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
        Body (JSON):
            {
                "line_id": 123,       // sale.order.line ID
                "product_id": 456,    // OR product.template ID (alternative to line_id)
                "cart_type": "product_cart",  // required when using product_id: "product_cart" or "service_cart"
                "qty": 5
            }
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            line_id = body.get("line_id")
            product_id = body.get("product_id")
            cart_type = body.get("cart_type")
            qty = float(body.get("qty", 0))

            SaleOrderLine = request.env["sale.order.line"].sudo()
            line = None

            if line_id:
                # Direct line_id lookup
                line = SaleOrderLine.browse(line_id)
                if not line.exists():
                    return _json_err("Cart line not found", status=404)
            elif product_id:
                # Lookup by product.template ID within user's cart
                product_template = request.env["product.template"].sudo().browse(product_id)
                if not product_template.exists():
                    return _json_err("Product not found", status=404)

                variant_ids = product_template.product_variant_ids.ids

                # Find the cart
                order = _get_or_create_cart(partner, device_id, is_guest, cart_type or "product_cart")
                line = order.order_line.filtered(lambda l: l.product_id.id in variant_ids)[:1]
                if not line:
                    return _json_err("Product not found in cart", status=404)
            else:
                return _json_err("line_id or product_id is required", status=400)

            # Verify ownership
            if is_guest:
                if not line.order_id.is_guest_cart or line.order_id.device_id != device_id:
                    return _json_err("Cart line does not belong to this device", status=403)
            else:
                if line.order_id.is_guest_cart or line.order_id.partner_id.id != partner.id:
                    return _json_err("Cart line does not belong to this user", status=403)

            order = line.order_id
            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")

            if qty <= 0:
                # Remove line if qty is 0 or negative
                line.unlink()
                return _json_ok("Cart line removed", data=_build_cart_response(order, base_url, partner=partner))

            # Check stock for products (not services)
            product = line.product_id
            if product.detailed_type not in ('service', 'combo'):
                available_qty = float(product.qty_available or 0.0)
                if qty > available_qty:
                    return _json_err(
                        f"Requested quantity exceeds available stock.",
                        data={
                            "product_id": line.product_template_id.id,
                            "available_qty": available_qty,
                            "requested_qty": qty,
                        },
                        status=400
                    )

            # Store original price_unit before update
            original_price = line.price_unit

            # Update quantity using SQL to avoid Odoo's automatic price recalculation
            request.env.cr.execute(
                "UPDATE sale_order_line SET product_uom_qty = %s WHERE id = %s",
                (qty, line.id)
            )
            request.env.cr.commit()

            # Clear ALL caches to force fresh reads from database
            request.env.invalidate_all()

            # Recompute line-level amounts (price_subtotal, price_tax, price_total)
            # This is necessary because raw SQL bypasses ORM dependency tracking
            line._compute_amount()

            # Recompute order-level totals
            order._compute_amounts()
            if hasattr(order, '_compute_tax_totals'):
                order._compute_tax_totals()

            _logger.info(
                f"Cart line {line.id} updated: qty={qty}, price_unit={original_price}, "
                f"subtotal={line.price_subtotal}, tax={line.price_tax}, total={line.price_total}")

            return _json_ok("Cart line updated", data=_build_cart_response(order, base_url, partner=partner))

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("Error updating cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/confirm/product", type="http", auth="public", methods=["POST"], csrf=False)
    def confirm_product_order(self, **kwargs):
        """
        Confirm product draft Sale Orders for the authenticated user and create invoices.
        Headers:
            Authorization: Bearer <access_token>
        Usage:
            POST /api/cart/confirm/product             → confirm product draft order
            POST /api/cart/confirm/product?ids=7,6     → confirm specific product draft orders by IDs
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()
            AccountMove = request.env["account.move"].sudo()

            ids_param = kwargs.get("ids")
            order_ids = []
            if ids_param:
                try:
                    order_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip().isdigit()]
                except Exception:
                    return _json_err("Invalid ids parameter format. Use comma-separated integers.", status=400)

            if order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "=", "product_cart")
                ])

            orders = orders.filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")
            if not orders:
                return _json_err("No valid product draft orders found for confirmation", status=404)

            confirmed_orders = []

            for order in orders:
                order.action_confirm()
                _logger.info(f"Product Order {order.id} confirmed for partner {partner.id}")

                invoices = order._create_invoices()
                if not invoices:
                    _logger.warning(f"No invoice created for product order {order.id}")
                    continue

                created_invoice = invoices[0]
                confirmed_orders.append({
                    "order_id": order.id,
                    "invoice_id": created_invoice.id,
                    "invoice_number": created_invoice.name,
                    "total_amount": created_invoice.amount_total,
                    # "state": order.state,
                    "state": 'draft',
                    "origin": order.origin,
                })

            if not confirmed_orders:
                return _json_err("No invoices were created for the provided orders", status=500)

            return _json_ok(
                "Product orders confirmed and invoices created successfully",
                data={
                    "count": len(confirmed_orders),
                    "results": confirmed_orders
                },
                status=200
            )

        except Exception as e:
            _logger.exception("confirm_product_order error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/confirm/service", type="http", auth="public", methods=["POST"], csrf=False)
    def confirm_service_order(self, **kwargs):
        """
        Confirm service draft Sale Orders for the authenticated user and create invoices.
        Headers:
            Authorization: Bearer <access_token>
        Usage:
            POST /api/cart/confirm/service             → confirm service draft order
            POST /api/cart/confirm/service?ids=7,6     → confirm specific service draft orders by IDs
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()
            AccountMove = request.env["account.move"].sudo()

            ids_param = kwargs.get("ids")
            order_ids = []
            if ids_param:
                try:
                    order_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip().isdigit()]
                except Exception:
                    return _json_err("Invalid ids parameter format. Use comma-separated integers.", status=400)

            if order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "=", "service_cart")
                ])

            orders = orders.filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")
            if not orders:
                return _json_err("No valid service draft orders found for confirmation", status=404)

            confirmed_orders = []

            for order in orders:
                order.action_confirm()
                _logger.info(f"Service Order {order.id} confirmed for partner {partner.id}")

                invoices = order._create_invoices()
                if not invoices:
                    _logger.warning(f"No invoice created for service order {order.id}")
                    continue

                created_invoice = invoices[0]
                confirmed_orders.append({
                    "order_id": order.id,
                    "invoice_id": created_invoice.id,
                    "invoice_number": created_invoice.name,
                    "total_amount": created_invoice.amount_total,
                    # "state": order.state,
                    "state": 'draft',
                    "origin": order.origin,
                })

            if not confirmed_orders:
                return _json_err("No invoices were created for the provided orders", status=500)

            return _json_ok(
                "Service orders confirmed and invoices created successfully",
                data={
                    "count": len(confirmed_orders),
                    "results": confirmed_orders
                },
                status=200
            )

        except Exception as e:
            _logger.exception("confirm_service_order error: %s", e)
            return _json_err(str(e), status=500)


    @http.route('/api/cart/apply-coupon/products', type='http', auth='public', methods=['POST'], csrf=False)
    def apply_coupon_products(self, **kwargs):
        """
        Apply coupon to PRODUCT carts only by adding a proper negative discount line.
        Headers:
            Authorization: Bearer <access_token>
        Body:
            {"coupon_code": "ABC123"}
        """
        try:
            raw_data = request.httprequest.data or b"{}"
            body = json.loads(raw_data.decode("utf-8"))
            coupon_code = body.get('coupon_code')

            if not coupon_code:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Coupon code is required'}),
                    status=400, content_type='application/json'
                )

            partner, err = _partner_from_token()
            if err:
                return err

            loyalty_card = request.env['loyalty.card'].sudo().search([('code', '=', coupon_code)], limit=1)
            if not loyalty_card:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Coupon code not found'}),
                    status=404, content_type='application/json'
                )

            loyalty_program = loyalty_card.program_id
            if not loyalty_program:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Loyalty program not found'}),
                    status=404, content_type='application/json'
                )

            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft'),
                ('origin', '=', 'product_cart')
            ], limit=1)

            if not sale_order:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No active PRODUCT sale order found'}),
                    status=404, content_type='application/json'
                )

            reward = loyalty_program.reward_ids[:1]
            if not reward:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No rewards available'}),
                    status=400, content_type='application/json'
                )

            reward = reward[0]
            discount_product = reward.discount_line_product_id
            discount_percentage = reward.discount

            if not discount_product:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No discount product linked to reward'}),
                    status=400, content_type='application/json'
                )

            existing_coupon_line = sale_order.order_line.filtered(lambda l: l.product_id.id == discount_product.id)
            if existing_coupon_line:
                existing_coupon_line.unlink()

            subtotal_before_discount = sum(line.price_subtotal for line in sale_order.order_line)
            # Use Odoo's float_round for proper decimal precision
            discount_amount = float_round((subtotal_before_discount * discount_percentage) / 100, precision_digits=2)

            # Get default tax from discount product or from company settings
            discount_taxes = discount_product.taxes_id
            if not discount_taxes:
                # Use same taxes as the order lines if discount product has no taxes
                order_line_taxes = sale_order.order_line.filtered(lambda l: l.tax_id).mapped('tax_id')
                if order_line_taxes:
                    discount_taxes = order_line_taxes[:1]  # Use first tax found

            discount_line = request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': discount_product.id,
                'name': f"{reward.description or 'Discount'} ({discount_percentage}% Off)",
                'product_uom_qty': 1,
                'tax_id': [(6, 0, discount_taxes.ids)] if discount_taxes else [(6, 0, [])],
            })

            discount_line.sudo().write({'price_unit': -abs(discount_amount)})

            # Recompute taxes and amounts after applying discount
            sale_order._compute_amounts()
            if hasattr(sale_order, '_compute_tax_totals'):
                sale_order._compute_tax_totals()

            sale_order.message_post(
                body=f"Coupon {coupon_code} applied ({discount_percentage}% off = {discount_amount:.2f})."
            )

            return Response(
                json.dumps({
                    'status': 'success',
                    'message': f'Coupon applied successfully to PRODUCT cart ({discount_percentage}% off)',
                    'sale_order_id': sale_order.id,
                    'price_before_discount': subtotal_before_discount,
                    'discount_amount': discount_amount,
                    'sale_order_amount': sale_order.amount_total,
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.exception("Error applying coupon to PRODUCT cart")
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/cart/apply-coupon/services', type='http', auth='public', methods=['POST'], csrf=False)
    def apply_coupon_services(self, **kwargs):
        """
        Apply coupon to SERVICE carts only by adding a proper negative discount line.
        Headers:
            Authorization: Bearer <access_token>
        Body:
            {"coupon_code": "ABC123"}
        """
        try:
            raw_data = request.httprequest.data or b"{}"
            body = json.loads(raw_data.decode("utf-8"))
            coupon_code = body.get('coupon_code')

            if not coupon_code:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Coupon code is required'}),
                    status=400, content_type='application/json'
                )

            partner, err = _partner_from_token()
            if err:
                return err

            loyalty_card = request.env['loyalty.card'].sudo().search([('code', '=', coupon_code)], limit=1)
            if not loyalty_card:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Coupon code not found'}),
                    status=404, content_type='application/json'
                )

            loyalty_program = loyalty_card.program_id
            if not loyalty_program:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Loyalty program not found'}),
                    status=404, content_type='application/json'
                )

            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft'),
                ('origin', '=', 'service_cart')
            ], limit=1)

            if not sale_order:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No active SERVICE sale order found'}),
                    status=404, content_type='application/json'
                )

            reward = loyalty_program.reward_ids[:1]
            if not reward:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No rewards available'}),
                    status=400, content_type='application/json'
                )

            reward = reward[0]
            discount_product = reward.discount_line_product_id
            discount_percentage = reward.discount

            if not discount_product:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No discount product linked to reward'}),
                    status=400, content_type='application/json'
                )

            existing_coupon_line = sale_order.order_line.filtered(lambda l: l.product_id.id == discount_product.id)
            if existing_coupon_line:
                existing_coupon_line.unlink()

            subtotal_before_discount = sum(line.price_subtotal for line in sale_order.order_line)
            # Use Odoo's float_round for proper decimal precision
            discount_amount = float_round((subtotal_before_discount * discount_percentage) / 100, precision_digits=2)

            # Get default tax from discount product or from company settings
            discount_taxes = discount_product.taxes_id
            if not discount_taxes:
                # Use same taxes as the order lines if discount product has no taxes
                order_line_taxes = sale_order.order_line.filtered(lambda l: l.tax_id).mapped('tax_id')
                if order_line_taxes:
                    discount_taxes = order_line_taxes[:1]  # Use first tax found

            discount_line = request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': discount_product.id,
                'name': f"{reward.description or 'Discount'} ({discount_percentage}% Off)",
                'product_uom_qty': 1,
                'tax_id': [(6, 0, discount_taxes.ids)] if discount_taxes else [(6, 0, [])],
            })

            discount_line.sudo().write({'price_unit': -abs(discount_amount)})

            # Recompute taxes and amounts after applying discount
            sale_order._compute_amounts()
            if hasattr(sale_order, '_compute_tax_totals'):
                sale_order._compute_tax_totals()

            sale_order.message_post(
                body=f"Coupon {coupon_code} applied ({discount_percentage}% off = {discount_amount:.2f})."
            )

            return Response(
                json.dumps({
                    'status': 'success',
                    'message': f'Coupon applied successfully to SERVICE cart ({discount_percentage}% off)',
                    'sale_order_id': sale_order.id,
                    'price_before_discount': subtotal_before_discount,
                    'discount_amount': discount_amount,
                    'sale_order_amount': sale_order.amount_total,
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.exception("Error applying coupon to SERVICE cart")
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                content_type='application/json'
            )

    # @http.route("/api/cart/clear/products", type="http", auth="public", methods=["DELETE"], csrf=False)
    # def clear_product_cart_lines(self, **kwargs):
    #     """
    #     Clear all product lines (product type) from all draft PRODUCT carts for the authenticated user.
    #     Headers:
    #         Authorization: Bearer <access_token>
    #     """
    #     partner, err = _partner_from_token()
    #     if err:
    #         return err
    #
    #     try:
    #         SaleOrder = request.env["sale.order"].sudo()
    #
    #         product_orders = SaleOrder.search([
    #             ("partner_id", "=", partner.id),
    #             ("state", "=", "draft"),
    #             ("origin", "=", "product_cart")
    #         ])
    #
    #         if not product_orders:
    #             return _json_err("No draft PRODUCT carts found", status=404)
    #
    #         total_lines_removed = 0
    #         cleared_orders = []
    #
    #         for order in product_orders:
    #             product_lines = order.order_line.filtered(lambda l: l.product_id.detailed_type == "product")
    #             total_lines_removed += len(product_lines)
    #             if product_lines:
    #                 product_lines.unlink()
    #                 order.message_post(body=f"All product lines cleared via API at {datetime.now()}")
    #                 cleared_orders.append(order.id)
    #
    #         return _json_ok(
    #             "Product lines cleared successfully",
    #             data={
    #                 "cleared_orders": cleared_orders,
    #                 "total_orders": len(cleared_orders),
    #                 "total_lines_removed": total_lines_removed
    #             },
    #             status=200
    #         )
    #
    #     except Exception as e:
    #         _logger.exception("clear_product_cart_lines error: %s", e)
    #         return _json_err(str(e), status=500)

    @http.route("/api/cart/clear/products", type="http", auth="public", methods=["DELETE"], csrf=False)
    def clear_product_cart_lines(self, **kwargs):
        """
        Clear all product lines (product type) and coupon lines from all draft PRODUCT carts.
        Supports both authenticated users and guest users with device_id.
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            # Build search domain based on auth type
            if is_guest:
                product_orders = SaleOrder.search([
                    ("device_id", "=", device_id),
                    ("is_guest_cart", "=", True),
                    ("state", "=", "draft"),
                    ("origin", "=", "product_cart")
                ])
            else:
                product_orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("is_guest_cart", "=", False),
                    ("state", "=", "draft"),
                    ("origin", "=", "product_cart")
                ])

            if not product_orders:
                return _json_err("No draft PRODUCT carts found", status=404)

            total_lines_removed = 0
            cleared_orders = []

            for order in product_orders:
                product_lines = order.order_line.filtered(lambda l: l.product_id.detailed_type == "product")
                coupon_lines = order.order_line.filtered(lambda l: l.price_unit < 0)

                all_lines_to_remove = product_lines | coupon_lines
                total_lines_removed += len(all_lines_to_remove)

                if all_lines_to_remove:
                    all_lines_to_remove.unlink()
                    order.message_post(body=f"All product lines and coupon lines cleared via API at {datetime.now()}")
                    cleared_orders.append(order.id)

            return _json_ok(
                "Product lines and coupon lines cleared successfully",
                data={
                    "cleared_orders": cleared_orders,
                    "total_orders": len(cleared_orders),
                    "total_lines_removed": total_lines_removed
                },
                status=200
            )

        except Exception as e:
            _logger.exception("clear_product_cart_lines error: %s", e)
            return _json_err(str(e), status=500)

    # @http.route("/api/cart/clear/services", type="http", auth="public", methods=["DELETE"], csrf=False)
    # def clear_service_cart_lines(self, **kwargs):
    #     """
    #     Clear all service or combo lines from all draft SERVICE carts for the authenticated user.
    #     Headers:
    #         Authorization: Bearer <access_token>
    #     """
    #     partner, err = _partner_from_token()
    #     if err:
    #         return err
    #
    #     try:
    #         SaleOrder = request.env["sale.order"].sudo()
    #
    #         service_orders = SaleOrder.search([
    #             ("partner_id", "=", partner.id),
    #             ("state", "=", "draft"),
    #             ("origin", "=", "service_cart")
    #         ])
    #
    #         if not service_orders:
    #             return _json_err("No draft SERVICE carts found", status=404)
    #
    #         total_lines_removed = 0
    #         cleared_orders = []
    #
    #         for order in service_orders:
    #             service_lines = order.order_line.filtered(lambda l: l.product_id.detailed_type in ["service", "combo"])
    #             total_lines_removed += len(service_lines)
    #             if service_lines:
    #                 service_lines.unlink()
    #                 order.message_post(body=f"All service/combo lines cleared via API at {datetime.now()}")
    #                 cleared_orders.append(order.id)
    #
    #         return _json_ok(
    #             "Service lines cleared successfully",
    #             data={
    #                 "cleared_orders": cleared_orders,
    #                 "total_orders": len(cleared_orders),
    #                 "total_lines_removed": total_lines_removed
    #             },
    #             status=200
    #         )
    #
    #     except Exception as e:
    #         _logger.exception("clear_service_cart_lines error: %s", e)
    #         return _json_err(str(e), status=500)

    @http.route("/api/cart/clear/services", type="http", auth="public", methods=["DELETE"], csrf=False)
    def clear_service_cart_lines(self, **kwargs):
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()
            Appointment = request.env["appointment.management"].sudo()

            # 1. بناء الدومين للبحث عن سلال الخدمات المسودة
            domain = [("state", "=", "draft"), ("origin", "=", "service_cart")]
            if is_guest:
                domain += [("device_id", "=", device_id), ("is_guest_cart", "=", True)]
            else:
                domain += [("partner_id", "=", partner.id), ("is_guest_cart", "=", False)]

            service_orders = SaleOrder.search(domain)

            if not service_orders:
                return _json_err("No draft SERVICE carts found", status=404)

            total_lines_removed = 0
            total_appointments_cancelled = 0
            cleared_orders = []

            for order in service_orders:
                all_lines = order.order_line

                # --- التعديل الجديد: إلغاء الحجوزات المرتبطة ---
                # البحث عن المواعيد المرتبطة بأسطر هذا الأوردر
                for line in all_lines:
                    # 1. إلغاء المواعيد المباشرة المرتبطة بالسطر (الخدمات المنفردة)
                    if hasattr(line, 'appointment_id') and line.appointment_id:
                        app = line.appointment_id
                        if app.state != '4':  # لو مش ملغي أصلاً
                            app.action_appointment_cancel()  # دالة الإلغاء الموجودة في الموديل
                            total_appointments_cancelled += 1

                    # 2. إلغاء مواعيد البكجات (Combos)
                    # بما أن البكج لا يغلق السطر، بنبحث عن أي حجز للعميل لنفس الخدمات في حالة draft/confirmed
                    if not is_guest and line.product_id.appointment_package_line_ids:
                        pkg_services = line.product_id.appointment_package_line_ids.mapped('product_id')
                        related_apps = Appointment.search([
                            ('partner_id', '=', partner.id),
                            ('product_id', 'in', pkg_services.ids),
                            ('state', 'in', ['1', '2'])  # Partial Approved / Approved
                        ])
                        for app in related_apps:
                            app.action_appointment_cancel()
                            total_appointments_cancelled += 1

                # مسح الأسطر من السلة
                total_lines_removed += len(all_lines)
                if all_lines:
                    all_lines.unlink()
                    order.message_post(
                        body=f"Cleared {len(all_lines)} lines and associated appointments via API at {datetime.now()}")
                    cleared_orders.append(order.id)

            return _json_ok(
                "Service lines and associated appointments cleared successfully",
                data={
                    "cleared_orders": cleared_orders,
                    "total_lines_removed": total_lines_removed,
                    "total_appointments_cancelled": total_appointments_cancelled
                },
                status=200
            )

        except Exception as e:
            _logger.exception("clear_service_cart_lines error: %s", e)
            return _json_err(str(e), status=500)
    # @http.route("/api/cart/confirm/cash", type="http", auth="public", methods=["POST"], csrf=False)
    # def confirm_cash_payment(self, **kwargs):
    #     partner, err = _partner_from_token()
    #     if err:
    #         return err
    #
    #     try:
    #         raw = request.httprequest.data or b"{}"
    #         body = json.loads(raw.decode("utf-8"))
    #         order_id = body.get("order_id")
    #
    #         if not order_id:
    #             return _json_err("order_id is required", status=400)
    #
    #         SaleOrder = request.env["sale.order"].sudo()
    #         PaymentRegister = request.env["account.payment.register"].sudo()
    #
    #         order = SaleOrder.browse(order_id)
    #         if not order.exists():
    #             return _json_err("Order not found", status=404)
    #
    #         if order.partner_id.id != partner.id:
    #             return _json_err("You are not allowed to confirm this order", status=403)
    #
    #
    #         if order.state == "draft":
    #             order.action_confirm()
    #
    #
    #         existing_invoice = order.invoice_ids.filtered(lambda m: m.move_type == "out_invoice")
    #
    #         if existing_invoice:
    #             invoice = existing_invoice[0]
    #         else:
    #             invoices = order._create_invoices()
    #             invoice = invoices[0] if invoices else None
    #
    #         if not invoice:
    #             return _json_err("Invoice creation failed", status=500)
    #
    #
    #         if invoice.state == "draft":
    #             invoice.action_post()
    #
    #
    #         if invoice.payment_state == "paid":
    #             return _json_ok(
    #                 "Invoice already paid",
    #                 data={
    #                     "order_id": order.id,
    #                     "invoice_id": invoice.id,
    #                     "invoice_state": invoice.payment_state,
    #                     "total_amount": invoice.amount_total
    #                 }
    #             )
    #
    #
    #         cash_journal = request.env["account.journal"].sudo().search([
    #             ("type", "=", "cash")
    #         ], limit=1)
    #
    #         if not cash_journal:
    #             return _json_err("No cash journal found", 500)
    #
    #         payment_register = PaymentRegister.with_context(
    #             active_model="account.move",
    #             active_ids=[invoice.id]
    #         ).create({
    #             "journal_id": cash_journal.id,
    #             "amount": invoice.amount_total,
    #             "payment_method_line_id": request.env.ref(
    #                 "account.account_payment_method_manual_in"
    #             ).id,
    #         })
    #
    #         payment_register.action_create_payments()
    #
    #         order.message_post(body="Cash payment completed & linked to invoice via API.")
    #
    #         return _json_ok(
    #             "Cash payment completed successfully",
    #             data={
    #                 "order_id": order.id,
    #                 "invoice_id": invoice.id,
    #                 "invoice_state": invoice.payment_state,
    #                 "total_amount": invoice.amount_total
    #             }
    #         )
    #
    #     except Exception as e:
    #         _logger.exception("confirm_cash_payment error: %s", e)
    #         return _json_err(str(e), status=500)

    # @http.route('/api/cart/confirm/cash', type='http', auth='none', methods=['POST'], csrf=False)
    # def confirm_cash_payment(self, **kwargs):
    #     try:
    #         raw_data = request.httprequest.data or b"{}"
    #         body = json.loads(raw_data.decode("utf-8"))
    #         order_id = body.get('order_id')
    #
    #         if not order_id:
    #             return Response(
    #                 json.dumps({'status': 'error', 'message': 'Order ID is required'}),
    #                 status=400, content_type='application/json'
    #             )
    #
    #         sale_order = request.env['sale.order'].sudo().browse(order_id)
    #         if not sale_order.exists():
    #             return Response(
    #                 json.dumps({'status': 'error', 'message': 'Sale order not found'}),
    #                 status=404, content_type='application/json'
    #             )
    #
    #         pos_session = request.env['pos.session'].sudo().search([('state', '=', 'opened')], limit=1)
    #         if not pos_session:
    #             return Response(
    #                 json.dumps({'status': 'error', 'message': 'No active POS session found'}),
    #                 status=500, content_type='application/json'
    #             )
    #
    #         if not pos_session.config_id.sequence_id:
    #             return Response(
    #                 json.dumps({'status': 'error', 'message': 'POS Sequence ID is missing in the configuration'}),
    #                 status=500, content_type='application/json'
    #             )
    #
    #         session_id = pos_session.id
    #         sequence_id = pos_session.config_id.sequence_id.id
    #
    #         order_name = pos_session.config_id.sequence_id._next()
    #
    #         amount_tax = sale_order.amount_tax if sale_order.amount_tax else 0.0
    #
    #         amount_paid = sale_order.amount_total
    #
    #         amount_return = 0.0
    #
    #         pos_order = request.env['pos.order'].sudo().create({
    #             'session_id': session_id,
    #             'name': order_name,
    #             'order_id': sale_order.id,
    #             'amount_total': sale_order.amount_total,
    #             'amount_tax': amount_tax,
    #             'amount_paid': amount_paid,
    #             'amount_return': amount_return,
    #         })
    #
    #         pos_payment = request.env['pos.payment'].sudo().create({
    #             'pos_order_id': pos_order.id,
    #             'amount': amount_paid,
    #             'payment_method_id': 1,
    #             'payment_date': datetime.now(),
    #         })
    #
    #         pos_order.payment_ids = [(4, pos_payment.id)]
    #
    #         return Response(
    #             json.dumps({
    #                 'status': 'success',
    #                 'message': 'Payment confirmed successfully',
    #                 'data': {'order_id': pos_order.id, 'name': pos_order.name}
    #             }),
    #             status=200,
    #             content_type='application/json'
    #         )
    #
    #     except Exception as e:
    #         _logger.error("Error confirming payment for order %s: %s", order_id, str(e))
    #         return Response(
    #             json.dumps({'status': 'error', 'message': str(e)}),
    #             status=500,
    #             content_type='application/json'
    #         )

    @http.route('/api/cart/confirm/cash', type='http', auth='none', methods=['POST'], csrf=False)
    def confirm_cash_payment(self, **kwargs):
        try:
            raw_data = request.httprequest.data or b"{}"
            body = json.loads(raw_data.decode("utf-8"))
            order_id = body.get('order_id')

            if not order_id:
                return Response(
                    json.dumps({'status': 'error', 'message': 'Order ID is required'}),
                    status=400, content_type='application/json'
                )

            sale_order = request.env['sale.order'].sudo().browse(order_id)
            if not sale_order.exists():
                return Response(
                    json.dumps({'status': 'error', 'message': 'Sale order not found'}),
                    status=404, content_type='application/json'
                )
            sale_order.sudo().action_confirm()

            pos_session = request.env['pos.session'].sudo().search([('state', '=', 'opened')], limit=1)
            if not pos_session:
                return Response(
                    json.dumps({'status': 'error', 'message': 'No active POS session found'}),
                    status=500, content_type='application/json'
                )

            if not pos_session.config_id.sequence_id:
                return Response(
                    json.dumps({'status': 'error', 'message': 'POS Sequence ID is missing in the configuration'}),
                    status=500, content_type='application/json'
                )

            session_id = pos_session.id
            sequence_id = pos_session.config_id.sequence_id.id

            order_name = pos_session.config_id.sequence_id._next()

            amount_tax = sale_order.amount_tax if sale_order.amount_tax else 0.0
            amount_paid = sale_order.amount_total
            amount_return = 0.0

            pos_order = request.env['pos.order'].sudo().create({
                'session_id': session_id,
                'name': order_name,
                'order_id': sale_order.id,
                'amount_total': sale_order.amount_total,
                'amount_tax': amount_tax,
                'amount_paid': amount_paid,
                'amount_return': amount_return,
            })

            pos_payment = request.env['pos.payment'].sudo().create({
                'pos_order_id': pos_order.id,
                'amount': amount_paid,
                'payment_method_id': 1,
                'payment_date': datetime.now(),
            })

            pos_order.payment_ids = [(4, pos_payment.id)]

            partner = sale_order.partner_id
            product = sale_order.order_line[0].product_id

            appointment = request.env['appointment.management'].sudo().search([
                ('partner_id', '=', partner.id),
                ('product_id', '=', product.id),
                ('state', '=', '2')
            ], limit=1)

            if appointment:
                appointment.write({
                    'state': '3'
                })

            return Response(
                json.dumps({
                    'status': 'success',
                    'message': 'Payment confirmed successfully',
                    'data': {'order_id': pos_order.id, 'name': pos_order.name}
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error("Error confirming payment for order %s: %s", order_id, str(e))
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                content_type='application/json'
            )



    @http.route('/api/cart/remove/coupon', type='http', auth='public', methods=['POST'], csrf=False)
    def remove_coupon_from_cart(self, **kwargs):
        """
        Remove coupon from the authenticated user's product or service cart by token.
        Headers:
            Authorization: Bearer <access_token>
        Body (JSON):
            {
                "remove_coupon": true,
                "cart_type": "product"  // or "service"
            }
        Response:
            {
                "status": "success",
                "message": "Coupon removed successfully"
            }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw_data = request.httprequest.data or b"{}"
            body = json.loads(raw_data.decode("utf-8"))
            remove_coupon = body.get('remove_coupon')
            cart_type = body.get('cart_type')

            if not remove_coupon:
                return Response(
                    json.dumps({'status': 'error', 'message': 'remove_coupon key is required'}),
                    status=400, content_type='application/json'
                )

            if not cart_type or cart_type not in ["product", "service"]:
                return Response(
                    json.dumps({'status': 'error', 'message': 'cart_type is required and must be "product" or "service"'}),
                    status=400, content_type='application/json'
                )

            sale_order = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'draft'),
                ('origin', '=', f'{cart_type}_cart')
            ], limit=1)

            if not sale_order:
                return Response(
                    json.dumps({'status': 'error', 'message': f'No active {cart_type} sale order found'}),
                    status=404, content_type='application/json'
                )

            if cart_type == 'product':
                existing_coupon_line = sale_order.order_line.filtered(lambda l: l.price_unit < 0)
            elif cart_type == 'service':
                existing_coupon_line = sale_order.order_line.filtered(lambda l: l.price_unit < 0)

            if existing_coupon_line:
                existing_coupon_line.unlink()
                sale_order._compute_amounts()
                sale_order.message_post(
                    body=f"Coupon removed from {cart_type} cart via API."
                )
                return Response(
                    json.dumps({
                        'status': 'success',
                        'message': f'Coupon removed successfully from the {cart_type} cart',
                        'sale_order_id': sale_order.id,
                        'sale_order_amount': sale_order.amount_total
                    }),
                    status=200,
                    content_type='application/json'
                )

            return Response(
                json.dumps({'status': 'error', 'message': 'No coupon found to remove in the cart'}),
                status=404,
                content_type='application/json'
            )

        except Exception as e:
            _logger.exception("Error removing coupon from cart")
            return Response(
                json.dumps({'status': 'error', 'message': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route("/api/cart/add/combo", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_cart_combo(self, **kwargs):
        """
        Add service / combo products to user's service cart.
        Supports both authenticated users and guest users with device_id.
        product_id is a product.template ID (unified with other cart endpoints).
        Quantity is always 1
        Headers:
            Authorization: Bearer <access_token> (for authenticated users)
            OR
            X-Device-ID: <device_id> (for guest users)
        """
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return _json_err("Invalid JSON payload", status=400)

            # Accept "products", "services", or "combos" keys for flexibility
            products = body.get("products", body.get("services", body.get("combos", [])))
            if not products:
                return _json_err("No products provided. Use 'products', 'services', or 'combos' key.", status=400)

            SaleOrderLine = request.env["sale.order.line"].sudo()

            # Get or create cart using helper function
            order = _get_or_create_cart(partner, device_id, is_guest, "service_cart")

            for item in products:
                product_id = item.get("product_id")
                if not product_id:
                    continue

                # Try as product.template ID first, then fallback to product.product ID
                product_template = request.env["product.template"].sudo().browse(product_id)
                if product_template.exists():
                    product = product_template.product_variant_ids[:1] or product_template
                else:
                    # Fallback: try as product.product (variant) ID
                    product = request.env["product.product"].sudo().browse(product_id)
                    if not product.exists():
                        _logger.warning(f"Combo not found (tried template and variant): {product_id}")
                        continue
                    product_template = product.product_tmpl_id

                if product_template.detailed_type not in ("service", "combo"):
                    _logger.warning(
                        f"Skipped product {product_id} (detailed_type={product_template.detailed_type})"
                    )
                    continue

                qty = 1
                # Use list_price from template as fallback (product.template has list_price, product.product has lst_price)
                price = getattr(product, 'lst_price', None) or product_template.list_price

                existing_line = order.order_line.filtered(
                    lambda l: l.product_id.id == product.id
                )

                if existing_line:
                    existing_line.product_uom_qty = qty
                    # Reset is_scheduled to False when combo is re-added/updated
                    existing_line.is_scheduled = False
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price,
                        "name": product.display_name,
                        "is_scheduled": False,  # Default to False for new items
                    })

            order.message_post(
                body=f"Service/Combo cart updated via API at {datetime.now()}"
            )

            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            cart_data = _build_cart_response(order, base_url, partner=partner)

            return _json_ok(
                "Service/Combo cart updated successfully",
                data=cart_data,
                status=200
            )

        except Exception as e:
            _logger.exception("add_to_cart_combo error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/sale/confirm/product2", type="http", auth="public", methods=["POST"], csrf=False)
    def confirm_product_sale_orders2(self, **kwargs):
        """
        Confirm product sale orders and create invoices using access token
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            ids_param = kwargs.get("ids")
            order_ids = []
            if ids_param:
                order_ids = [int(i) for i in ids_param.split(",") if i.isdigit()]

            if order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "=", "product_cart")
                ])

            orders = orders.filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")
            if not orders:
                return _json_err("No product orders available for confirmation", 404)

            results = []

            for order in orders:
                order.action_confirm()
                invoices = order._create_invoices()

                if not invoices:
                    continue

                invoice = invoices[0]
                results.append({
                    "order_id": order.id,
                    "order_name": order.name,
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "invoice_state": invoice.state,
                    "amount_total": invoice.amount_total,
                })

            if not results:
                return _json_err("Orders confirmed but no invoices created", 500)

            return _json_ok(
                "Product sale orders confirmed successfully",
                {
                    "count": len(results),
                    "results": results
                }
            )

        except Exception as e:
            _logger.exception("confirm_product_sale_orders error")
            return _json_err(str(e), 500)

    @http.route("/api/sale/confirm/service2", type="http", auth="public", methods=["POST"], csrf=False)
    def confirm_service_sale_orders2(self, **kwargs):
        """
        Confirm service sale orders and create invoices using access token
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            ids_param = kwargs.get("ids")
            order_ids = []
            if ids_param:
                order_ids = [int(i) for i in ids_param.split(",") if i.isdigit()]

            if order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "=", "service_cart")
                ])

            orders = orders.filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")
            if not orders:
                return _json_err("No service orders available for confirmation", 404)

            results = []

            for order in orders:
                order.action_confirm()
                invoices = order._create_invoices()

                if not invoices:
                    continue

                invoice = invoices[0]
                results.append({
                    "order_id": order.id,
                    "order_name": order.name,
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.name,
                    "invoice_state": invoice.state,
                    "amount_total": invoice.amount_total,
                })

            if not results:
                return _json_err("Orders confirmed but no invoices created", 500)

            return _json_ok(
                "Service sale orders confirmed successfully",
                {
                    "count": len(results),
                    "results": results
                }
            )

        except Exception as e:
            _logger.exception("confirm_service_sale_orders error")
            return _json_err(str(e), 500)

    @http.route("/api/cart/check/product", type="http", auth="public", methods=["POST"], csrf=False)
    def check_product_qty(self, **kwargs):
        """
        Check if the quantity of a specific product is available in inventory and cart.
        Expected JSON body: {"product_id": <product_id>}
        Returns a message indicating whether the quantity is available in inventory.
        """
        raw_data = request.httprequest.data or b"{}"
        try:
            body = json.loads(raw_data.decode("utf-8"))
        except Exception:
            return _json_err("Invalid JSON payload", status=400)

        product_id = body.get('product_id')
        if not product_id:
            return _json_err("Product ID is required", status=400)

        try:
            product_id = int(product_id)
        except ValueError:
            return _json_err("Invalid Product ID", status=400)

        partner, err = _partner_from_token()
        if err:
            return err

        Product = request.env["product.product"].sudo()

        product = Product.search([("id", "=", product_id)], limit=1)
        if not product:
            return _json_err(f"Product {product_id} does not exist in the inventory", status=404)

        available_qty = product.qty_available
        if available_qty > 0:
            return _json_ok({
                "message": f"Product {product_id} is available in inventory with {available_qty} units."
            })
        else:
            return _json_err(f"Product {product_id} is out of stock", status=404)

    # ==================== GUEST CART ENDPOINTS ====================

    def _get_device_id(self):
        """Extract device_id from request headers or body."""
        # Try header first
        device_id = request.httprequest.headers.get("X-Device-ID")
        if device_id:
            return device_id

        # Try body
        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            return body.get("device_id")
        except Exception:
            return None

    def _get_or_create_guest_cart(self, device_id, cart_type="product_cart"):
        """Get or create a guest cart for the given device_id."""
        SaleOrder = request.env["sale.order"].sudo()

        # Search for existing guest cart
        order = SaleOrder.search([
            ("device_id", "=", device_id),
            ("is_guest_cart", "=", True),
            ("state", "=", "draft"),
            ("origin", "=", cart_type)
        ], limit=1)

        if not order:
            # Create new guest cart with a guest partner
            guest_partner = self._get_or_create_guest_partner()
            order = SaleOrder.create({
                "partner_id": guest_partner.id,
                "device_id": device_id,
                "is_guest_cart": True,
                "state": "draft",
                "origin": cart_type,
            })
            _logger.info(f"Created new guest cart {order.id} for device {device_id}")

        return order

    def _get_or_create_guest_partner(self):
        """Get or create a generic guest partner for guest carts."""
        Partner = request.env["res.partner"].sudo()
        guest_partner = Partner.search([("email", "=", "guest@guest.local")], limit=1)

        if not guest_partner:
            guest_partner = Partner.create({
                "name": "Guest Customer",
                "email": "guest@guest.local",
                "is_company": False,
            })
            _logger.info(f"Created guest partner with id {guest_partner.id}")

        return guest_partner

    def _format_guest_cart_response(self, order):
        """Format guest cart order for API response with full product data (Unified Logic)."""
        base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url").strip('/')
        lines = []
        applied_discounts = []
        total_qty = 0
        total_saving = 0

        for line in order.order_line.sudo():
            # 1. فلترة خصومات الولاء في مصفوفة منفصلة (لتطابق السلة الأساسية)
            is_reward = getattr(line, 'is_reward_line', False) or bool(getattr(line, 'reward_id', False))
            if is_reward:
                reward_type = line.reward_id.reward_type if getattr(line, 'reward_id', False) else 'discount'
                applied_discounts.append({
                    "line_id": line.id,
                    "name": line.product_id.name,
                    "description": line.name,
                    "type": reward_type,
                    "qty": line.product_uom_qty,
                    "amount": abs(line.price_total),
                })
                total_saving += abs(line.price_total)
                continue

            product = line.product_id
            product_tmpl = product.product_tmpl_id

            # 🚀 2. اكتشاف الـ Combo
            detailed_type = product_tmpl.detailed_type
            if detailed_type == 'service':
                if getattr(product, 'is_appointment_package', False) or len(
                        getattr(product, 'appointment_package_line_ids', [])) > 1:
                    detailed_type = 'combo'

            # 🚀 3. توحيد روابط الصور لتطابق المنتجات العادية
            main_image_url = None
            if product_tmpl.image_1920:
                main_image_url = f"{base_url}/api/public/image/product.template/{product_tmpl.id}/image_1920"
            elif product.image_1920:
                main_image_url = f"{base_url}/api/public/image/product.product/{product.id}/image_1920"

            gallery_urls = []
            if hasattr(product_tmpl, 'product_template_image_ids'):
                for img in product_tmpl.product_template_image_ids:
                    gallery_urls.append(f"{base_url}/api/public/image/product.image/{img.id}/image_1920")

            # 🚀 4. توحيد مصدر القسم (POS للخدمات، والمخازن للمنتجات)
            if detailed_type in ('service', 'combo'):
                cat_obj = product_tmpl.pos_categ_ids[0] if hasattr(product_tmpl,
                                                                   'pos_categ_ids') and product_tmpl.pos_categ_ids else None
                category_name = cat_obj.display_name if cat_obj else (
                    product_tmpl.categ_id.display_name if product_tmpl.categ_id else None)
            else:
                category_name = product_tmpl.categ_id.display_name if product_tmpl.categ_id else None

            # 5. بناء سطور الباقات (Appointments)
            appointment_lines_data = []
            if detailed_type == 'combo' and hasattr(product, 'appointment_package_line_ids'):
                for al in product.appointment_package_line_ids:
                    appointment_lines_data.append({
                        "package_line_id": al.id,
                        "product_id": al.product_id.id,
                        "name": al.product_id.name,
                        "branch_id": al.branch_id.id if al.branch_id else None,
                        "department_id": al.department_id.id if al.department_id else None,
                        "service_slot_inside": getattr(al, 'service_slot_inside', None),
                        "service_slot_outside": getattr(al, 'service_slot_outside', None),
                        "service_price_inside": getattr(al, 'service_price_inside', None),
                        "service_price_outside": getattr(al, 'service_price_outside', None),
                        "currency_id": al.currency_id.id if al.currency_id else None,
                        "is_scheduled": False,
                    })

            total_qty += line.product_uom_qty

            lines.append({
                "line_id": line.id,
                "product_variant": product.id,
                "product_id": product_tmpl.id,
                "name": product_tmpl.name,
                "product_name": product.display_name,
                "qty": line.product_uom_qty,
                "is_scheduled": getattr(line, 'is_scheduled', False),
                "price_unit": line.price_unit,
                "price_subtotal": line.price_subtotal,
                "total_price": line.price_subtotal,
                "price_tax": line.price_tax,
                "tax_amount": line.price_tax,
                "price_total": line.price_total,
                "discount": line.discount,
                "description": product_tmpl.description,

                # === القيم بعد التوحيد ===
                "detailed_type": detailed_type,
                "category": category_name,
                "main_image_url": main_image_url,
                "gallery_urls": gallery_urls,

                "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
                "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
                "barcode": product_tmpl.barcode if hasattr(product_tmpl, 'barcode') else None,
                "avg_rating": getattr(product_tmpl, 'avg_rating', None),
                "top": getattr(product_tmpl, 'top', None),
                "product_image": f"{base_url}/api/public/image/product.product/{product.id}/image_128" if product.image_128 else None,
                "link": f"{base_url}/shop/product/{product_tmpl.id}",
                "ar_name": getattr(product_tmpl, 'ar_name', None),
                "ar_description": getattr(product, 'ar_description', getattr(product_tmpl, 'ar_description', None)),
                "appointment_lines": appointment_lines_data,
            })

        return {
            "cart_id": order.id,
            "order_id": order.id,
            "cart_name": order.name,
            "device_id": order.device_id,
            "is_guest_cart": order.is_guest_cart,
            "cart_type": order.origin,
            "origin": order.origin,
            "state": order.state,
            "lines": lines,
            "items": lines,

            # === الخصومات والإحصائيات الموحدة ===
            "discounts": applied_discounts,

            "subtotal": order.amount_untaxed,
            "amount_untaxed": order.amount_untaxed,
            "tax": order.amount_tax,
            "amount_tax": order.amount_tax,
            "total": order.amount_total,
            "amount_total": order.amount_total,
            "currency": order.currency_id.name if order.currency_id else None,
            "item_count": len(lines),
            "total_items": len(lines),
            "total_qty": total_qty,

            "discount": round(total_saving, 2),
            "total_saving": round(total_saving, 2),
            "has_discount": len(applied_discounts) > 0 or total_saving > 0
        }

    @http.route("/api/guest/cart", type="http", auth="public", methods=["GET"], csrf=False)
    def get_guest_cart(self, **kwargs):
        """
        جلب سلة المشتريات للزائر (Guest) بناءً على معرف الجهاز (device_id).

        الترويسات (Headers) المتاحة:
            X-Device-ID: <device_id> (إجباري)
            X-Cart-Type: "product" أو "service" أو "combo" (اختياري، الافتراضي هو "product")
            lang: "ar" أو "en" (اختياري لتحديد لغة الاستجابة)

        معلمات الرابط (Query params):
            cart_type: "product" أو "service" أو "combo" (الافتراضي: "product")
        """
        # 1. استخراج معرف الجهاز الخاص بالزائر والتأكد من وجوده
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        # --- 2. استخراج إعدادات اللغة والموقع الجغرافي من الـ Headers ---
        header_lang = request.httprequest.headers.get('lang')
        header_lat = request.httprequest.headers.get('latitude')
        header_lng = request.httprequest.headers.get('longitude')

        # تحديد اللغة المطلوبة (من الهيدر أو الرابط، والافتراضي إنجليزي)
        raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
        lang_map = {'ar': 'ar_001', 'en': 'en_US'}
        lang = lang_map.get(raw_lang, raw_lang)
        # ----------------------------------------------------------------

        # 3. تحديد نوع السلة من الترويسات: فحص X-Cart-Type أولاً، ثم type
        cart_type_header = (
                request.httprequest.headers.get("X-Cart-Type", "").strip().lower()
                or request.httprequest.headers.get("type", "").strip().lower()
        )

        # تحديد نوع السلة من الرابط: فحص cart_type أولاً، ثم type
        cart_type_param = (
                kwargs.get("cart_type", "").strip().lower()
                or kwargs.get("type", "").strip().lower()
        )

        # القيمة النهائية لنوع السلة (الافتراضي "product")
        cart_type_raw = cart_type_header or cart_type_param or "product"

        # 4. توحيد صيغة نوع السلة لتتطابق مع قاعدة البيانات (دعم صيغ الجمع والمفرد والكومبو)
        if cart_type_raw in ["product", "product_cart", "products"]:
            cart_type = "product_cart"
        # 🚀 التعديل هنا: إضافة combo عشان تتسجل وتتقري كسلة خدمات
        elif cart_type_raw in ["service", "service_cart", "services", "combo", "combos", "combo_cart"]:
            cart_type = "service_cart"
        else:
            # إرجاع خطأ في حال إرسال نوع سلة غير معروف
            return _json_err("Invalid cart_type. Use 'product', 'service', or 'combo'", status=400)

        try:
            SaleOrder = request.env["sale.order"].sudo()

            # 5. البحث عن سلة الزائر المبدئية في قاعدة البيانات
            order = SaleOrder.search([
                ("device_id", "=", device_id),  # مطابقة الجهاز
                ("is_guest_cart", "=", True),  # التأكد إنها سلة زائر
                ("state", "=", "draft"),  # حالة السلة مبدئية
                ("origin", "=", cart_type)  # مطابقة النوع (منتجات أو خدمات)
            ], limit=1)

            # 6. إذا لم يتم العثور على سلة، نرجع هيكل بيانات فارغ لتفادي أخطاء الـ Frontend
            if not order:
                return _json_ok("No cart found", data={
                    "cart_id": None,
                    "order_id": None,
                    "device_id": device_id,
                    "cart_type": cart_type,
                    "origin": cart_type,
                    "lines": [],
                    "items": [],
                    "subtotal": 0,
                    "amount_untaxed": 0,
                    "tax": 0,
                    "amount_tax": 0,
                    "total": 0,
                    "amount_total": 0,
                    "item_count": 0,
                    "total_items": 0,
                    "total_qty": 0,
                })

            # 7. إذا وجدت السلة، نطبق عليها اللغة المطلوبة ونجهز بياناتها للإرجاع
            order_with_lang = order.with_context(lang=lang)
            return _json_ok("Cart retrieved", data=self._format_guest_cart_response(order_with_lang))

        except Exception as e:
            # 8. اصطياد وتوثيق أي خطأ غير متوقع
            _logger.exception("Error getting guest cart: %s", e)
            return _json_err(str(e), status=500)
    @http.route("/api/guest/cart/add/product", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_guest_cart_product(self, **kwargs):
        """
        Add products to guest cart.
        Headers:
            X-Device-ID: <device_id>
        Body (JSON):
            {
                "products": [
                    {"product_id": 123, "qty": 2},
                    {"product_id": 456, "qty": 1}
                ]
            }
        """
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            products = body.get("products", [])

            if not products:
                return _json_err("No products provided", status=400)

            order = self._get_or_create_guest_cart(device_id, "product_cart")
            SaleOrderLine = request.env["sale.order.line"].sudo()

            for item in products:
                product_id = item.get("product_id")
                qty = float(item.get("qty", 1))

                if not product_id or qty <= 0:
                    continue

                product = request.env["product.product"].sudo().browse(product_id)
                if not product.exists() or product.detailed_type == 'service':
                    continue

                # Check stock availability
                available_qty = float(product.qty_available or 0.0)
                if qty > available_qty:
                    return _json_err(
                        f"Requested quantity for '{product.display_name}' exceeds available stock.",
                        data={
                            "product_id": product.id,
                            "product_name": product.display_name,
                            "available_qty": available_qty,
                            "requested_qty": qty,
                        },
                        status=400
                    )

                # Check if product already in cart
                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)

                if existing_line:
                    new_qty = existing_line.product_uom_qty + qty
                    if new_qty > available_qty:
                        return _json_err(
                            f"Total quantity for '{product.display_name}' exceeds available stock.",
                            data={
                                "product_id": product.id,
                                "available_qty": available_qty,
                                "current_qty": existing_line.product_uom_qty,
                                "requested_qty": qty,
                            },
                            status=400
                        )
                    existing_line.write({"product_uom_qty": new_qty})
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": product.lst_price,
                    })

            return _json_ok("Products added to guest cart", data=self._format_guest_cart_response(order))

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("Error adding to guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/guest/cart/add/service", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_guest_cart_service(self, **kwargs):
        """
        Add services or packages (combos) to guest cart.
        Headers:
            X-Device-ID: <device_id>
        Body (JSON):
            {
                "services": [
                    {"product_id": 123},  // product.template id
                    {"product_id": 456}
                ]
            }
            OR
            {
                "products": [
                    {"product_id": 123},  // product.template id
                    {"product_id": 456}
                ]
            }
        """
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            # Support both "services" and "products" keys for flexibility
            services = body.get("services", body.get("products", []))

            if not services:
                return _json_err("No services or products provided", status=400)

            order = self._get_or_create_guest_cart(device_id, "service_cart")
            SaleOrderLine = request.env["sale.order.line"].sudo()

            for item in services:
                template_id = item.get("product_id")

                if not template_id:
                    continue

                # Handle as product.template ID (like main cart)
                product_template = request.env["product.template"].sudo().browse(template_id)
                if not product_template.exists():
                    # Try as product.product ID as fallback
                    product = request.env["product.product"].sudo().browse(template_id)
                    if not product.exists():
                        _logger.warning(f"Product not found: {template_id}")
                        continue
                    product_template = product.product_tmpl_id
                else:
                    product = product_template.product_variant_ids[:1]
                    if not product:
                        _logger.warning(f"No variant for template: {template_id}")
                        continue

                # Accept service and combo types
                if product_template.detailed_type not in ("service", "combo"):
                    _logger.warning(f"Product {template_id} skipped (detailed_type={product_template.detailed_type})")
                    continue

                qty = 1  # Services always qty 1

                # Check if service already in cart
                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)

                if existing_line:
                    # Reset quantity to 1 and is_scheduled for services
                    existing_line.write({
                        "product_uom_qty": qty,
                        "is_scheduled": False,
                    })
                    _logger.info(f"Updated {product_template.type} {product.id} in guest cart")
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": product.lst_price,
                        "name": product.display_name,
                        "is_scheduled": False,
                    })
                    _logger.info(f"Added {product_template.type} {product.id} to guest cart")

            return _json_ok("Services added to guest cart", data=self._format_guest_cart_response(order))

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("Error adding service to guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/guest/cart/update", type="http", auth="public", methods=["PUT", "POST"], csrf=False)
    def update_guest_cart_line(self, **kwargs):
        """
        Update quantity of a cart line.
        Headers:
            X-Device-ID: <device_id>
        Body (JSON):
            {
                "line_id": 123,
                "qty": 5
            }
        """
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            line_id = body.get("line_id")
            qty = float(body.get("qty", 0))

            if not line_id:
                return _json_err("line_id is required", status=400)

            SaleOrderLine = request.env["sale.order.line"].sudo()
            line = SaleOrderLine.browse(line_id)

            if not line.exists():
                return _json_err("Cart line not found", status=404)

            # Verify line belongs to guest cart with this device_id
            if not line.order_id.is_guest_cart or line.order_id.device_id != device_id:
                return _json_err("Cart line does not belong to this device", status=403)

            if qty <= 0:
                # Remove line if qty is 0 or negative
                order = line.order_id
                line.unlink()
                return _json_ok("Cart line removed", data=self._format_guest_cart_response(order))

            # Check stock for products
            product = line.product_id
            if product.detailed_type != 'service':
                available_qty = float(product.qty_available or 0.0)
                if qty > available_qty:
                    return _json_err(
                        f"Requested quantity exceeds available stock.",
                        data={
                            "product_id": product.id,
                            "available_qty": available_qty,
                            "requested_qty": qty,
                        },
                        status=400
                    )

            order = line.order_id

            # Update quantity using SQL to avoid Odoo's automatic price recalculation
            request.env.cr.execute(
                "UPDATE sale_order_line SET product_uom_qty = %s WHERE id = %s",
                (qty, line.id)
            )
            request.env.cr.commit()

            # Clear ALL caches to force fresh reads from database
            request.env.invalidate_all()

            # Recompute line-level amounts (price_subtotal, price_tax, price_total)
            # This is necessary because raw SQL bypasses ORM dependency tracking
            line._compute_amount()

            # Recompute order-level totals
            order._compute_amounts()
            if hasattr(order, '_compute_tax_totals'):
                order._compute_tax_totals()

            _logger.info(
                f"Guest cart line {line.id} updated: qty={qty}, "
                f"subtotal={line.price_subtotal}, tax={line.price_tax}, total={line.price_total}")

            return _json_ok("Cart line updated", data=self._format_guest_cart_response(order))

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("Error updating guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/guest/cart/remove/<int:line_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def remove_from_guest_cart(self, line_id, **kwargs):
        """
        Remove a line from guest cart.
        Headers:
            X-Device-ID: <device_id>
        """
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        try:
            SaleOrderLine = request.env["sale.order.line"].sudo()
            line = SaleOrderLine.browse(line_id)

            if not line.exists():
                return _json_err("Cart line not found", status=404)

            # Verify line belongs to guest cart with this device_id
            if not line.order_id.is_guest_cart or line.order_id.device_id != device_id:
                return _json_err("Cart line does not belong to this device", status=403)

            order = line.order_id
            line.unlink()

            return _json_ok("Item removed from cart", data=self._format_guest_cart_response(order))

        except Exception as e:
            _logger.exception("Error removing from guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route(["/api/guest/cart/clear", "/api/guest/cart/clear/products", "/api/guest/cart/clear/services"],
                type="http", auth="public", methods=["DELETE"], csrf=False)
    def clear_guest_cart(self, **kwargs):
        """
        Clear all items from guest cart.
        Headers:
            X-Device-ID: <device_id>
            X-Cart-Type: "product" or "service" (optional)
        Query params:
            cart_type: "product" or "service" or "product_cart" or "service_cart"
        Routes:
            /api/guest/cart/clear - clears based on header/param
            /api/guest/cart/clear/products - clears product cart
            /api/guest/cart/clear/services - clears service cart
        """
        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        # Determine cart type from URL path, header, or param
        path = request.httprequest.path
        if path.endswith("/products"):
            cart_type = "product_cart"
        elif path.endswith("/services"):
            cart_type = "service_cart"
        else:
            # Get from header: check X-Cart-Type first, then 'type' header
            cart_type_header = (
                request.httprequest.headers.get("X-Cart-Type", "").strip().lower()
                or request.httprequest.headers.get("type", "").strip().lower()
            )
            # Then check query params: cart_type, then type
            cart_type_param = (
                kwargs.get("cart_type", "").strip().lower()
                or kwargs.get("type", "").strip().lower()
            )
            cart_type_raw = cart_type_header or cart_type_param or "product"

            # Normalize cart_type to origin format (accept plural forms too)
            if cart_type_raw in ["product", "product_cart", "products"]:
                cart_type = "product_cart"
            elif cart_type_raw in ["service", "service_cart", "services"]:
                cart_type = "service_cart"
            else:
                return _json_err("Invalid cart_type. Use 'product' or 'service'", status=400)

        try:
            SaleOrder = request.env["sale.order"].sudo()
            order = SaleOrder.search([
                ("device_id", "=", device_id),
                ("is_guest_cart", "=", True),
                ("state", "=", "draft"),
                ("origin", "=", cart_type)
            ], limit=1)

            if order:
                order.order_line.unlink()
                return _json_ok("Cart cleared", data=self._format_guest_cart_response(order))

            return _json_ok("No cart found to clear", data={
                "cart_id": None,
                "order_id": None,
                "device_id": device_id,
                "cart_type": cart_type,
                "origin": cart_type,
                "lines": [],
                "items": [],
                "subtotal": 0,
                "amount_untaxed": 0,
                "tax": 0,
                "amount_tax": 0,
                "total": 0,
                "amount_total": 0,
                "item_count": 0,
                "total_items": 0,
                "total_qty": 0,
            })

        except Exception as e:
            _logger.exception("Error clearing guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/guest/cart/sync", type="http", auth="public", methods=["POST"], csrf=False)
    def sync_guest_cart_to_user(self, **kwargs):
        """
        Sync guest cart to authenticated user's cart when they login/register.
        This merges the guest cart into the user's existing cart or transfers ownership.
        Headers:
            Authorization: Bearer <access_token>
            X-Device-ID: <device_id>
        Body (JSON):
            {
                "merge": true  // If true, merge with existing cart. If false, replace.
            }
        """
        # Get authenticated user
        partner, err = _partner_from_token()
        if err:
            return err

        device_id = self._get_device_id()
        if not device_id:
            return _json_err("X-Device-ID header is required", status=400)

        try:
            raw = request.httprequest.data or b"{}"
            body = json.loads(raw.decode("utf-8"))
            merge = body.get("merge", True)

            SaleOrder = request.env["sale.order"].sudo()
            SaleOrderLine = request.env["sale.order.line"].sudo()

            synced_carts = []

            # Process both product and service carts
            for cart_type in ["product_cart", "service_cart"]:
                guest_order = SaleOrder.search([
                    ("device_id", "=", device_id),
                    ("is_guest_cart", "=", True),
                    ("state", "=", "draft"),
                    ("origin", "=", cart_type)
                ], limit=1)

                if not guest_order or not guest_order.order_line:
                    continue

                # Get or create user's cart
                user_order = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "=", cart_type),
                    ("is_guest_cart", "=", False)
                ], limit=1)

                if merge and user_order:
                    # Merge guest cart into user's cart
                    for guest_line in guest_order.order_line:
                        existing_line = user_order.order_line.filtered(
                            lambda l: l.product_id.id == guest_line.product_id.id
                        )
                        if existing_line:
                            existing_line.write({
                                "product_uom_qty": existing_line.product_uom_qty + guest_line.product_uom_qty
                            })
                        else:
                            SaleOrderLine.create({
                                "order_id": user_order.id,
                                "product_id": guest_line.product_id.id,
                                "product_uom_qty": guest_line.product_uom_qty,
                                "price_unit": guest_line.price_unit,
                            })

                    # Delete guest cart after merge
                    guest_order.unlink()
                    synced_carts.append({
                        "cart_type": cart_type,
                        "action": "merged",
                        "cart_id": user_order.id,
                    })
                else:
                    # Transfer ownership of guest cart to user
                    if user_order:
                        # Delete user's existing cart if not merging
                        user_order.unlink()

                    guest_order.write({
                        "partner_id": partner.id,
                        "is_guest_cart": False,
                        "device_id": False,
                    })
                    synced_carts.append({
                        "cart_type": cart_type,
                        "action": "transferred",
                        "cart_id": guest_order.id,
                    })

            if not synced_carts:
                return _json_ok("No guest carts found to sync", data={"synced_carts": []})

            return _json_ok("Guest carts synced successfully", data={"synced_carts": synced_carts})

        except json.JSONDecodeError:
            return _json_err("Invalid JSON payload", status=400)
        except Exception as e:
            _logger.exception("Error syncing guest cart: %s", e)
            return _json_err(str(e), status=500)

    @http.route('/api/cart/validate_by_id', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_cart_id_availability(self, **kwargs):
        """
        التحقق من توفر المنتجات في فرع محدد وتحديث السلة لتخرج من هذا الفرع مع تعيين التوصيل كـ 'استلام من الفرع'.
        يدعم:
        1. المستخدمين المسجلين (عبر الـ Authorization Bearer Token).
        2. الزوار (عبر الـ X-Device-ID).
        """
        # --- 1. التحقق من الهوية باستخدام الدالة المساعدة ---
        partner, device_id, is_guest, err = _partner_or_device()
        if err:
            return err  # هيرجع 401 لو التوكن غلط أو منتهي

        try:
            body = request.dispatcher.jsonrequest
            cart_id = body.get('cart_id')
            branch_id = body.get('branch_id')
            carrier_id = body.get('carrier_id')  # ممكن الفرونت إند يبعته، ولو مبعتوش الباك إند هيتصرف

            if not cart_id or not branch_id:
                return {"status": "error", "message": "Missing cart_id or branch_id"}

            # --- 2. البحث عن السلة بناءً على نوع المستخدم ---
            domain = [('id', '=', int(cart_id)), ('state', '=', 'draft')]

            if is_guest:
                domain += [('device_id', '=', device_id), ('is_guest_cart', '=', True)]
            else:
                domain += [('partner_id', '=', partner.id), ('is_guest_cart', '=', False)]

            order = request.env['sale.order'].sudo().search(domain, limit=1)

            if not order:
                return {"status": "error", "message": "Unauthorized access or Cart not found"}

            # --- 3. تحديد مستودع الفرع المختار ---
            warehouse = request.env['stock.warehouse'].sudo().search([
                ('company_id', '=', int(branch_id))
            ], limit=1)

            if not warehouse:
                return {"status": "error", "message": "Selected branch has no warehouse configured"}

            # --- 4. تحديد طريقة التوصيل (استلام من الفرع) ---
            pickup_carrier = False
            if carrier_id:
                pickup_carrier = request.env['delivery.carrier'].sudo().browse(int(carrier_id))
            else:
                # لو مفيش id مبعوت، الباك إند هيبحث عن طريقة التوصيل بالاسم
                pickup_carrier = request.env['delivery.carrier'].sudo().search([
                    '|', ('name', 'ilike', 'استلام من الفرع'), ('name', 'ilike', 'Pickup')
                ], limit=1)

            # --- 5. تحديث السلة لتسجل على الفرع ومستودعه وطريقة التوصيل وعنوان الاستلام ---
            update_vals = {
                'company_id': int(branch_id),
                'warehouse_id': warehouse.id,
                # السطر السحري: إجبار عنوان الاستلام ليكون هو عنوان المستودع/الفرع
                # 'partner_shipping_id': warehouse.partner_id.id
            }

            if pickup_carrier and pickup_carrier.exists():
                update_vals['carrier_id'] = pickup_carrier.id

            order.sudo().write(update_vals)

            # تحديث تسعيرة التوصيل في السلة (مسح القديم وإضافة استلام من الفرع مجاناً)
            if pickup_carrier and pickup_carrier.exists():
                order.sudo().set_delivery_line(pickup_carrier, 0.0)

            # --- 6. فحص المخزون (بأسلوب الـ add_to_cart) ---
            ctx = {'warehouse': warehouse.id}
            unavailable_items = []

            for line in order.order_line:
                product = line.product_id.sudo().with_context(**ctx)

                # تخطي الخدمات وسطر التوصيل نفسه
                if product.detailed_type == 'service' or getattr(line, 'is_delivery', False):
                    continue

                available_qty = float(product.virtual_available or 0.0)
                requested_qty = line.product_uom_qty

                if requested_qty > available_qty:
                    unavailable_items.append({
                        "line_id": line.id,
                        "product_id": product.product_tmpl_id.id,
                        "variant_id": product.id,
                        "product_name": product.display_name,
                        "available_qty": max(0, available_qty),
                        "requested_qty": requested_qty,
                        "shortage": requested_qty - max(0, available_qty)
                    })

            # --- 7. الرد النهائي ---
            if unavailable_items:
                return {
                    "status": "partial",
                    "message": "Some items are not available in this branch",
                    "data": {
                        "cart_id": order.id,
                        "unavailable_items": unavailable_items
                    }
                }

            return {
                "status": "success",
                "message": "All items are available, cart updated to the selected branch and set for pickup",
                "data": {"cart_id": order.id}
            }

        except Exception as e:
            _logger.exception("Validation failed: %s", str(e))
            return {"status": "error", "message": str(e)}

    @http.route('/api/orders/history', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_order_history(self, **kwargs):
        try:
            # 1. التحقق من الهوية
            auth_header = request.httprequest.headers.get('Authorization')
            header_lang = request.httprequest.headers.get('lang', 'en').lower()
            if not auth_header:
                return request.make_response(json.dumps({"status": "error", "message": "Auth header missing"}),
                                             headers=[('Content-Type', 'application/json')], status=401)

            # افترض إن الـ SECRET_KEY معرف عندك فوق في الملف
            token = auth_header.split(" ")[1] if " " in auth_header else auth_header
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])  # تأكد إن الـ SECRET_KEY موجود
            current_partner_id = payload.get("partner_id")

            status_mapping = {
                'draft': {'key': 'pending', 'ar': 'بانتظار الدفع', 'en': 'Pending Payment'},
                'sent': {'key': 'confirmed', 'ar': 'تم التأكيد', 'en': 'Confirmed'},
                'sale': {'key': 'processing', 'ar': 'جاري التجهيز', 'en': 'Processing'},
                'done': {'key': 'delivered', 'ar': 'تم التوصيل', 'en': 'Delivered'},
                'cancel': {'key': 'cancelled', 'ar': 'ملغي', 'en': 'Cancelled'}
            }

            orders = request.env['sale.order'].sudo().search([
                ('partner_id', '=', current_partner_id),
                ('order_line.product_id.detailed_type', '=', 'product')
            ], order='date_order desc')

            # تعريف المنطقة الزمنية للسعودية
            saudi_tz = pytz.timezone('Asia/Riyadh')

            history = []
            for order in orders:
                # استبعاد سطر التوصيل من الفلترة عشان ميتحسبش في items_count
                storable_lines = order.order_line.filtered(
                    lambda l: l.product_id.detailed_type == 'product' and not getattr(l, 'is_delivery', False)
                )

                if not storable_lines: continue

                # الحالة الافتراضية من أمر البيع
                state_info = status_mapping.get(order.state, {'key': 'unknown', 'ar': 'غير معروف', 'en': 'Unknown'})

                # ====================================================================
                # >>> التعديل السحري لتوحيد الحالة مع إذن التوصيل (التتبع) <<<
                # ====================================================================
                if order.state == 'sale':
                    pickings = order.picking_ids.filtered(lambda x: x.state != 'cancel')
                    if pickings:
                        # لو المخزن سلم الشحنة فعلياً (done)
                        if all(p.state == 'done' for p in pickings):
                            state_info = {'key': 'delivered', 'ar': 'تم التوصيل', 'en': 'Delivered'}
                # ====================================================================

                # --- منطق تحديد نوع التوصيل ---
                delivery_type = "shipping"
                delivery_details = {}

                loc = getattr(order, 'location_id', False)

                if not loc:
                    loc = request.env['res.partner.location'].sudo().search([
                        ('partner_id', '=', order.partner_id.id)
                    ], limit=1, order="id desc")

                is_pickup = False
                branch = order.warehouse_id.partner_id

                # توحيد المنطق مع API التفاصيل
                if order.carrier_id and (
                        'pickup' in order.carrier_id.name.lower() or 'استلام' in order.carrier_id.name):
                    is_pickup = True
                elif hasattr(order, 'branch_id') and order.branch_id:
                    is_pickup = True
                    branch = order.branch_id
                elif order.partner_shipping_id.id == order.warehouse_id.partner_id.id:
                    is_pickup = True

                if is_pickup:
                    delivery_type = "pickup"
                    delivery_details = {
                        "branch_name": branch.name,
                        "address": f"{branch.street or ''} {branch.city or ''}",
                        "latitude": getattr(branch, 'partner_latitude', 0.0),
                        "longitude": getattr(branch, 'partner_longitude', 0.0)
                    }
                else:
                    delivery_type = "shipping"
                    if loc:
                        delivery_details = {
                            "receiver_name": order.partner_id.name,
                            "location_id": loc.id,
                            "label": loc.label or 'Home',
                            "address": loc.address or '',
                            "buildingName": loc.building_name or '',
                            "apartmentNumber": loc.apartment_number or '',
                            "floor": loc.floor or '',
                            "street": loc.street or '',
                            "latitude": loc.latitude or 0.0,
                            "longitude": loc.longitude or 0.0,
                            "additionalInfo": loc.additional_info or '',
                            "phone": order.partner_id.phone or order.partner_id.mobile or ""
                        }
                    else:
                        addr = order.partner_shipping_id
                        delivery_details = {
                            "receiver_name": addr.name or order.partner_id.name,
                            "full_address": f"{addr.street or ''} {addr.city or ''}".strip() or "No Address Provided",
                            "phone": addr.phone or addr.mobile or order.partner_id.mobile or ""
                        }

                # --- التعديل السحري لتحويل الوقت للسعودية ---
                formatted_date = ""
                if order.date_order:
                    utc_dt = pytz.utc.localize(order.date_order)
                    saudi_dt = utc_dt.astimezone(saudi_tz)
                    formatted_date = saudi_dt.strftime('%Y-%m-%d %H:%M:%S')

                history.append({
                    "order_id": order.id,
                    "order_ref": order.name,
                    "date": formatted_date,
                    "total": order.amount_total,
                    "currency": order.currency_id.symbol or "SR",
                    "items_count": len(storable_lines),
                    "status": state_info['key'],
                    "status_display": state_info.get(header_lang, state_info['en']),
                    "delivery_type": delivery_type,
                    "delivery_details": delivery_details
                })

            return request.make_response(json.dumps({"status": "success", "orders": history}, default=str),
                                         headers=[('Content-Type', 'application/json')])

        except Exception as e:
            _logger.error("Order History API Error: %s", str(e))
            return request.make_response(json.dumps({"status": "error", "message": str(e)}),
                                         headers=[('Content-Type', 'application/json')], status=500)
    @http.route('/api/order/track', type='json', auth='public', methods=['POST'], csrf=False)
    def track_order_shipping(self, **kwargs):
        try:
            # 1. فك التوكن واستخراج اللغة من الهيدر
            auth_header = request.httprequest.headers.get('Authorization')
            header_lang = request.httprequest.headers.get('lang', 'en').lower()

            token = auth_header.split(" ")[1] if auth_header and " " in auth_header else auth_header
            payload = jwt.decode(token, "bcf2e5f933a069b6d737d5cc0a7af01b", algorithms=["HS256"])
            current_partner_id = payload.get("partner_id")

            order_id = kwargs.get('order_id')
            order = request.env['sale.order'].sudo().browse(int(order_id))

            if not order.exists() or order.partner_id.id != current_partner_id:
                return {"status": "error", "message": "Unauthorized"}

            # 2. الوصول لبيانات الشحن (Picking)
            picking = order.picking_ids.filtered(lambda x: x.state != 'cancel')[:1]

            # 3. قاموس الحالات المترجم
            status_translations = {
                'en': {
                    'draft': 'Reviewing Order',
                    'waiting': 'Waiting for Products',
                    'confirmed': 'Reserved in Warehouse',
                    'assigned': 'Packing & Preparing',
                    'done': 'Delivered Successfully',
                    'cancel': 'Shipment Cancelled',
                    'internal': 'Internal Delivery',
                    'no_ref': 'Tracking Ref. Pending'
                },
                'ar': {
                    'draft': 'جاري مراجعة الطلب',
                    'waiting': 'بانتظار توفر المنتجات',
                    'confirmed': 'تم تأكيد الحجز في المخزن',
                    'assigned': 'جاري التغليف والتحضير',
                    'done': 'تم التسليم بنجاح',
                    'cancel': 'تم إلغاء الشحنة',
                    'internal': 'شركة شحن داخلية',
                    'no_ref': 'لم يصدر رقم تتبع بعد'
                }
            }

            # اختيار اللغة المناسبة (الافتراضي إنجليزي لو الموبايل مبعتش)
            msg = status_translations.get(header_lang, status_translations['en'])

            return {
                "status": "success",
                "tracking_info": {
                    "order_ref": order.name,
                    "shipping_status": msg.get(picking.state, picking.state or "Processing"),
                    "carrier_name": picking.carrier_id.name or msg['internal'],
                    "tracking_number": picking.carrier_tracking_ref or msg['no_ref'],
                    "tracking_link": picking.carrier_tracking_url or ""
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @http.route('/api/order/details', type='json', auth='public', methods=['POST'], csrf=False)
    def get_order_details(self, **kwargs):
        try:
            # 1. التحقق من الهوية
            auth_header = request.httprequest.headers.get('Authorization')

            # --- 🌐 تظبيط لغة الترجمة ---
            raw_lang = request.httprequest.headers.get('lang', 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            token = auth_header.split(" ")[1] if auth_header and " " in auth_header else auth_header
            payload = jwt.decode(token, "bcf2e5f933a069b6d737d5cc0a7af01b", algorithms=["HS256"])
            current_partner_id = payload.get("partner_id")

            order_id = kwargs.get('order_id')

            # 🚀 إضافة الـ Context هنا عشان الطلب وكل محتوياته (زي المنتجات) تترجم
            order = request.env['sale.order'].sudo().with_context(lang=lang).browse(int(order_id))

            if not order.exists() or order.partner_id.id != current_partner_id:
                return {"status": "error", "message": "Unauthorized"}

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # --- بداية منطق استخراج بيانات التوصيل المحدث (مطابق لـ History) ---
            # 1. محاولة جلب اللوكيشن المربوط أو البحث عنه
            loc = getattr(order, 'location_id', False)
            if not loc:
                loc = request.env['res.partner.location'].sudo().search([
                    ('partner_id', '=', order.partner_id.id)
                ], limit=1, order="id desc")

            # 2. فحص هل الطلب "استلام من الفرع" (Pickup)
            is_pickup = False
            branch = order.warehouse_id.partner_id

            # التعديل الجوهري: فحص طريقة التوصيل (carrier_id)
            if order.carrier_id and ('pickup' in order.carrier_id.name.lower() or 'استلام' in order.carrier_id.name):
                is_pickup = True
            elif hasattr(order, 'branch_id') and order.branch_id:
                is_pickup = True
                branch = order.branch_id
            elif order.partner_shipping_id.id == order.warehouse_id.partner_id.id:
                is_pickup = True

            delivery_details = {}

            if is_pickup:
                # حالة الاستلام من الفرع (بنفس شكل History)
                delivery_details = {
                    "delivery_type": "pickup",
                    "branch_name": branch.name,
                    "address": f"{branch.street or ''} {branch.city or ''}".strip(),
                    "latitude": getattr(branch, 'partner_latitude', 0.0),
                    "longitude": getattr(branch, 'partner_longitude', 0.0)
                }
            else:
                # حالة الشحن (بنفس شكل History)
                if loc:
                    delivery_details = {
                        "delivery_type": "shipping",
                        "receiver_name": order.partner_id.name,
                        "location_id": loc.id,
                        "label": loc.label or 'Home',
                        "address": loc.address or '',
                        "buildingName": loc.building_name or '',
                        "apartmentNumber": loc.apartment_number or '',
                        "floor": loc.floor or '',
                        "street": loc.street or '',
                        "latitude": loc.latitude or 0.0,
                        "longitude": loc.longitude or 0.0,
                        "additionalInfo": loc.additional_info or '',
                        "phone": order.partner_id.phone or order.partner_id.mobile or ""
                    }
                else:
                    addr = order.partner_shipping_id
                    delivery_details = {
                        "delivery_type": "shipping",
                        "receiver_name": addr.name or order.partner_id.name,
                        "full_address": f"{addr.street or ''} {addr.city or ''}".strip() or "No Address Provided",
                        "phone": addr.phone or addr.mobile or order.partner_id.mobile or ""
                    }
            # --- نهاية منطق بيانات التوصيل ---

            # 3. تجميع بنود الطلب
            lines = []
            total_discount_amount = 0.0

            for line in order.order_line:
                # >>> تخطي سطر التوصيل تماماً من الظهور كمنتج <<<
                if getattr(line, 'is_delivery', False):
                    continue

                # 🔥 التعديل الجديد: تخطي سطور الخصومات والكوبونات من الظهور كمنتج وحساب قيمتها
                if getattr(line, 'is_reward_line', False) or line.price_subtotal < 0:
                    total_discount_amount += abs(line.price_subtotal)
                    continue

                # 🚀 إضافة Context للمنتج صراحةً لضمان الترجمة
                product = line.product_id.with_context(lang=lang)
                image_public_url = f"{base_url}/api/public/image/product.template/{product.product_tmpl_id.id}/image_1920"
                lines.append({
                    "product_id": product.id,
                    "product_name": product.name,  # ✅ هنا هيرجع مترجم
                    "quantity": line.product_uom_qty,
                    "price_unit": line.price_unit,
                    "subtotal": line.price_subtotal,
                    "image_url": image_public_url
                })

            # 4. تحويل وقت الطلب لتوقيت السعودية
            formatted_date = ""
            if order.date_order:
                import pytz
                saudi_tz = pytz.timezone('Asia/Riyadh')
                utc_dt = pytz.utc.localize(order.date_order)
                saudi_dt = utc_dt.astimezone(saudi_tz)
                formatted_date = saudi_dt.strftime('%Y-%m-%d %H:%M:%S')

            return {
                "status": "success",
                "order_details": {
                    "id": order.id,
                    "ref": order.name,
                    "date": formatted_date,
                    "total": order.amount_total,
                    "tax": order.amount_tax,
                    "discount_amount": round(total_discount_amount, 2),  # ✅ تم إضافة إجمالي الخصم هنا
                    "currency": order.currency_id.symbol or "SR",
                    "delivery_details": delivery_details,
                    "items": lines
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @http.route('/api/v1/checkout/free_confirm', type='http', auth='public', methods=['POST'], csrf=False, cors='*')
    def free_checkout_confirm(self, **kwargs):
        partner, device_id, is_guest, error_response = _partner_or_device()
        if error_response: return error_response

        try:
            body = json.loads(request.httprequest.data.decode("utf-8"))
            order_id = body.get('order_id')

            if not order_id:
                return _json_err("Missing order_id", status=400)

            order = request.env['sale.order'].sudo().browse(int(order_id))

            # 1. التأكد من وجود الأوردر وملكيته
            if not order.exists() or (order.partner_id.id != partner.id and not is_guest):
                return _json_err("Order not found or Access Denied", status=403)

            # 2. التأكد إن الأوردر لسه Draft عشان منأكدوش مرتين
            if order.state != 'draft':
                return _json_err("Order is already confirmed or cancelled.", status=400)

            # 3. التأكد من أحدث الأسعار قبل التأكيد
            order.sudo()._update_programs_and_rewards()

            # 4. === صمام الأمان الأساسي ===
            # لازم نضمن إن الإجمالي فعلاً صفر أو أقل، عشان اليوزر ميهربش من الدفع
            if order.amount_total > 0:
                return _json_err(
                    f"Cannot confirm for free. Order total is {order.amount_total} {order.currency_id.name}. Payment required.",
                    status=400
                )

            # 5. تأكيد الطلب (تحويله من Draft لـ Sale Order)
            order.sudo().action_confirm()

            return _json_ok(data={
                'order_id': order.id,
                'state': order.state,
                'total_amount': order.amount_total,
            }, message="Order confirmed successfully for free.")

        except Exception as e:
            import traceback
            _logger.error(traceback.format_exc())
            return _json_err(f"Technical Error: {str(e)}", status=500)

    @http.route("/api/product/notify_restock", type="http", auth="public", methods=["POST", "OPTIONS"], csrf=False)
    def notify_restock(self, **kwargs):
        headers = [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*')]
        if request.httprequest.method == 'OPTIONS':
            return request.make_response("", headers=headers)

        is_ar = request.httprequest.headers.get('lang', 'en').lower() in ['ar', 'ar_001']

        try:
            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            product_id = payload.get("product_id")
            is_notify = payload.get("is_notify", False)
            email_from_body = payload.get("email")

            if not product_id:
                return _json_err("رقم المنتج مفقود" if is_ar else "Missing product_id", status=400)

            # 1. محاولة جلب العميل من التوكن (بأمان تام بدون ما نكسر الدالة لو مفيش توكن)
            partner = None
            auth_header = request.httprequest.headers.get("Authorization") or ""
            if auth_header.startswith("Bearer "):
                p, err = _partner_from_token()
                if not err:  # التوكن سليم
                    partner = p

            # 2. استخراج الإيميل النهائي (من حساب العميل لو مسجل، أو من الـ Body لو ضيف)
            final_email = email_from_body
            if partner and not final_email:
                final_email = partner.email

            if not final_email:
                return _json_err(
                    "البريد الإلكتروني مطلوب لتفعيل الإشعار" if is_ar else "Email is required to enable notifications",
                    status=400)

            # 3. تسجيل الإشعار
            if is_notify:
                # منع التكرار لو العميل طلب إشعار لنفس المنتج ومتبعتش لسه
                existing = request.env['product.stock.notification'].sudo().search([
                    ('email', '=', final_email),
                    ('product_id', '=', int(product_id)),
                    ('is_notified', '=', False)
                ], limit=1)

                if not existing:
                    request.env['product.stock.notification'].sudo().create({
                        'partner_id': partner.id if partner else False,
                        'email': final_email,
                        'product_id': int(product_id)
                    })

                msg = "تم تسجيل طلبك، سنعلمك فور توفر المنتج" if is_ar else "We will notify you as soon as the product is back in stock"
                return _json_ok(msg)

            # لو الموبايل بعت is_notify = False
            return _json_ok("تم إلغاء طلب الإشعار" if is_ar else "Notification request ignored")

        except Exception as e:
            _logger.exception("Error in notify_restock API")
            return _json_err("حدث خطأ داخلي: " + str(e) if is_ar else str(e), status=500)