from odoo import http
from odoo.http import request, Response
from datetime import datetime, timedelta
import json, jwt, logging
import base64

_logger = logging.getLogger(__name__)
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"


def _json_ok(msg, data=None, status=200):
    return Response(json.dumps({"status": "success", "message": msg, "data": data or {}}),
                    status=status, content_type="application/json")


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


class PosOrderApiController(http.Controller):

    @http.route("/api/pos/order", type="http", auth="public", methods=["POST"], csrf=False)
    def create_pos_order(self, **kwargs):
        """
        Create POS order (with appointment support) via API.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw = request.httprequest.data or b"{}"
            payload = json.loads(raw.decode("utf-8"))

            config_id = payload.get("config_id")
            lines = payload.get("lines", [])
            statements = payload.get("statement_ids", [])
            amount_paid = float(payload.get("amount_paid", 0.0))
            to_invoice = bool(payload.get("to_invoice", False))

            if not config_id:
                return _json_err("config_id is required")
            if not lines:
                return _json_err("Order lines are required")

            PosOrder = request.env["pos.order"].sudo()
            PosPayment = request.env["pos.payment"].sudo()
            PosSession = request.env["pos.session"].sudo()

            session = PosSession.search([
                ("config_id", "=", config_id),
                ("state", "=", "opened")
            ], limit=1)
            if not session:
                return _json_err("No open POS session found for this config")

            order_lines = []
            total = 0.0
            for l in lines:
                product = request.env["product.product"].sudo().browse(l.get("product_id"))
                if not product.exists():
                    _logger.warning(f"⚠️ Product not found: {l.get('product_id')}")
                    continue

                qty = float(l.get("qty", 1.0))
                price_unit = float(l.get("price_unit", product.list_price))
                discount = float(l.get("discount", 0.0))
                subtotal = (price_unit * qty) * (1 - discount / 100)
                total += subtotal

                full_name = (
                    f"Appointment: {l.get('appointment_type', '')} | "
                    f"Employee: {l.get('employee_name', '')} | "
                    f"Branch: {l.get('branch_name', '')} | "
                    f"Slot: {l.get('slot_name', '')} | "
                    f"Date: {l.get('date', '')}"
                )

                order_lines.append((0, 0, {
                    "product_id": product.id,
                    "qty": qty,
                    "price_unit": price_unit,
                    "discount": discount,
                    "price_subtotal": subtotal,
                    "price_subtotal_incl": subtotal,
                    "full_product_name": full_name,
                    "name": f"Shop/{datetime.now().strftime('%H%M%S')}",
                }))

            order_vals = {
                "partner_id": partner.id,
                "session_id": session.id,
                "to_invoice": to_invoice,
                "amount_paid": amount_paid,
                "amount_total": total,
                "amount_return": 0.0,
                "lines": order_lines,
            }

            order = PosOrder.create(order_vals)

            # Recompute taxes and amounts properly
            if hasattr(order, "_recompute_dynamic_lines"):
                order._recompute_dynamic_lines(recompute_all_taxes=True)
            elif hasattr(order, "_compute_amount_all"):
                order._compute_amount_all()

            # Calculate actual tax from order lines
            computed_tax = sum(line.price_subtotal_incl - line.price_subtotal for line in order.lines)
            order.amount_tax = computed_tax
            order.amount_paid = amount_paid
            order.amount_total = order.amount_untaxed + computed_tax if hasattr(order, 'amount_untaxed') else total

            total_payment = 0.0
            for s in statements:
                payment_method = request.env["pos.payment.method"].sudo().browse(s.get("payment_method_id"))
                if not payment_method.exists():
                    _logger.warning(f"⚠️ Invalid payment method: {s.get('payment_method_id')}")
                    continue
                amt = float(s.get("amount", 0.0))
                total_payment += amt
                PosPayment.create({
                    "pos_order_id": order.id,
                    "amount": amt,
                    "payment_method_id": payment_method.id,
                    "session_id": session.id,
                })

            # Determine if order is fully paid
            is_paid = abs(total_payment - total) < 0.01

            if is_paid:
                order.amount_paid = total_payment
                order.action_pos_order_paid()
                order.state = 'paid'

            request.env.cr.flush()
            request.env.invalidate_all()

            Appointment = request.env["appointment.management"].sudo()

            for line in lines:
                if not line.get("is_appointment_line"):
                    continue

                product = request.env["product.product"].sudo().browse(line.get("product_id") or 0)
                if not product.exists():
                    _logger.warning(f"Skipping — product not found for line {line}")
                    continue

                employee = request.env["hr.employee"].sudo().browse(line.get("employee_id") or 0)
                if not employee.exists() and line.get("employee_name"):
                    employee = request.env["hr.employee"].sudo().search([
                        ("name", "ilike", line["employee_name"])
                    ], limit=1)

                branch = request.env["res.company"].sudo().browse(line.get("branch_id") or 0)
                if not branch.exists() and line.get("branch_name"):
                    branch = request.env["res.company"].sudo().search([
                        ("name", "ilike", line["branch_name"])
                    ], limit=1)

                _logger.warning(
                    f"[DEBUG] product.exists={product.exists()} id={product.id}, "
                    f"employee.exists={employee.exists()} id={employee.id}, "
                    f"branch.exists={branch.exists()} id={branch.id}"
                )

                if not (product.exists() and employee.exists() and branch.exists()):
                    _logger.warning(
                        f"Skipping appointment creation — missing one of product/employee/branch for {line}")
                    continue

                appointment_vals = {
                    "partner_id": partner.id,
                    "product_id": product.id,
                    "employee_id": employee.id,
                    "branch_id": branch.id,
                    "appointment_type": line.get("appointment_type", "inside"),
                    "date": line.get("date") or datetime.now(),
                    "price_unit": line.get("price_unit", 0.0),
                    "notes": f"Slot: {line.get('slot_name', '')}",
                    "state": "2" if is_paid else "1",  # "2" = approved/paid, "1" = partial approved/unpaid
                }

                appointment = Appointment.create(appointment_vals)
                _logger.info(f"✅ Appointment created: {appointment.sequence} for order {order.name} with state {'paid' if is_paid else 'unpaid'}")

                # Update is_scheduled flag on sale order line if exists
                SaleOrderLine = request.env["sale.order.line"].sudo().search([
                    ("order_partner_id", "=", partner.id),
                    ("product_id", "=", product.id),
                    ("is_scheduled", "=", False),
                ], limit=1, order="id desc")

                if SaleOrderLine:
                    SaleOrderLine.write({"is_scheduled": True})
                    _logger.info(f"✅ Updated sale order line {SaleOrderLine.id} is_scheduled to True for product {product.id}")

            _logger.info(f"✅ POS Order {order.name or order.id} created successfully with appointments")

            return _json_ok("POS order created successfully", {
                "order_id": order.id,
                "session_id": session.id,
                "partner_id": partner.id,
                "amount_total": order.amount_total,
                "amount_paid": order.amount_paid,
                "state": order.state,
            })

        except Exception as e:
            _logger.exception("POS Order API Error")
            return _json_err(str(e), 500)

    @http.route("/api/branches", type="http", auth="public", methods=["GET"], csrf=False)
    def get_branches(self, **kwargs):
        """
        Get all branches (companies) with location and contact details, excluding the main company.
        """
        try:
            Company = request.env["res.company"].sudo()

            # التعديل هنا: بنبحث عن الشركات اللي ليها شركة أم (يعني فروع)
            companies = Company.search([('parent_id', '!=', False)])

            data = []
            for company in companies:
                address = ", ".join(filter(None, [
                    company.street,
                    company.street2,
                    company.city,
                    company.state_id.name if company.state_id else "",
                    company.country_id.name if company.country_id else "",
                ]))

                data.append({
                    "id": company.id,
                    "name": company.name,
                    "address": address,
                    "phone": company.phone,
                    "mobile": company.mobile,
                    "email": company.email,
                    "latitude": company.partner_latitude,
                    "longitude": company.partner_longitude,
                    "work_time_from": company.work_time_from,
                    "work_time_to": company.work_time_to,
                })

            return _json_ok("Branches fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching branches")
            return _json_err(str(e), 500)
    @http.route("/api/appointment/available_employees", type="http", auth="public", methods=["GET"], csrf=False)
    def get_available_employees(self, **kwargs):
        try:
            # 1. استلام البيانات واللغة
            header_lang = request.httprequest.headers.get('lang', 'en').lower()
            lang = 'ar_001' if header_lang == 'ar' else 'en_US'

            product_id = kwargs.get("product_id")
            date_str = kwargs.get("date")
            branch_id = kwargs.get("branch_id")

            if not product_id or not date_str:
                return self._json_response({"status": "error", "message": "Missing product_id or date"})

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                return self._json_response({"status": "error", "message": "Invalid date format"})

            # 2. جلب الموظفين المرتبطين بالمنتج (Product -> Plans -> Department)
            product = request.env["product.product"].sudo().browse(int(product_id))
            if not product.exists():
                return self._json_response({"status": "error", "message": "Product not found"})

            departments = product.plan_ids.mapped("department_id")

            emp_domain = [("department_id", "in", departments.ids), ("active", "=", True)]
            if branch_id:
                emp_domain.append(("company_id", "=", int(branch_id)))

            employees = request.env["hr.employee"].sudo().with_context(lang=lang).search(emp_domain)

            # 3. جلب الـ Slots المتاحة (بناءً على الحقول الحقيقية في الداتابيز)
            SlotModel = request.env["appointment.employee.slot"].sudo()

            # ملحوظة: استخدمنا حقل 'state' للتأكد إن الموعد متاح (لو السيستم بيستخدمه كدة)
            slots = SlotModel.search([
                ("employee_id", "in", employees.ids),
                ("date", "=", date_obj)
            ])

            if not slots:
                return self._json_response({"status": "success", "data": []})

            # 4. تجميع البيانات للموبايل
            data = []
            active_emps = slots.mapped('employee_id')

            for emp in active_emps:
                emp_slots = slots.filtered(lambda s: s.employee_id.id == emp.id)

                available_times = []
                for s in emp_slots:
                    # استخدمنا الحقل 'time' اللي ظهر في الـ SQL
                    available_times.append({
                        "slot_id": s.id,
                        "start_time": s.time,  # الحقل الحقيقي من الداتابيز
                        "status": s.state or "available"
                    })

                data.append({
                    "id": emp.id,
                    "name": emp.name,
                    "job_title": emp.job_title or "",
                    "department": emp.department_id.name if emp.department_id else "",
                    "image_url": f"/api/public/image/hr.employee/{emp.id}/image_1920",
                    "available_times": available_times
                })

            return self._json_response({
                "status": "success",
                "data": data
            })

        except Exception as e:
            return self._json_response({"status": "error", "message": str(e)})

    def _json_response(self, data):
        return request.make_response(
            json.dumps(data, default=str),
            headers=[('Content-Type', 'application/json')]
        )

    def _json_response(self, data):
        return request.make_response(json.dumps(data, default=str), headers=[('Content-Type', 'application/json')])

    def _json_response(self, data):
        return request.make_response(json.dumps(data, default=str), headers=[('Content-Type', 'application/json')])

    @http.route("/api/appointment/available_slots", type="http", auth="public", methods=["GET"], csrf=False)
    def get_available_slots(self, **kwargs):
        """
        Get available time slots for a given employee on a specific date.
        Example:
            /api/appointment/available_slots?employee_id=12&date=2025-11-10
        """
        try:
            # --- 1. توحيد استخراج اللغة من الهيدر (يدعم lang أو Accept-Language) ---
            header_lang = request.httprequest.headers.get('lang') or request.httprequest.headers.get('Accept-Language')
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            is_arabic = raw_lang.startswith('ar')

            employee_id = kwargs.get("employee_id")
            date_str = kwargs.get("date")

            # 🚀 ترجمة رسائل التحقق (Validation Messages)
            if not employee_id:
                return _json_err("رقم الموظف مفقود" if is_arabic else "Missing employee_id")
            if not date_str:
                return _json_err(
                    "التاريخ مفقود (الصيغة المطلوبة: YYYY-MM-DD)" if is_arabic else "Missing date (format: YYYY-MM-DD)")

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return _json_err(
                    "صيغة التاريخ غير صحيحة. المتوقع YYYY-MM-DD" if is_arabic else "Invalid date format. Expected YYYY-MM-DD")

            employee = request.env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                msg_err = f"الموظف رقم {employee_id} غير موجود" if is_arabic else f"Employee with ID {employee_id} not found"
                return _json_err(msg_err)

            Slot = request.env["appointment.employee.slot"].sudo()

            slots = Slot.search([
                ("employee_id", "=", employee.id),
                ("date", "=", date_obj),
                ("state", "=", "draft")
            ], order="time asc")

            # --- 2. دالة تنسيق الوقت (الأرقام إنجليزية دائماً والكلمة تترجم) ---
            def format_localized_time(t_float, is_ar):
                h24 = int(t_float)
                m = int(round((t_float - h24) * 60))

                # تحديد صباحاً / مساءً أو AM / PM
                am_pm_en = "AM" if h24 < 12 else "PM"
                am_pm_ar = "صباحًا" if h24 < 12 else "مساءً"

                # تحويل لنظام 12 ساعة
                h12 = h24 % 12
                if h12 == 0:
                    h12 = 12

                time_str_base = f"{h12:02d}:{m:02d}"

                # 🚀 التعديل هنا: الأرقام تظل إنجليزية دائماً، نغير فقط النص الملحق
                if is_ar:
                    return f"{time_str_base} {am_pm_ar}"
                else:
                    return f"{time_str_base} {am_pm_en}"

            data = []
            for s in slots:
                time_str = format_localized_time(s.time, is_arabic)

                data.append({
                    "slot_id": s.id,
                    "employee_id": s.employee_id.id,
                    "employee_name": s.employee_id.name,
                    "date": str(s.date),
                    "time": s.time,
                    "time_str": time_str,
                    "state": s.state,
                })

            # 🚀 ترجمة رسالة النجاح
            msg_success = "تم جلب المواعيد المتاحة بنجاح" if is_arabic else "Available slots fetched successfully"
            return _json_ok(msg_success, data)

        except Exception as e:
            _logger.exception("Error fetching available slots")
            # 🚀 ترجمة رسالة الخطأ الداخلي
            msg_server_error = "حدث خطأ داخلي في السيرفر أثناء جلب المواعيد" if is_arabic else str(e)
            return _json_err(msg_server_error, 500)

    @http.route("/api/appointment/book", type="http", auth="public", methods=["POST", "OPTIONS"], csrf=False)
    def create_appointment(self, **kwargs):
        headers = [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*')]
        if request.httprequest.method == 'OPTIONS':
            return request.make_response("", headers=headers)

        # 🚀 قراءة لغة التطبيق من الهيدر لترجمة رسائل الـ API
        is_ar = request.httprequest.headers.get('lang', 'en').lower() == 'ar'

        partner, err = _partner_from_token()
        if err:
            _logger.warning("Booking Auth Error: %s", err)
            return err

        try:
            raw_data = request.httprequest.data
            payload = json.loads(raw_data.decode("utf-8")) if raw_data else {}
            data = {**payload, **kwargs}
            _logger.info("DEBUG BOOKING PAYLOAD: %s", data)

            line_id = data.get("line_id")
            slot_id = data.get("slot_id")
            date_str = data.get("date")
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")

            if not slot_id or not date_str:
                msg = "رقم الموعد أو التاريخ مفقود" if is_ar else "Missing slot_id or date"
                return request.make_response(json.dumps({"status": "error", "message": msg}),
                                             headers=headers, status=400)

            Slot = request.env["appointment.employee.slot"].sudo().browse(int(slot_id))
            if not Slot.exists():
                msg = "الموعد غير موجود أو تم حجزه" if is_ar else "Slot not found"
                return request.make_response(json.dumps({"status": "error", "message": msg}),
                                             headers=headers, status=400)

            target_product_id = int(product_id)
            target_product = request.env['product.product'].sudo().browse(target_product_id)

            # 1. البحث الذكي عن سطر الكارت
            sol = False
            if line_id:
                sol = request.env["sale.order.line"].sudo().browse(int(line_id))
            elif product_id:
                # 1.1 البحث عن خدمة فردية غير محجوزة
                sol = request.env["sale.order.line"].sudo().search([
                    ('order_partner_id', '=', partner.id),
                    ('product_id', '=', target_product_id),
                    ('order_id.state', '=', 'draft'),
                    ('is_scheduled', '=', False)
                ], limit=1, order="id desc")

                # 1.2 البحث عن خدمة فردية محجوزة مسبقاً (حالة التعديل)
                if not sol:
                    sol = request.env["sale.order.line"].sudo().search([
                        ('order_partner_id', '=', partner.id),
                        ('product_id', '=', target_product_id),
                        ('order_id.state', '=', 'draft'),
                        ('is_scheduled', '=', True)
                    ], limit=1, order="id desc")

                # 1.3 البحث داخل سطر الباقة (Combo) عن باقة لم تُجدول هذه الخدمة فيها بعد
                if not sol:
                    draft_lines = request.env["sale.order.line"].sudo().search([
                        ('order_partner_id', '=', partner.id),
                        ('order_id.state', '=', 'draft')
                    ])
                    for line in draft_lines:
                        if any(target_product_id == pkg.product_id.id for pkg in
                               line.product_id.appointment_package_line_ids):
                            # التأكد أن هذه الخدمة تحديداً لم تحجز بعد في هذا السطر
                            existing_app = request.env["appointment.management"].sudo().search([
                                ('order_line_id', '=', line.id),
                                ('product_id', '=', target_product_id),
                                ('state', '!=', '4')  # غير ملغي
                            ], limit=1)
                            if not existing_app:
                                sol = line
                                break
                            elif not sol:
                                sol = line  # احتياطي في حالة التعديل

            if not sol or not sol.exists():
                _logger.error("Booking Failed: SOL not found for Product ID %s", product_id)
                msg = "لم يتم العثور على الخدمة في السلة" if is_ar else "Cart line not found"
                return request.make_response(json.dumps({"status": "error", "message": msg}),
                                             headers=headers, status=400)

            # =========================================================
            # 🚀 1. تحديد السعر وتأكيد هل هي باقة؟
            # =========================================================
            is_combo_cart_line = bool(sol.product_id.appointment_package_line_ids)

            if is_combo_cart_line:
                # لو السطر ده عبارة عن باقة، إذن أي موعد يتحجز ليه هيكون سعره 0
                # لأن العميل هيدفع سعر الباقة الإجمالي الموجود على السلة
                final_price = 0.0
            else:
                # لو خدمة فردية عادية، تاخد السعر الطبيعي
                final_price = sol.price_unit or sol.product_id.list_price or 0.0

            # =========================================================
            # 🚀 2. حساب عدد السلوتات المطلوبة بناءً على الخدمة نفسها
            # =========================================================
            required_slots = 1
            if hasattr(target_product, 'get_website_appointment_duration'):
                required_slots = int(target_product.sudo().get_website_appointment_duration(
                    appointment_type='inside',
                    branch_id=int(branch_id) if branch_id else None
                ) or 1)
            # تم حذف الاعتماد على مدة الباقة الأم حتى لا يتم تضخيم وقت الحجز للخدمة الفرعية

            slots_to_link = [Slot.id]

            if required_slots > 1:
                domain = [
                    ('employee_id', '=', Slot.employee_id.id),
                    ('time', '>', Slot.time)
                ]

                if hasattr(Slot, 'date'):
                    domain.append(('date', '=', Slot.date))
                elif hasattr(Slot, 'schedule_date'):
                    domain.append(('schedule_date', '=', Slot.schedule_date))

                subsequent_slots = request.env["appointment.employee.slot"].sudo().search(
                    domain,
                    order='time asc',
                    limit=required_slots - 1
                )

                for s in subsequent_slots:
                    if s.state == 'draft':
                        slots_to_link.append(s.id)
                    else:
                        break

                if len(slots_to_link) < required_slots:
                    msg = "الوقت المتبقي لا يكفي لإتمام الخدمة، يرجى اختيار موعد أبكر" if is_ar else "Not enough consecutive time slots available for this service."
                    return request.make_response(json.dumps({"status": "error", "message": msg}), headers=headers,
                                                 status=400)

            # =========================================================
            # 🚀 3. إنشاء الحجز
            # =========================================================
            vals = {
                "partner_id": partner.id,
                "employee_id": Slot.employee_id.id,
                "date": date_str,
                "branch_id": int(branch_id or Slot.employee_id.company_id.id or request.env.company.id),
                "product_id": target_product_id,
                "price_unit": final_price,
                "state": "1",
                "sale_order_id": sol.order_id.id,
                "order_line_id": sol.id,
            }

            app_obj = request.env["appointment.management"].sudo().create(vals)

            # ربط السلوتات بالحجز وحجزها
            app_obj.write({"slot_ids": [(6, 0, slots_to_link)]})
            request.env["appointment.employee.slot"].sudo().browse(slots_to_link).write({'state': 'wait'})

            # =========================================================
            # 🚀 4. تحديث حالة الجدولة للسلة (is_scheduled) وربط الـ ID
            # =========================================================
            if not is_combo_cart_line:
                # خدمة فردية عادية
                sol.write({"appointment_id": app_obj.id, "is_scheduled": True})
                _logger.info("Single service SOL %s marked as scheduled", sol.id)
            else:
                # باقة: نربط الـ appointment_id بأول حجز عشان يظهر مرجع في أودو
                if not sol.appointment_id:
                    sol.write({"appointment_id": app_obj.id})

                # نتحقق هل تم جدولة جميع خدمات الباقة بعد هذا الحجز؟
                package_product_ids = sol.product_id.appointment_package_line_ids.mapped('product_id.id')

                booked_apps = request.env["appointment.management"].sudo().search([
                    ('order_line_id', '=', sol.id),
                    ('state', '!=', '4')  # غير ملغي
                ])
                booked_product_ids = booked_apps.mapped('product_id.id')

                # إذا تم جدولة جميع خدمات الباقة بنجاح
                all_booked = all(p_id in booked_product_ids for p_id in package_product_ids)
                if all_booked:
                    sol.write({"is_scheduled": True})
                    _logger.info("Combo package SOL %s fully scheduled!", sol.id)
                else:
                    sol.write({"is_scheduled": False})
                    _logger.info("Combo package SOL %s partially scheduled (%s/%s)",
                                 sol.id, len(set(booked_product_ids)), len(package_product_ids))

            # إشعار الموبايل
            request.env['notifications.model'].sudo().create({
                'partner': partner.id,
                'noti_type': 'Booking',
                'content_ar': 'تمت جدولة موعدك بنجاح ⏳',
                'content_en': 'Appointment Scheduled Successfully ⏳',
                'sub_content_ar': f'تمت جدولة موعدك يوم {date_str} مع {Slot.employee_id.name}. يرجى إتمام الدفع لتأكيد الحجز.',
                'sub_content_en': f'Your appointment on {date_str} with {Slot.employee_id.name} is scheduled. Please complete payment to confirm.',
            })

            msg_success = "تمت جدولة الموعد بنجاح، بانتظار الدفع" if is_ar else "Appointment scheduled successfully, awaiting payment"
            return request.make_response(json.dumps({
                "status": "success",
                "message": msg_success,
                "appointment_id": app_obj.id
            }), headers=headers)

        except Exception as e:
            _logger.exception("Final Booking Error: %s", str(e))
            msg_error = "حدث خطأ داخلي، يرجى المحاولة لاحقاً" if is_ar else str(e)
            return request.make_response(json.dumps({"status": "error", "message": msg_error}), headers=headers,
                                         status=500)
    @http.route("/api/appointment/reschedule", type="http", auth="public", methods=["POST"], csrf=False)
    def reschedule_appointment(self, **kwargs):
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            # 🌐 استخراج اللغة في بداية الكود لدعم ترجمة رسائل الخطأ والنجاح
            is_ar = request.httprequest.headers.get('lang', 'en').lower() in ['ar', 'ar_001']

            appointment_id = payload.get("appointment_id")
            employee_id = payload.get("employee_id")
            slot_id = payload.get("slot_id")
            date_str = payload.get("date")
            branch_id = payload.get("branch_id")

            if not all([appointment_id, employee_id, slot_id, date_str, branch_id]):
                return _json_err("الحقول المطلوبة مفقودة" if is_ar else "Missing required fields")

            appointment = request.env["appointment.management"].sudo().browse(int(appointment_id))
            if not appointment.exists() or appointment.partner_id.id != partner.id:
                return _json_err("لم يتم العثور على الموعد" if is_ar else "Appointment not found", 404)

            if appointment.state != '2':
                return _json_err(
                    "يمكن فقط إعادة جدولة المواعيد المدفوعة" if is_ar else "Only paid appointments can be rescheduled")

            now = datetime.now()
            current_app_date = appointment.date

            if isinstance(current_app_date, str):
                current_app_date = datetime.strptime(current_app_date, "%Y-%m-%d %H:%M:%S")
            elif not hasattr(current_app_date, 'hour'):
                current_app_date = datetime.combine(current_app_date, datetime.min.time())

            if (current_app_date - now) < timedelta(days=2):
                return _json_err(
                    "لا يمكن إعادة الجدولة: الموعد الأصلي يبدأ خلال أقل من 48 ساعة" if is_ar else "Cannot reschedule: original appointment starts within 48 hours")

            try:
                new_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if new_date_obj < now.date():
                    return _json_err(
                        "لا يمكن إعادة الجدولة لتاريخ سابق" if is_ar else "Cannot reschedule to a past date")
            except Exception:
                return _json_err(
                    "صيغة التاريخ غير صحيحة. المتوقع YYYY-MM-DD" if is_ar else "Invalid date format. Expected YYYY-MM-DD")

            new_slot = request.env["appointment.employee.slot"].sudo().browse(int(slot_id))
            new_employee = request.env["hr.employee"].sudo().browse(int(employee_id))
            new_branch = request.env["res.company"].sudo().browse(int(branch_id))

            if not new_slot.exists() or new_slot.state != 'draft':
                return _json_err("الموعد الجديد غير متاح" if is_ar else "New slot is not available")
            if not new_employee.exists():
                return _json_err("لم يتم العثور على الموظف" if is_ar else "Employee not found")
            if not new_branch.exists():
                return _json_err("لم يتم العثور على الفرع" if is_ar else "Branch not found")

            if appointment.slot_ids:
                appointment.slot_ids.write({"state": "draft"})

            appointment.write({
                "employee_id": new_employee.id,
                "branch_id": new_branch.id,
                "date": new_date_obj,
                "slot_ids": [(5, 0, 0), (4, new_slot.id)],
            })

            new_slot.write({"state": "draft", "date": new_date_obj})

            # 🚀 --- التعديل هنا: تخزين الإشعار باللغتين معاً في قاعدة البيانات ---
            request.env['notifications.model'].sudo().create({
                'partner': partner.id,
                'noti_type': 'Reminder',
                'content_ar': 'تم تعديل موعدك 🔄',
                'content_en': 'Appointment Rescheduled 🔄',
                'sub_content_ar': f'تم نقل موعدك إلى يوم {date_str} مع {new_employee.name}.',
                'sub_content_en': f'Your appointment is moved to {date_str} with {new_employee.name}.',
            })
            # ------------------------------------------------

            return _json_ok("تمت إعادة جدولة الموعد بنجاح" if is_ar else "Appointment rescheduled successfully", {
                "appointment_id": appointment.id,
                "employee": new_employee.name,
                "branch": new_branch.name,
                "date": str(appointment.date),
                "slot": new_slot.name
            })

        except Exception as e:
            _logger.exception("Error rescheduling appointment")
            return _json_err("حدث خطأ أثناء الجدولة: " + str(e) if is_ar else str(e), 500)

    @http.route("/api/appointment/cancel", type="http", auth="public", methods=["POST"], csrf=False)
    def cancel_appointment(self, **kwargs):
        partner, err = _partner_from_token()
        if err:
            return err

        # 🚀 التريكة السحرية: استخراج بيئة Admin كاملة لكل الأوبجكتس لمنع أخطاء الصلاحيات
        sudo_env = request.env['res.partner'].sudo().env
        partner_sudo = partner.with_env(sudo_env)

        try:
            # 🚀 استخراج اللغة من الهيدر لترجمة ردود الـ API
            is_ar = request.httprequest.headers.get('lang', 'en').lower() in ['ar', 'ar_001']

            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            appointment_id = payload.get("appointment_id")
            if not appointment_id:
                return _json_err("رقم الموعد مفقود" if is_ar else "Missing appointment_id")

            refund_method = payload.get("refund_method", "wallet")
            if refund_method not in ('wallet', 'same_card', 'bank_transfer'):
                return _json_err(
                    "طريقة الاسترداد غير صالحة" if is_ar else "Invalid refund_method. Must be 'wallet', 'same_card', or 'bank_transfer'")

            # استخدام sudo_env في كل البحث
            appointment = sudo_env["appointment.management"].browse(int(appointment_id))
            if not appointment.exists() or appointment.partner_id.id != partner.id:
                return _json_err("الموعد غير موجود" if is_ar else "Appointment not found", 404)

            if appointment.state != '2':
                return _json_err(
                    "يمكن فقط إلغاء المواعيد المدفوعة" if is_ar else "Only paid/approved appointments can be cancelled")
            if appointment.state == '4':
                return _json_err("الموعد ملغي بالفعل" if is_ar else "Appointment is already cancelled")

            now = datetime.now()
            appointment_date = appointment.date
            if isinstance(appointment_date, str):
                appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d %H:%M:%S")
            elif not hasattr(appointment_date, 'hour'):
                appointment_date = datetime.combine(appointment_date, datetime.min.time())

            refund_policies = sudo_env["appointment.refund.policy"].search(
                [], order="hours_before_appointment asc"
            )

            refund_percentage = 100.0
            deduction_percentage = 0.0
            matched_policy_hours = None

            for policy in refund_policies:
                threshold_time = now + timedelta(hours=policy.hours_before_appointment)
                if threshold_time > appointment_date:
                    deduction_percentage = policy.percentage
                    refund_percentage = 100.0 - policy.percentage
                    matched_policy_hours = policy.hours_before_appointment
                    break
                else:
                    refund_percentage = 100.0
                    deduction_percentage = 0.0

            # =================================================================
            # 🚀 1. حساب السعر الأصلي للخدمة (شامل الضريبة)
            # =================================================================
            original_price = appointment.price_unit

            if appointment.order_line_id:
                original_price = appointment.order_line_id.price_total
            elif hasattr(appointment, 'pos_reference') and appointment.pos_reference:
                pos_order = sudo_env['pos.order'].search([('pos_reference', '=', appointment.pos_reference)], limit=1)
                if pos_order:
                    pos_line = pos_order.lines.filtered(lambda l: l.product_id.id == appointment.product_id.id)
                    if pos_line:
                        original_price = pos_line[0].price_subtotal_incl
            elif hasattr(appointment, 'price_total') and appointment.price_total > 0:
                original_price = appointment.price_total

            deduction_amount = round(original_price * (deduction_percentage / 100), 2)
            refund_amount = round(original_price - deduction_amount, 2)
            # =================================================================

            # 2. تحديث حالة الموعد
            appointment.write({
                "state": "4",
                "cancelled_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "refund_amount": refund_amount,
                "deduction_amount": deduction_amount,
                "deduction_percentage": deduction_percentage,
            })

            if appointment.slot_ids:
                appointment.slot_ids.write({"state": "draft"})

            # =================================================================
            # 🚀 3. إنشاء الكريدت نوت المباشر وضبط مبلغه أوتوماتيكياً (ORM Way)
            # =================================================================
            _logger.info("========== START APPOINTMENT CANCELLATION ==========")
            invoices = sudo_env['account.move'].browse()

            # أ) جلب الفاتورة من أمر البيع
            if appointment.sale_order_id:
                invoices |= appointment.sale_order_id.invoice_ids.filtered(
                    lambda i: i.state == 'posted' and i.move_type == 'out_invoice')

            # ب) جلب الفاتورة من نقطة البيع
            if not invoices and hasattr(appointment, 'pos_reference') and appointment.pos_reference:
                pos_order = sudo_env['pos.order'].search([('pos_reference', '=', appointment.pos_reference)], limit=1)
                if pos_order and hasattr(pos_order, 'account_move') and pos_order.account_move:
                    invoices |= pos_order.account_move.filtered(
                        lambda i: i.state == 'posted' and i.move_type == 'out_invoice')

            # ج) جلب الفاتورة المربوطة مباشرة
            if not invoices and hasattr(sudo_env['account.move'], 'appointment_ids'):
                invoices |= sudo_env['account.move'].search([
                    ('appointment_ids', 'in', appointment.id),
                    ('state', '=', 'posted'),
                    ('move_type', '=', 'out_invoice')
                ])

            if invoices:
                for invoice in invoices:
                    try:
                        reversal_vals = {
                            'ref': f'إلغاء الحجز {appointment.appointment_ref}' if is_ar else f'Cancellation of {appointment.appointment_ref}',
                            'date': now.date(),
                            'invoice_date': now.date(),
                            'journal_id': invoice.journal_id.id,
                        }

                        credit_notes = invoice._reverse_moves([reversal_vals])

                        if credit_notes:
                            for cn in credit_notes:
                                if cn.state == 'draft':
                                    line_commands = []
                                    for line in cn.invoice_line_ids:
                                        if appointment.product_id and line.product_id.id == appointment.product_id.id:
                                            line_commands.append((1, line.id, {'discount': deduction_percentage}))
                                        else:
                                            line_commands.append((2, line.id, 0))

                                    cn.write({'invoice_line_ids': line_commands})
                                    cn.action_post()

                                _logger.info(" -> SUCCESS: Credit Note %s Created & Posted (Total: %s)", cn.name,
                                             cn.amount_total)

                                if refund_method == 'wallet' and cn.amount_total > 0:
                                    journal = sudo_env['account.journal'].search([
                                        ('type', 'in', ('bank', 'cash')),
                                        ('company_id', '=', cn.company_id.id)
                                    ], limit=1)

                                    if journal:
                                        payment_vals = {
                                            'payment_type': 'outbound',
                                            'partner_type': 'customer',
                                            'partner_id': cn.partner_id.id,
                                            'amount': cn.amount_total,
                                            'journal_id': journal.id,
                                            'ref': f'Refund to Wallet - {appointment.appointment_ref}',
                                            'company_id': cn.company_id.id,
                                        }
                                        payment = sudo_env['account.payment'].create(payment_vals)
                                        payment.action_post()

                                        lines = (cn + payment.move_id).line_ids.filtered(
                                            lambda
                                                l: l.account_id.account_type == 'asset_receivable' and not l.reconciled
                                        )
                                        if len(lines) > 1:
                                            lines.reconcile()

                                        _logger.info(" -> SUCCESS: Credit Note %s Fully Reconciled as PAID", cn.name)

                    except Exception as e:
                        _logger.error("FAILED TO ADJUST/RECONCILE CREDIT NOTE FOR INVOICE %s: %s", invoice.name, str(e))
            else:
                _logger.warning("SKIPPED: This appointment has no linked Invoices.")

            _logger.info("========== END APPOINTMENT CANCELLATION ==========")

            # =================================================================
            # 4. تغذية المحفظة / إنشاء طلب استرداد بنكي
            # =================================================================
            refund_request_id = None
            refund_request_sequence = None

            if refund_method == 'wallet':
                if refund_amount > 0:
                    partner_sudo.add_wallet_credit(
                        amount=refund_amount,
                        source_type='refund',
                        source_description='Cancellation refund for %s' % appointment.appointment_ref,
                        notes='Policy: %s hrs, Deduction: %.1f%%, Refund: %.2f' % (
                            matched_policy_hours or 'N/A', deduction_percentage, refund_amount
                        ),
                    )
                refund_msg_ar = "تم استرداد المبلغ إلى محفظتك."
                refund_msg_en = "Refund credited to your wallet automatically."
            else:
                request_vals = {
                    "appointment_id": appointment.id,
                    "refund_amount": refund_amount,
                    "refund_method": refund_method,
                    "reason": payload.get("reason", ""),
                }

                if refund_method == 'same_card':
                    card_last_four = payload.get("card_last_four")
                    if not card_last_four:
                        return _json_err(
                            "رقم البطاقة مفقود" if is_ar else "Missing card_last_four for same_card refund")
                    request_vals.update({
                        "card_last_four": card_last_four,
                        "card_type": payload.get("card_type", ""),
                        "transaction_reference": payload.get("transaction_reference", ""),
                    })
                elif refund_method == 'bank_transfer':
                    bank_name = payload.get("bank_name")
                    if not bank_name:
                        return _json_err("اسم البنك مفقود" if is_ar else "Missing bank_name")
                    request_vals.update({
                        "bank_name": bank_name,
                        "account_holder_name": payload.get("account_holder_name"),
                        "account_number": payload.get("account_number"),
                        "swift_code": payload.get("swift_code", ""),
                    })

                refund_req = sudo_env["appointment.refund.request"].create(request_vals)
                refund_request_id = refund_req.id
                refund_request_sequence = refund_req.sequence

                refund_msg_ar = "تم تقديم طلب الاسترداد للإدارة."
                refund_msg_en = "Refund request submitted. Pending admin approval."

            refund_status_message = refund_msg_ar if is_ar else refund_msg_en

            # 5. إرسال إشعار الإلغاء للموبايل
            sudo_env['notifications.model'].create({
                'partner': partner.id,
                'noti_type': 'Failure',
                'content_ar': 'تم إلغاء الموعد ❌',
                'content_en': 'Appointment Cancelled ❌',
                'sub_content_ar': f'تم إلغاء حجزك. {refund_msg_ar}',
                'sub_content_en': f'Your booking has been cancelled. {refund_msg_en}',
            })

            # 🔥 الضربة القاضية: إجبار أودو إنه يعتمد كل الحسابات (Flush) كـ Admin
            # علشان يخلص حسابات الـ Sale Order من غير ما يضرب أخطاء الصلاحيات!
            if hasattr(sudo_env, 'flush_all'):
                sudo_env.flush_all()
            else:
                sudo_env.cr.flush()

            response_data = {
                "appointment_id": appointment.id,
                "appointment_sequence": appointment.appointment_ref,
                "state": "4",
                "original_price": original_price,
                "deduction_amount": deduction_amount,
                "refund_amount": refund_amount,
                "refund_method": refund_method,
                "cancelled_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "refund_status_message": refund_status_message,
            }

            if refund_request_id:
                response_data.update({
                    "refund_request_id": refund_request_id,
                    "refund_request_sequence": refund_request_sequence,
                    "refund_request_state": "pending",
                })

            msg_success = "تم إلغاء الموعد بنجاح" if is_ar else "Appointment cancelled successfully"
            return _json_ok(msg_success, response_data)

        except Exception as e:
            _logger.exception("Error cancelling appointment via API")
            msg_err = f"حدث خطأ أثناء الإلغاء: {str(e)}" if is_ar else str(e)
            return _json_err(msg_err, 500)
    def get_product_order_history(self, **kwargs):
        """
        Get the physical product purchase history for the partner.
        Excludes draft/cancelled orders and service-only appointments.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # Search for confirmed sales orders (state 'sale' or 'done')
            # We filter by partner and exclude 'draft' or 'cancel'
            orders = request.env["sale.order"].sudo().search([
                ("partner_id", "=", partner.id),
                ("state", "in", ["sale", "done"]),
                # Optional: Filter for orders that originated from product_cart
                # ("origin", "=", "product_cart")
            ], order="date_order desc")

            data = []
            for order in orders:
                items = []
                for line in order.order_line:
                    # We only include physical products (storable or consumable)
                    # or those not linked to an appointment
                    product = line.product_id

                    items.append({
                        "product_variant": product.product_variant_id.id if product.product_variant_id else product.id,
                        "product_id": product.id,
                        "name": product.name,
                        "qty": line.product_uom_qty,
                        "price_unit": line.price_unit,
                        "total_price": line.price_subtotal,
                        "tax_amount": line.price_tax,
                        "description": product.description_sale or False,
                        "detailed_type": product.detailed_type,
                        "category": product.categ_id.name,
                        "currency": order.currency_id.name,
                        "uom": line.product_uom.name,
                        "main_image_url": f"/web/image/product.product/{product.id}/image_1920" if product.image_1920 else None,
                        "gallery_urls": [], # Can be expanded if you have a gallery module
                    })

                # Only add to list if the order has physical items
                if items:
                    data.append({
                        "order_id": order.id,
                        "name": order.name,
                        "date": str(order.date_order),
                        "state": order.state,
                        "total_items": int(sum(order.order_line.mapped('product_uom_qty'))),
                        "amount_untaxed": order.amount_untaxed,
                        "amount_tax": order.amount_tax,
                        "amount_total": order.amount_total,
                        "delivery_status": getattr(order, 'delivery_status', 'N/A'), # Requires stock module
                        "items": items
                    })

            return _json_ok("Product order history fetched successfully", {
                "count": len(data),
                "orders": data
            })

        except Exception as e:
            _logger.exception("Error fetching product order history")
            return _json_err(str(e), 500)

    @http.route("/api/image/<string:model>/<int:record_id>/<string:field>",
                type="http", auth="public", methods=["GET"], csrf=False)
    def get_public_image(self, model, record_id, field, **kwargs):
        try:
            allowed_models = ["product.template", "product.product", "product.template.img"]
            if model not in allowed_models:
                _logger.warning("IMAGE >> model not allowed: %s", model)
                return request.not_found()

            record = request.env[model].sudo().browse(record_id)
            if not record.exists():
                _logger.warning("IMAGE >> record not found: %s id=%s", model, record_id)
                return request.not_found()

            image_data = getattr(record, field, None)

            # ✅ Key debug line
            _logger.info("IMAGE >> model=%s id=%s field=%s | has_data=%s | type=%s",
                         model, record_id, field, bool(image_data), type(image_data))

            if not image_data:
                _logger.warning("IMAGE >> field is empty: %s", field)
                return request.not_found()

            import base64

            # ✅ Handle both bytes and string
            if isinstance(image_data, bytes):
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = base64.b64decode(image_data.encode('utf-8'))

            # ✅ Detect image type (jpeg vs png)
            if image_bytes[:3] == b'\xff\xd8\xff':
                content_type = "image/jpeg"
            elif image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                content_type = "image/png"
            else:
                content_type = "image/jpeg"  # default fallback

            _logger.info("IMAGE >> serving %s bytes as %s", len(image_bytes), content_type)

            return request.make_response(image_bytes, headers=[
                ("Content-Type", content_type),
                ("Cache-Control", "public, max-age=86400"),
            ])
        except Exception as e:
            _logger.exception("IMAGE >> Error serving image: %s", str(e))
            return request.not_found()
    #history of appointment
    @http.route("/api/appointment/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_appointment_history(self, **kwargs):
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # --- استخراج اللغة من الـ Headers للترجمة ---
            header_lang = request.httprequest.headers.get('lang')
            raw_lang = (header_lang or kwargs.get('lang') or 'en').lower()
            lang_map = {'ar': 'ar_001', 'en': 'en_US'}
            lang = lang_map.get(raw_lang, raw_lang)

            # --- تمرير اللغة في الـ Context ---
            appointments = request.env["appointment.management"].sudo().with_context(lang=lang).search([
                ("partner_id", "=", partner.id),
                ("state", "in", ["2", "3", "4"])
            ], order="date desc")

            base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")

            data = []
            for appointment in appointments:
                # إجبار الـ Context على المنتج
                product = appointment.product_id.with_context(lang=lang) if appointment.product_id else None
                product_tmpl = product.product_tmpl_id if product else None

                # ✅ بناء رابط الصورة الرئيسية
                main_image_url = None
                if product_tmpl and product_tmpl.sudo().image_1920:
                    main_image_url = f"{base_url}/api/public/image/product.template/{product_tmpl.id}/image_1920"
                elif product and product.sudo().image_1920:
                    main_image_url = f"{base_url}/api/public/image/product.product/{product.id}/image_1920"

                # ✅ إضافة معرض الصور
                gallery_urls = []
                if product_tmpl and hasattr(product_tmpl, "img_ids"):
                    for img in product_tmpl.img_ids.sudo():
                        if img.img:
                            gallery_urls.append(f"{base_url}/api/public/image/product.template.img/{img.id}/img")

                slots_info = []
                for slot in appointment.slot_ids:
                    slots_info.append({
                        "slot_id": slot.id,
                        "name": slot.name,
                        "time": slot.time,
                        "state": slot.state
                    })

                state_display_map = {
                    '0': 'Draft',
                    '1': 'Partial Approved',
                    '2': 'Approved',
                    '3': 'Completed',
                    '4': 'Cancelled'
                }

                # 🧮 حساب الضريبة والإجمالي (السعر الأساسي + الضريبة)
                price_unit = appointment.price_unit or 0.0
                tax_amount = 0.0
                if product and product.taxes_id:
                    tax_amount = sum(tax.amount * price_unit / 100 for tax in product.taxes_id)
                total_price = price_unit + tax_amount

                # 🌐 استخراج الفئة المترجمة: الاعتماد على فئات نقطة البيع (POS Categories) أولاً
                category_name = None
                if product:
                    if hasattr(product, 'pos_categ_ids') and product.pos_categ_ids:
                        # أخذ أول فئة نقطة بيع مترجمة
                        category_name = product.pos_categ_ids[0].with_context(lang=lang).name
                    elif product.categ_id:
                        # بديل احتياطي: الفئة الأساسية
                        category_name = product.categ_id.with_context(lang=lang).name

                # 🌐 وحدة القياس المترجمة
                uom_name = product.uom_id.with_context(lang=lang).name if product and product.uom_id else None

                # ⭐️ التعديل الجديد: استخراج الخدمات الفرعية إذا كانت الخدمة "باقة" ⭐️
                package_items = []
                if product and hasattr(product,
                                       'appointment_package_line_ids') and product.appointment_package_line_ids:
                    for pkg_line in product.appointment_package_line_ids:
                        sub_product = pkg_line.product_id.with_context(lang=lang) if pkg_line.product_id else None
                        if sub_product:
                            package_items.append({
                                "service_id": sub_product.id,
                                "service_name": sub_product.name,
                            })

                appointment_data = {
                    "appointment_id": appointment.id,
                    "sequence": appointment.appointment_ref,
                    "employee_id": appointment.employee_id.id,
                    "employee_name": appointment.employee_id.name,
                    "date": str(appointment.date),
                    "state": appointment.state,
                    "state_display": state_display_map.get(appointment.state, appointment.state),
                    "price_unit": price_unit,
                    "notes": appointment.notes,
                    "branch_id": appointment.branch_id.id if appointment.branch_id else None,
                    "branch_name": appointment.branch_id.name if appointment.branch_id else "",
                    "service_data": {
                        "product_variant": product.product_variant_id.id if product and product.product_variant_id else (
                            product.id if product else None),
                        "product_id": product.id if product else None,
                        "name": product.name if product else "",
                        "qty": 1.0,
                        "is_scheduled": True,
                        "price_unit": price_unit,
                        "total_price": total_price,
                        "tax_amount": tax_amount,
                        "description": product.description_sale or False if product else False,
                        "detailed_type": product.detailed_type if product else False,
                        "category": category_name,
                        "currency": appointment.company_id.currency_id.name,
                        "uom": uom_name,
                        "main_image_url": main_image_url,
                        "gallery_urls": gallery_urls,

                        # ⭐️ إضافة بيانات الباقة للـ JSON اللي رايح للموبايل ⭐️
                        "is_package": bool(package_items),  # هترجع true لو الحجز ده عبارة عن باقة
                        "package_items": package_items,  # لستة بأسماء الخدمات اللي جوه الباقة
                    },
                    "slot_ids": appointment.slot_ids.mapped("id"),
                    "slots_info": slots_info,
                }

                if appointment.state == '4':
                    appointment_data.update({
                        "cancelled_at": str(appointment.cancelled_at) if appointment.cancelled_at else None,
                        "refund_amount": appointment.refund_amount or 0.0,
                        "deduction_amount": appointment.deduction_amount or 0.0,
                        "deduction_percentage": appointment.deduction_percentage or 0.0,
                    })

                data.append(appointment_data)

            return _json_ok("Appointment history fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching appointment history")
            return _json_err(str(e), 500)
    @http.route("/api/appointment/employees_for_service", type="http", auth="public", methods=["GET"], csrf=False)
    def get_employees_for_service(self, **kwargs):
        """
        Get all employees for a specific service (product_id) across all branches.
        Logic:
          - Get all departments linked to this product via plan_ids
          - Find employees in those departments
          - Return all employees working in these departments across all branches
        """
        try:
            product_id = kwargs.get("product_id")

            if not product_id:
                return _json_err("Missing product_id")

            product = request.env["product.product"].sudo().browse(int(product_id))
            if not product.exists():
                return _json_err(f"Product with ID {product_id} not found")

            departments = product.plan_ids.mapped("department_id")
            if not departments:
                return _json_err("This product has no departments linked in its plans")

            employees = request.env["hr.employee"].sudo().search([("department_id", "in", departments.ids)])

            if not employees:
                return _json_ok("No employees found for this product's departments", [])

            data = []
            for emp in employees:
                data.append({
                    "id": emp.id,
                    "name": emp.name,
                    "branch": emp.company_id.name if emp.company_id else "",
                    "job_title": emp.job_title or "",
                    "work_email": emp.work_email or "",
                    "work_phone": emp.work_phone or "",
                    "department": emp.department_id.name if emp.department_id else "",
                    "image_url": f"/web/image/hr.employee/{emp.id}/image_1920",
                })

            return _json_ok("Employees for service fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching employees for service")
            return _json_err(str(e), 500)

    @http.route("/api/update_partner_location", type="http", auth="public", methods=["POST"], csrf=False)
    def update_partner_location(self, **kwargs):
        """
        Update partner's location (longitude and latitude) via API.
        The partner must be authenticated with a valid token.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            long = payload.get("long")
            late = payload.get("late")

            if not long or not late:
                return _json_err("Longitude and Latitude are required.")

            partner.write({
                'long': long,
                'late': late
            })

            return _json_ok("Partner location updated successfully", {
                "partner_id": partner.id,
                "name": partner.name,
                "long": long,
                "late": late
            })

        except Exception as e:
            return _json_err(f"Error updating location: {str(e)}", 500)

    @http.route('/appointment/pos-user/invoice/<int:order_id>', type='http', auth="none", methods=['GET'], csrf=False)
    def download_unified_invoice(self, order_id, **kwargs):
        """
        Unified route to download POS PDF receipt for BOTH Appointments and Sale Orders.
        Handles ID collisions.
        """
        try:
            # 1. البحث في الجدولين في نفس الوقت
            appointment = request.env["appointment.management"].sudo().browse(order_id)
            sale_order = request.env["sale.order"].sudo().browse(order_id)

            appt_exists = appointment.exists()
            sale_exists = sale_order.exists()

            target_record = None
            report_ref = None
            filename = "Receipt.pdf"

            # 2. تحديد الفاتورة المطلوبة
            if appt_exists and not sale_exists:
                target_record = appointment
                report_ref = 'sms_mobile_sa_otp.action_report_appointment_pos_receipt'
                filename = f"Receipt_Appt_{appointment.appointment_ref or appointment.id}.pdf"

            elif sale_exists and not appt_exists:
                target_record = sale_order
                report_ref = 'sms_mobile_sa_otp.action_report_sale_pos_receipt'
                filename = f"Receipt_Sale_{sale_order.name or sale_order.id}.pdf"

            elif appt_exists and sale_exists:
                if appointment.create_date > sale_order.create_date:
                    target_record = appointment
                    report_ref = 'sms_mobile_sa_otp.action_report_appointment_pos_receipt'
                    filename = f"Receipt_Appt_{appointment.appointment_ref or appointment.id}.pdf"
                else:
                    target_record = sale_order
                    report_ref = 'sms_mobile_sa_otp.action_report_sale_pos_receipt'
                    filename = f"Receipt_Sale_{sale_order.name or sale_order.id}.pdf"
            else:
                return request.make_response("Record Not Found in Appointments or Sales", status=404)

            # 3. إصدار الـ PDF
            report_sudo = request.env.ref(report_ref).sudo()
            pdf_content, content_type = report_sudo._render(
                report_sudo.id,
                [target_record.id]
            )

            # 4. إرسال الملف
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', str(len(pdf_content))),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]

            return request.make_response(pdf_content, headers=headers)

        except Exception as e:
            _logger.error("Unified POS Receipt Download Error: %s", str(e))
            return request.make_response(f"Server Error: {str(e)}", status=500)
    # ═══════════════════════════════════════════════════════════════════════════
    # REFUND REQUEST API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════════

    @http.route("/api/refund/request", type="http", auth="public", methods=["POST"], csrf=False)
    def create_refund_request(self, **kwargs):
        """
        Create a refund request for a cancelled appointment.

        Two options for refund method:
        1. same_card - Refund to the same card used for payment
        2. bank_transfer - Manual bank transfer with customer-provided bank details

        Note: Wallet refunds are processed automatically during cancellation.
        This endpoint is for requesting alternative refund methods.

        JSON Body for same_card:
        {
            "appointment_id": 123,
            "refund_method": "same_card",
            "card_last_four": "4242",
            "card_type": "Visa",
            "transaction_reference": "TXN123456",
            "reason": "I prefer refund to my card"
        }

        JSON Body for bank_transfer:
        {
            "appointment_id": 123,
            "refund_method": "bank_transfer",
            "bank_name": "Al Rajhi Bank",
            "account_holder_name": "John Doe",
            "account_number": "SA0380000000608010167519",
            "swift_code": "RJHISARI",
            "reason": "Please transfer to my bank account"
        }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            appointment_id = payload.get("appointment_id")
            refund_method = payload.get("refund_method")
            reason = payload.get("reason", "")

            if not appointment_id:
                return _json_err("Missing appointment_id")
            if not refund_method:
                return _json_err("Missing refund_method. Must be 'same_card' or 'bank_transfer'")
            if refund_method not in ('same_card', 'bank_transfer'):
                return _json_err("Invalid refund_method. Must be 'same_card' or 'bank_transfer'")

            # Fetch appointment
            appointment = request.env["appointment.management"].sudo().browse(int(appointment_id))
            if not appointment.exists() or appointment.partner_id.id != partner.id:
                return _json_err("Appointment not found", 404)

            # Must be cancelled to request refund
            if appointment.state != '4':
                return _json_err("Only cancelled appointments can request refund. Current state is not cancelled.")

            # Check if refund request already exists
            existing_request = request.env["appointment.refund.request"].sudo().search([
                ("appointment_id", "=", appointment.id),
                ("state", "not in", ("declined",))
            ], limit=1)
            if existing_request:
                return _json_err(
                    f"A refund request already exists for this appointment. Status: {existing_request.state}",
                    400
                )

            # Prepare request values
            request_vals = {
                "appointment_id": appointment.id,
                "refund_amount": appointment.refund_amount or appointment.price_unit,
                "refund_method": refund_method,
                "reason": reason,
            }

            # Validate and add method-specific fields
            if refund_method == 'same_card':
                card_last_four = payload.get("card_last_four")
                card_type = payload.get("card_type")
                transaction_reference = payload.get("transaction_reference")

                if not card_last_four:
                    return _json_err("Missing card_last_four for same_card refund")

                request_vals.update({
                    "card_last_four": card_last_four,
                    "card_type": card_type or "",
                    "transaction_reference": transaction_reference or "",
                })

            elif refund_method == 'bank_transfer':
                bank_name = payload.get("bank_name")
                account_holder_name = payload.get("account_holder_name")
                account_number = payload.get("account_number")
                swift_code = payload.get("swift_code")

                if not bank_name:
                    return _json_err("Missing bank_name for bank_transfer refund")
                if not account_holder_name:
                    return _json_err("Missing account_holder_name for bank_transfer refund")
                if not account_number:
                    return _json_err("Missing account_number (IBAN) for bank_transfer refund")

                request_vals.update({
                    "bank_name": bank_name,
                    "account_holder_name": account_holder_name,
                    "account_number": account_number,
                    "swift_code": swift_code or "",
                })

            # Create the refund request
            refund_request = request.env["appointment.refund.request"].sudo().create(request_vals)

            _logger.info(
                "Refund request %s created for appointment %s by partner %s | method=%s amount=%.2f",
                refund_request.sequence, appointment.sequence, partner.id,
                refund_method, refund_request.refund_amount
            )

            return _json_ok("Refund request submitted successfully. Pending admin approval.", {
                "refund_request_id": refund_request.id,
                "request_sequence": refund_request.sequence,
                "appointment_id": appointment.id,
                "appointment_sequence": appointment.sequence,
                "refund_amount": refund_request.refund_amount,
                "refund_method": refund_method,
                "state": "pending",
                "message": "Your refund request has been submitted and is pending admin review."
            })

        except Exception as e:
            _logger.exception("Error creating refund request via API")
            return _json_err(str(e), 500)

    @http.route("/api/refund/status", type="http", auth="public", methods=["GET"], csrf=False)
    def get_refund_request_status(self, **kwargs):
        """
        Get the status of a refund request.

        Query params:
            - refund_request_id: ID of the refund request
            OR
            - appointment_id: ID of the appointment to check for refund requests
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            refund_request_id = kwargs.get("refund_request_id")
            appointment_id = kwargs.get("appointment_id")

            if not refund_request_id and not appointment_id:
                return _json_err("Missing refund_request_id or appointment_id")

            domain = [("partner_id", "=", partner.id)]
            if refund_request_id:
                domain.append(("id", "=", int(refund_request_id)))
            else:
                domain.append(("appointment_id", "=", int(appointment_id)))

            refund_request = request.env["appointment.refund.request"].sudo().search(domain, limit=1, order="id desc")

            if not refund_request:
                return _json_err("Refund request not found", 404)

            data = {
                "refund_request_id": refund_request.id,
                "request_sequence": refund_request.sequence,
                "appointment_id": refund_request.appointment_id.id,
                "appointment_sequence": refund_request.appointment_id.sequence,
                "refund_amount": refund_request.refund_amount,
                "refund_method": refund_request.refund_method,
                "state": refund_request.state,
                "state_display": dict(refund_request._fields['state'].selection).get(refund_request.state),
                "reason": refund_request.reason or "",
                "decline_reason": refund_request.decline_reason or "",
                "requested_at": refund_request.requested_at.strftime("%Y-%m-%d %H:%M:%S") if refund_request.requested_at else None,
                "reviewed_at": refund_request.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if refund_request.reviewed_at else None,
                "completed_at": refund_request.completed_at.strftime("%Y-%m-%d %H:%M:%S") if refund_request.completed_at else None,
            }

            # Include bank/card details based on method
            if refund_request.refund_method == 'bank_transfer':
                data.update({
                    "bank_name": refund_request.bank_name,
                    "account_holder_name": refund_request.account_holder_name,
                    "account_number": refund_request.account_number,
                    "swift_code": refund_request.swift_code or "",
                })
            elif refund_request.refund_method == 'same_card':
                data.update({
                    "card_last_four": refund_request.card_last_four,
                    "card_type": refund_request.card_type or "",
                })

            return _json_ok("Refund request status fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching refund request status")
            return _json_err(str(e), 500)

    @http.route("/api/refund/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_refund_history(self, **kwargs):
        """
        Get all refund requests for the authenticated customer.

        Query params (optional):
            - state: Filter by state (pending, approved, processing, completed, declined)
            - limit: Number of records to return (default: 20)
            - offset: Offset for pagination (default: 0)
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            state = kwargs.get("state")
            limit = int(kwargs.get("limit", 20))
            offset = int(kwargs.get("offset", 0))

            domain = [("partner_id", "=", partner.id)]
            if state:
                domain.append(("state", "=", state))

            refund_requests = request.env["appointment.refund.request"].sudo().search(
                domain, limit=limit, offset=offset, order="create_date desc"
            )
            total_count = request.env["appointment.refund.request"].sudo().search_count(domain)

            data = []
            for req in refund_requests:
                data.append({
                    "refund_request_id": req.id,
                    "request_sequence": req.sequence,
                    "appointment_id": req.appointment_id.id,
                    "appointment_sequence": req.appointment_id.sequence,
                    "refund_amount": req.refund_amount,
                    "refund_method": req.refund_method,
                    "refund_method_display": dict(req._fields['refund_method'].selection).get(req.refund_method),
                    "state": req.state,
                    "state_display": dict(req._fields['state'].selection).get(req.state),
                    "decline_reason": req.decline_reason or "",
                    "requested_at": req.requested_at.strftime("%Y-%m-%d %H:%M:%S") if req.requested_at else None,
                    "completed_at": req.completed_at.strftime("%Y-%m-%d %H:%M:%S") if req.completed_at else None,
                })

            return _json_ok("Refund history fetched successfully", {
                "count": len(data),
                "total": total_count,
                "offset": offset,
                "limit": limit,
                "refund_requests": data
            })

        except Exception as e:
            _logger.exception("Error fetching refund history")
            return _json_err(str(e), 500)

    @http.route("/api/delete_partner", type="http", auth="public", methods=["DELETE", "POST", "OPTIONS"], csrf=False)
    def delete_partner_account(self, **kwargs):
        # 1. إعداد الـ Headers للسماح للموبايل بالوصول (CORS)
        headers = [
            ('Content-Type', 'application/json'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'DELETE, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type, Authorization, lang'),
        ]

        # معالجة طلب الـ OPTIONS (Preflight) اللي الموبايل بيبعته أولاً
        if request.httprequest.method == 'OPTIONS':
            return request.make_response("", headers=headers)

        try:
            # 2. التحقق من التوكن وجلب الـ Partner
            # تأكد أن الدالة _partner_from_token ترجع (partner, error_response)
            partner, err = self._partner_from_token()
            if err:
                # إذا كانت err هي الرد الجاهز، تأكد من إرجاعها مع الهيدرز
                return err

            # 3. تجهيز بيانات الأرشفة وتغيير المسميات لتسمح بإعادة التسجيل
            timestamp = datetime.now().strftime('%Y%m%d%H%M')
            rename_suffix = f"_del_{timestamp}"

            archive_vals = {
                "active": False,
                "comment": f"Account deleted via mobile app on {datetime.now()}.",
            }

            if partner.email:
                archive_vals["email"] = f"{partner.email}{rename_suffix}"

            if partner.phone:
                archive_vals["phone"] = f"{partner.phone}{rename_suffix}"

            # 4. أرشفة المستخدم (User) المرتبط بالـ Partner (خطوة أمان هامة)
            linked_user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            if linked_user:
                linked_user.write({
                    'active': False,
                    'login': f"{linked_user.login}{rename_suffix}"  # عشان يقدر يسجل بنفس الإيميل تاني
                })

            # 5. تنفيذ التعديل على العميل (Partner)
            partner.sudo().write(archive_vals)

            _logger.info("Account Deleted: Partner ID %s archived.", partner.id)

            # 6. الرد بنجاح العملية
            response_data = {
                "status": "success",
                "message": "Your account has been successfully removed. You can register again at any time."
            }
            return request.make_response(json.dumps(response_data), headers=headers)

        except Exception as e:
            _logger.exception("Account deletion error: %s", e)
            error_data = {
                "status": "error",
                "message": f"Internal server error: {str(e)}"
            }
            return request.make_response(json.dumps(error_data), headers=headers, status=500)

    def _partner_from_token(self):
        """
        دالة مساعدة لفك التوكن وجلب العميل.
        تأكد أن هذه الدالة موجودة داخل الكلاس أو استبدلها بمنطق الـ JWT الخاص بك.
        """
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header or " " not in auth_header:
            res = {"status": "error", "message": "Token missing"}
            return None, request.make_response(json.dumps(res), headers=[('Content-Type', 'application/json')],
                                               status=401)

        token = auth_header.split(" ")[1]
        try:
            # SECRET_KEY يجب أن يكون معرفاً لديك
            payload = jwt.decode(token, "bcf2e5f933a069b6d737d5cc0a7af01b", algorithms=["HS256"])
            partner_id = payload.get("partner_id")
            partner = request.env['res.partner'].sudo().browse(partner_id)
            if not partner.exists():
                raise Exception("Partner not found")
            return partner, None
        except Exception as e:
            res = {"status": "error", "message": str(e)}
            return None, request.make_response(json.dumps(res), headers=[('Content-Type', 'application/json')],
                                               status=401)