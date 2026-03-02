from odoo import http,fields
from odoo.http import request, Response
import jwt
import logging
import json
from datetime import datetime
import base64

from .api import _json_ok, _json_err
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"

_logger = logging.getLogger(__name__)


def _partner_from_token():
    auth_header = request.httprequest.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None, _json_err("Authorization Bearer token is required", status=401)

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        partner_id = payload.get("partner_id")
        if not partner_id:
            return None, _json_err("Invalid token payload", status=401)

        partner = request.env["res.partner"].sudo().browse(partner_id)
        if not partner.exists():
            return None, _json_err("Partner not found", status=404)

        return partner, None

    except jwt.ExpiredSignatureError:
        return None, _json_err("Token has expired", status=401)
    except jwt.InvalidTokenError:
        return None, _json_err("Invalid token", status=401)
    except Exception as e:
        _logger.exception("Token decode error: %s", e)
        return None, _json_err(str(e), status=400)



class CartApiController(http.Controller):



    @http.route("/api/cart/add/product", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_cart_product(self, **kwargs):
        """
        Add storable products to authenticated user's product cart (draft Sale Order).
        Headers:
            Authorization: Bearer <access_token>
        Body (JSON):
            {
                "products": [
                    {"product_id": 123, "qty": 2},
                    {"product_id": 456, "qty": 1}
                ]
            }
        Response: Same structure as /api/cart
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return _json_err("Invalid JSON payload", status=400)

            products = body.get("products", [])
            if not products:
                return _json_err("No products provided", status=400)

            SaleOrder = request.env["sale.order"].sudo()
            SaleOrderLine = request.env["sale.order.line"].sudo()

            order = SaleOrder.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "draft"),
                ("origin", "=", "product_cart")
            ], limit=1)

            if not order:
                order = SaleOrder.create({
                    "partner_id": partner.id,
                    "state": "draft",
                    "origin": "product_cart",
                })
                _logger.info(f"Created new product cart for partner {partner.id}")



            for item in products:
                template_id = item.get("product_id")
                qty = float(item.get("qty", 1))

                if not template_id or qty <= 0:
                    continue

                product_template = request.env["product.template"].sudo().browse(template_id)
                if not product_template.exists() or product_template.type != 'product':
                    continue

                product = product_template.product_variant_ids[:1]
                if not product:
                    continue

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

                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)

                price_unit = (
                    product_template.price_after_discount
                    if getattr(product_template, "price_after_discount", 0) > 0
                    else product.lst_price
                )

                if existing_line:
                    new_qty = existing_line.product_uom_qty + qty
                    if new_qty > available_qty:
                        return _json_err(
                            f"Cannot add {qty} more units. Only {available_qty - existing_line.product_uom_qty} units available.",
                            data={
                                "product_id": product.id,
                                "product_name": product.display_name,
                                "available_qty": available_qty,
                                "existing_qty": existing_line.product_uom_qty,
                                "requested_additional_qty": qty,
                            },
                            status=400
                        )
                    existing_line.product_uom_qty = new_qty
                    existing_line.price_unit = price_unit
                    _logger.info(
                        f"Updated quantity and price for product {product.id} to {new_qty}, price={price_unit}")
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price_unit,
                        "name": product.display_name,
                    })
                    _logger.info(f"Added new product {product.id} (qty={qty}, price={price_unit}) to cart")

            order.message_post(body=f"Product cart updated via API at {datetime.now()}")

            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            cart_items = []

            for line in order.order_line.sudo():
                product_tmpl = line.product_template_id.sudo()

                main_image_url = (
                    f"{base_url}/api/image/product.template/{product_tmpl.id}/image_1920"
                    if product_tmpl.image_1920 else None
                )
                gallery_urls = []
                if hasattr(product_tmpl, 'img_ids'):
                    for img in product_tmpl.img_ids.sudo():
                        if img.img:
                            gallery_urls.append(
                                f"{base_url}/api/image/product.template.img/{img.id}/img"
                            )

                cart_items.append({
                    "product_id": product_tmpl.id,
                    "name": product_tmpl.display_name,
                    "qty": line.product_uom_qty,
                    "price_unit": line.price_unit,
                    "total_price": line.price_subtotal,

                    "description": product_tmpl.description,
                    "detailed_type": product_tmpl.detailed_type,
                    "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
                    "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
                    "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
                    "barcode": product_tmpl.barcode,
                    "avg_rating": product_tmpl.avg_rating,
                    "top": product_tmpl.top,

                    "main_image_url": main_image_url,
                    "gallery_urls": gallery_urls,

                    "ar_name": product_tmpl.ar_name,
                    "ar_description": product_tmpl.ar_description,
                })

            return _json_ok(
                "Cart updated successfully",
                data={
                    "order_id": order.id,
                    "partner_id": partner.id,
                    "items": cart_items,
                    "total_items": len(cart_items),
                    "total_amount": order.amount_total,
                },
                status=200
            )

        except Exception as e:
            _logger.exception("add_to_cart_product error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/add/service", type="http", auth="public", methods=["POST"], csrf=False)
    def add_to_cart_service(self, **kwargs):
        """
        Add 'service' or 'combo' products to authenticated user's service cart (draft Sale Order).
        Quantity is always set to 1.
        Headers:
            Authorization: Bearer <access_token>
        Body (JSON):
        {
            "products": [
                {"product_id": 123}
            ]
        }
        Response: Same structure as /api/cart/add/product
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                return _json_err("Invalid JSON payload", status=400)

            products = body.get("products", [])
            if not products:
                return _json_err("No products provided", status=400)

            SaleOrder = request.env["sale.order"].sudo()
            SaleOrderLine = request.env["sale.order.line"].sudo()

            order = SaleOrder.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "draft"),
                ("origin", "=", "service_cart")
            ], limit=1)

            if not order:
                order = SaleOrder.create({
                    "partner_id": partner.id,
                    "state": "draft",
                    "origin": "service_cart",
                })
                _logger.info(f"Created new service cart for partner {partner.id}")

            for item in products:
                template_id = item.get("product_id")

                if not template_id:
                    continue

                product_template = request.env["product.template"].sudo().browse(template_id)
                if not product_template.exists():
                    _logger.warning(f"Product template not found: {template_id}")
                    continue

                if product_template.type not in ("service", "combo"):
                    _logger.warning(f"Product {template_id} skipped (type={product_template.type})")
                    continue

                product = product_template.product_variant_ids[:1] or product_template
                qty = 1

                existing_line = order.order_line.filtered(lambda l: l.product_id.id == product.id)
                if existing_line:
                    existing_line.product_uom_qty = qty
                    _logger.info(f"Updated {product_template.type} {product.id} quantity to {qty}")
                else:
                    SaleOrderLine.create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": product.lst_price,
                        "name": product.display_name,
                    })
                    _logger.info(f"Added new {product_template.type} {product.id} to cart")

            order.message_post(body=f"Service/Combo cart updated via API at {datetime.now()}")

            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
            cart_items = []

            for line in order.order_line.sudo():
                product_tmpl = line.product_template_id.sudo()

                main_image_url = (
                    f"{base_url}/api/image/product.template/{product_tmpl.id}/image_1920"
                    if product_tmpl.image_1920 else None
                )
                gallery_urls = []
                if hasattr(product_tmpl, "img_ids"):
                    for img in product_tmpl.img_ids.sudo():
                        if img.img:
                            gallery_urls.append(
                                f"{base_url}/api/image/product.template.img/{img.id}/img"
                            )

                cart_items.append({
                    "product_id": product_tmpl.id,
                    "name": product_tmpl.display_name,
                    "qty": line.product_uom_qty,
                    "price_unit": line.price_unit,
                    "total_price": line.price_subtotal,
                    "description": product_tmpl.description,
                    "detailed_type": product_tmpl.detailed_type,
                    "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
                    "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
                    "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
                    "barcode": product_tmpl.barcode,
                    "avg_rating": product_tmpl.avg_rating,
                    "top": product_tmpl.top,
                    "main_image_url": main_image_url,
                    "gallery_urls": gallery_urls,
                    "ar_name": product_tmpl.ar_name,
                    "ar_description": product_tmpl.ar_description,
                })

            return _json_ok(
                "Service/Combo cart updated successfully",
                data={
                    "order_id": order.id,
                    "partner_id": partner.id,
                    "items": cart_items,
                    "total_items": len(cart_items),
                    "total_amount": order.amount_total,
                },
                status=200
            )

        except Exception as e:
            _logger.exception("add_to_cart_service error: %s", e)
            return _json_err(str(e), status=500)

    @http.route("/api/cart/remove/<int:template_id>", type="http", auth="public", methods=["DELETE"], csrf=False)
    def remove_cart_item(self, template_id, **kwargs):
        """
        Remove a specific product/service (by template_id) from all of the user's active draft carts.
        Headers:
            Authorization: Bearer <access_token>
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            orders = SaleOrder.search([
                ("partner_id", "=", partner.id),
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



    @http.route(
        ["/api/cart", "/api/cart/<int:order_id>"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False
    )
    def get_cart(self, order_id=None, **kwargs):
        """
        Get one or multiple draft carts for the authenticated user.
        Headers:
            Authorization: Bearer <access_token>
            X-Cart-Type: "product" or "service"
        URL:
            /api/cart                     → Get all draft carts
            /api/cart/<order_id>          → Get one specific cart by ID
            /api/cart?ids=7,6             → Get multiple carts by ID list
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()
            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")

            cart_type = request.httprequest.headers.get("X-Cart-Type", "").lower()

            origin_filter = []
            if cart_type == "product":
                origin_filter = ["product_cart"]
            elif cart_type == "service":
                origin_filter = ["service_cart"]
            else:
                origin_filter = ["product_cart", "service_cart"]

            ids_param = kwargs.get("ids")
            if ids_param:
                try:
                    order_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip().isdigit()]
                except Exception:
                    return _json_err("Invalid ids parameter format. Use comma-separated integers.", status=400)
            else:
                order_ids = []

            if order_id:
                orders = SaleOrder.browse([order_id])
            elif order_ids:
                orders = SaleOrder.browse(order_ids)
            else:
                orders = SaleOrder.search([
                    ("partner_id", "=", partner.id),
                    ("state", "=", "draft"),
                    ("origin", "in", origin_filter),
                ])

            orders = orders.exists().filtered(lambda o: o.partner_id.id == partner.id and o.state == "draft")

            if not orders:
                return _json_err("No draft carts found", status=404)

            def _build_cart_data(order):
                cart_items = []
                total_discount = 0

                for line in order.order_line.sudo():
                    product_tmpl = line.product_template_id.sudo()

                    if not product_tmpl.is_appointment_service and product_tmpl.detailed_type == "service":
                        total_discount += line.price_unit * line.product_uom_qty
                        continue

                    main_image_url = (
                        f"{base_url}/api/image/product.template/{product_tmpl.id}/image_1920"
                        if product_tmpl.image_1920 else None
                    )

                    gallery_urls = []
                    if hasattr(product_tmpl, "img_ids"):
                        for img in product_tmpl.img_ids.sudo():
                            if img.img:
                                gallery_urls.append(
                                    f"{base_url}/api/image/product.template.img/{img.id}/img"
                                )

                    # cart_items.append({
                    #     "product_variant": line.product_id.id,
                    #     "product_id": product_tmpl.id,
                    #     "name": product_tmpl.display_name,
                    #     "qty": line.product_uom_qty,
                    #     "is_scheduled": line.is_scheduled,
                    #     "price_unit": line.price_unit,
                    #     "total_price": line.price_subtotal,
                    #     "tax_amount": sum(line.tax_id.sudo().mapped("amount")),
                    #     "description": product_tmpl.description,
                    #     "detailed_type": product_tmpl.detailed_type,
                    #     "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
                    #     "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
                    #     "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
                    #     "barcode": product_tmpl.barcode,
                    #     "avg_rating": product_tmpl.avg_rating,
                    #     "top": product_tmpl.top,
                    #     "main_image_url": main_image_url,
                    #     "gallery_urls": gallery_urls,
                    #     "ar_name": product_tmpl.ar_name,
                    #     "ar_description": product_tmpl.ar_description,
                    # })

                    # --- Appointment service lines (for services only) ---
                    appointment_lines_data = []
                    if product_tmpl.detailed_type == "service":
                        for al in line.product_id.appointment_package_line_ids.sudo():
                            appointment_lines_data.append({
                                "package_line_id": al.id,
                                "product_id": al.product_id.id,
                                "name": al.product_id.name,
                                "branch_id": al.branch_id.id,
                                "department_id": al.department_id.id,
                                "service_slot_inside": al.service_slot_inside,
                                "service_slot_outside": al.service_slot_outside,
                                "service_price_inside": al.service_price_inside,
                                "service_price_outside": al.service_price_outside,
                                "currency_id": al.currency_id.id,
                            })

                    cart_items.append({
                        "product_variant": line.product_id.id,
                        "product_id": product_tmpl.id,
                        "name": product_tmpl.display_name,
                        "qty": line.product_uom_qty,
                        "is_scheduled": line.is_scheduled,
                        "price_unit": line.price_unit,
                        "total_price": line.price_subtotal,
                        "tax_amount": sum(line.tax_id.sudo().mapped("amount")),
                        "description": product_tmpl.description,
                        "detailed_type": product_tmpl.detailed_type,
                        "category": product_tmpl.categ_id.display_name if product_tmpl.categ_id else None,
                        "currency": product_tmpl.currency_id.name if product_tmpl.currency_id else None,
                        "uom": product_tmpl.uom_id.name if product_tmpl.uom_id else None,
                        "barcode": product_tmpl.barcode,
                        "avg_rating": product_tmpl.avg_rating,
                        "top": product_tmpl.top,
                        "main_image_url": main_image_url,
                        "gallery_urls": gallery_urls,
                        "ar_name": product_tmpl.ar_name,
                        "ar_description": product_tmpl.ar_description,
                        "appointment_lines": appointment_lines_data,
                    })

                return {
                    "order_id": order.id,
                    "origin": order.origin,
                    "state": order.state,
                    "partner_id": order.partner_id.id,
                    "items": cart_items,
                    "total_items": len(cart_items),
                    "amount_untaxed": order.amount_untaxed,
                    "amount_tax": order.amount_tax,
                    "amount_total": order.amount_total,
                    "discount": total_discount,
                }

            carts_data = [_build_cart_data(order) for order in orders]

            if not carts_data:
                return _json_err("No items found for this type", status=404)

            return _json_ok(
                "Carts fetched successfully",
                data={"count": len(carts_data), "orders": carts_data},
                status=200,
            )

        except Exception as e:
            _logger.exception("get_cart error: %s", e)
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
            discount_amount = round((subtotal_before_discount * discount_percentage) / 100, 2)

            discount_line = request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': discount_product.id,
                'name': f"{reward.description or 'Discount'} ({discount_percentage}% Off)",
                'product_uom_qty': 1,
                'tax_id': [(6, 0, [])],
            })

            discount_line.sudo().write({'price_unit': -abs(discount_amount)})

            sale_order._compute_amounts()

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
            discount_amount = round((subtotal_before_discount * discount_percentage) / 100, 2)

            discount_line = request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': discount_product.id,
                'name': f"{reward.description or 'Discount'} ({discount_percentage}% Off)",
                'product_uom_qty': 1,
                'tax_id': [(6, 0, [])],
            })

            discount_line.sudo().write({'price_unit': -abs(discount_amount)})

            sale_order._compute_amounts()

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

    @http.route("/api/cart/clear/products", type="http", auth="public", methods=["DELETE"], csrf=False)
    def clear_product_cart_lines(self, **kwargs):
        """
        Clear all product lines (product type) from all draft PRODUCT carts for the authenticated user.
        Headers:
            Authorization: Bearer <access_token>
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            product_orders = SaleOrder.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "draft"),
                ("origin", "=", "product_cart")
            ])

            if not product_orders:
                return _json_err("No draft PRODUCT carts found", status=404)

            total_lines_removed = 0
            cleared_orders = []

            for order in product_orders:
                product_lines = order.order_line.filtered(lambda l: l.product_id.detailed_type == "product")
                total_lines_removed += len(product_lines)
                if product_lines:
                    product_lines.unlink()
                    order.message_post(body=f"All product lines cleared via API at {datetime.now()}")
                    cleared_orders.append(order.id)

            return _json_ok(
                "Product lines cleared successfully",
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

    @http.route("/api/cart/clear/services", type="http", auth="public", methods=["DELETE"], csrf=False)
    def clear_service_cart_lines(self, **kwargs):
        """
        Clear all service or combo lines from all draft SERVICE carts for the authenticated user.
        Headers:
            Authorization: Bearer <access_token>
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            SaleOrder = request.env["sale.order"].sudo()

            service_orders = SaleOrder.search([
                ("partner_id", "=", partner.id),
                ("state", "=", "draft"),
                ("origin", "=", "service_cart")
            ])

            if not service_orders:
                return _json_err("No draft SERVICE carts found", status=404)

            total_lines_removed = 0
            cleared_orders = []

            for order in service_orders:
                service_lines = order.order_line.filtered(lambda l: l.product_id.detailed_type in ["service", "combo"])
                total_lines_removed += len(service_lines)
                if service_lines:
                    service_lines.unlink()
                    order.message_post(body=f"All service/combo lines cleared via API at {datetime.now()}")
                    cleared_orders.append(order.id)

            return _json_ok(
                "Service lines cleared successfully",
                data={
                    "cleared_orders": cleared_orders,
                    "total_orders": len(cleared_orders),
                    "total_lines_removed": total_lines_removed
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





