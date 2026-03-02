from odoo import http
from odoo.http import request, Response
from datetime import datetime
import json, jwt, logging

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
                "amount_tax": 0.0,
                "amount_return": 0.0,
                "lines": order_lines,
            }

            order = PosOrder.create(order_vals)

            if hasattr(order, "_recompute_dynamic_lines"):
                order._recompute_dynamic_lines(recompute_all_taxes=True)
            elif hasattr(order, "_compute_amount_all"):
                order._compute_amount_all()

            order.amount_paid = amount_paid
            order.amount_total = total

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

            if abs(total_payment - total) < 0.01:
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
                    "state": "approved",
                }

                appointment = Appointment.create(appointment_vals)
                _logger.info(f"✅ Appointment created: {appointment.sequence} for order {order.name}")

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
        Get all branches (companies) with location and contact details.
        """
        try:
            Company = request.env["res.company"].sudo()
            companies = Company.search([])

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
                    "latitude": company.latitude,
                    "longitude": company.longitude,
                    "work_time_from": company.work_time_from,
                    "work_time_to": company.work_time_to,
                })

            return _json_ok("Branches fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching branches")
            return _json_err(str(e), 500)

    @http.route("/api/appointment/available_employees", type="http", auth="public", methods=["GET"], csrf=False)
    def get_available_employees(self, **kwargs):
        """
        Get available employees for a specific service (product_id) and date.
        Logic:
          - Get all departments linked to this product via plan_ids
          - Find employees in those departments
          - Check which employees have available slots on that date
        """
        try:
            product_id = kwargs.get("product_id")
            date_str = kwargs.get("date")
            branch_id = kwargs.get("branch_id")

            if not product_id:
                return _json_err("Missing product_id")
            if not date_str:
                return _json_err("Missing date (format: YYYY-MM-DD)")

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return _json_err("Invalid date format. Expected YYYY-MM-DD")

            product = request.env["product.product"].sudo().browse(int(product_id))
            if not product.exists():
                return _json_err(f"Product with ID {product_id} not found")

            departments = product.plan_ids.mapped("department_id")
            if not departments:
                return _json_err("This product has no departments linked in its plans")

            employees_in_dept = request.env["hr.employee"].sudo().search([
                ("department_id", "in", departments.ids)
            ])
            employee_domain = [("department_id", "in", departments.ids)]
            if branch_id:
                try:
                    employee_domain.append(("company_id", "=", int(branch_id)))
                except ValueError:
                    return _json_err("Invalid branch_id format")
                
            employees_in_dept = request.env["hr.employee"].sudo().search(employee_domain)   
            
            if not employees_in_dept:
                return _json_ok("No employees found for this product's departments", [])

            Slot = request.env["appointment.employee.slot"].sudo()
            slots = Slot.search([
                ("employee_id", "in", employees_in_dept.ids),
                ("date", "=", date_obj),
            ])

            available_employees = slots.mapped("employee_id")

            data = []
            for emp in available_employees:
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

            return _json_ok("Available employees fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching available employees")
            return _json_err(str(e), 500)

    @http.route("/api/appointment/available_slots", type="http", auth="public", methods=["GET"], csrf=False)
    def get_available_slots(self, **kwargs):
        """
        Get available time slots for a given employee on a specific date.
        Example:
            /api/appointment/available_slots?employee_id=12&date=2025-11-10
        """
        try:
            employee_id = kwargs.get("employee_id")
            date_str = kwargs.get("date")

            if not employee_id:
                return _json_err("Missing employee_id")
            if not date_str:
                return _json_err("Missing date (format: YYYY-MM-DD)")

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return _json_err("Invalid date format. Expected YYYY-MM-DD")

            employee = request.env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                return _json_err(f"Employee with ID {employee_id} not found")

            Slot = request.env["appointment.employee.slot"].sudo()

            slots = Slot.search([
                ("employee_id", "=", employee.id),
                ("date", "=", date_obj),
                ("state", "=", "draft")
            ], order="time asc")

            data = []
            for s in slots:
                hour = int(s.time)
                minute = int(round((s.time - hour) * 60))
                time_str = f"{hour:02d}:{minute:02d}"

                data.append({
                    "slot_id": s.id,
                    "employee_id": s.employee_id.id,
                    "employee_name": s.employee_id.name,
                    "date": str(s.date),
                    "time": s.time,
                    "time_str": time_str,
                    "state": s.state,
                })

            return _json_ok("Available slots fetched successfully", data)

        except Exception as e:
            _logger.exception("Error fetching available slots")
            return _json_err(str(e), 500)

    @http.route("/api/appointment/book", type="http", auth="public", methods=["POST"], csrf=False)
    def create_appointment(self, **kwargs):
        """
        Create new appointment (book a slot)
        JSON Body Example:
        {
            "employee_id": 12,
            "slot_id": 210,
            "date": "2025-11-10",
            "branch_id": 1,
            "product_id": 84
        }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            raw_data = request.httprequest.data or b"{}"
            payload = json.loads(raw_data.decode("utf-8"))

            employee_id = payload.get("employee_id")
            slot_id = payload.get("slot_id")
            date_str = payload.get("date")
            branch_id = payload.get("branch_id")
            product_id = payload.get("product_id")

            if not employee_id:
                return _json_err("Missing employee_id")
            if not slot_id:
                return _json_err("Missing slot_id")
            if not date_str:
                return _json_err("Missing date (format: YYYY-MM-DD)")

            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                return _json_err("Invalid date format. Expected YYYY-MM-DD")

            Employee = request.env["hr.employee"].sudo().browse(int(employee_id))
            if not Employee.exists():
                return _json_err(f"Employee with ID {employee_id} not found")

            Slot = request.env["appointment.employee.slot"].sudo().browse(int(slot_id))
            if not Slot.exists():
                return _json_err(f"Slot with ID {slot_id} not found")

            if Slot.state != "draft":
                return _json_err("This slot is not available for booking")

            Branch = request.env["res.company"].sudo().browse(int(branch_id)) if branch_id else None
            Product = request.env["product.product"].sudo().browse(int(product_id)) if product_id else None

            price_unit = 0.0
            if Product and hasattr(Product, "list_price"):
                price_unit = Product.list_price

            Appointment = request.env["appointment.management"].sudo().create({
                "partner_id": partner.id,
                "employee_id": Employee.id,
                "date": date_obj,
                "branch_id": Branch.id if Branch else False,
                "product_id": Product.id if Product else False,
                "price_unit": price_unit,
                "state": "2",  # approved
                "notes": f"Created via API by {partner.name} at {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            })

            Appointment.write({
                "slot_ids": [(4, Slot.id)]
            })

            # Slot.write({"state": "wait","date": date_obj})
            Slot.write({"state": "draft","date": date_obj})

            if Product:
                SaleOrderLine = request.env["sale.order.line"].sudo().search([
                    ("order_partner_id", "=", partner.id),
                    ("product_id", "=", Product.id),
                    ("is_scheduled", "=", False),
                ], limit=1, order="id desc")

                if SaleOrderLine:
                    SaleOrderLine.write({"is_scheduled": True})

            return _json_ok("Appointment booked successfully", {
                "appointment_id": Appointment.id,
                "partner_id": partner.id,
                "partner_name": partner.name,
                "employee": Employee.name,
                "slot_name": Slot.name,
                "date": str(Appointment.date),
                "state": Appointment.state,
            })

        except Exception as e:
            _logger.exception("Error creating appointment via API")
            return _json_err(str(e), 500)

    @http.route("/api/appointment/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_appointment_history(self, **kwargs):
        """
        Get the appointment history for the partner based on the token, including slot_ids.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            appointments = request.env["appointment.management"].sudo().search([
                ("partner_id", "=", partner.id),("state","in", ["2","3"])
            ])

            data = []
            for appointment in appointments:
                slot_ids = appointment.slot_ids.mapped("id")

                data.append({
                    "appointment_id": appointment.id,
                    "employee_id": appointment.employee_id.id,
                    "employee_name": appointment.employee_id.name,
                    "product_id": appointment.product_id.id,
                    "product_name": appointment.product_id.name,
                    "date": str(appointment.date),
                    "state": appointment.state,
                    "price_unit": appointment.price_unit,
                    "notes": appointment.notes,
                    "branch_id": appointment.branch_id.id if appointment.branch_id else None,
                    "branch_name": appointment.branch_id.name if appointment.branch_id else "",
                    "slot_ids": slot_ids,
                })

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