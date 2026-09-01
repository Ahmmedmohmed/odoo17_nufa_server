from odoo import http
from odoo.http import request, Response
import jwt
import logging
import json
from datetime import datetime

from .api import _json_ok, _json_err
import pytz
from datetime import datetime
SECRET_KEY = "bcf2e5f933a069b6d737d5cc0a7af01b"
_logger = logging.getLogger(__name__)


def _partner_from_token():
    """Authenticate user from JWT Bearer token."""
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


def _get_product_type(product):
    """Determine if product is a service, combo, or regular product."""
    if not product:
        return "unknown"

    # Check if it's a service
    if product.detailed_type == 'service' or product.type == 'service':
        # Check if it's a combo (has combo lines or is marked as combo)
        if hasattr(product, 'is_combo') and product.is_combo:
            return "combo"
        if hasattr(product, 'combo_ids') and product.combo_ids:
            return "combo"
        return "service"

    # Check for consu (consumable) or product (storable)
    if product.detailed_type in ['consu', 'product'] or product.type in ['consu', 'product']:
        return "product"

    return "product"


def _get_product_image_url(product):
    """Get product image URL."""
    if product and product.id:
        return f"/web/image/product.product/{product.id}/image_256"
    return ""


def _get_employee_image_url(employee):
    """Get employee image URL."""
    if employee and employee.id:
        return f"/web/image/hr.employee/{employee.id}/image_256"
    return ""


class PaymentHistoryApiController(http.Controller):


    @http.route("/api/customer/payment/history", type="http", auth="public", methods=["GET"], csrf=False)
    def get_payment_history(self, **kwargs):
        """
        Get customer payment transaction history (POS, Online, and Wallet only) with Saudi Timezone.
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            # Parse query parameters
            limit = int(kwargs.get("limit", 50))
            offset = int(kwargs.get("offset", 0))
            payment_type = kwargs.get("payment_type", "all")  # 'all', 'pos', 'online', 'wallet'
            date_from = kwargs.get("date_from")
            date_to = kwargs.get("date_to")

            # Validate limit
            if limit > 100:
                limit = 100
            if limit < 1:
                limit = 50

            all_payments = []

            # 1. جلب مدفوعات الكاشير (POS Payments)
            if payment_type in ["all", "pos"]:
                pos_payments = self._get_pos_payments(partner, date_from, date_to)
                all_payments.extend(pos_payments)

            # 2. جلب المدفوعات الإلكترونية (Online Payments)
            if payment_type in ["all", "online"]:
                online_payments = self._get_online_payment_transactions(partner, date_from, date_to)
                all_payments.extend(online_payments)

            # 3. جلب مدفوعات المحفظة (Wallet Payments)
            if payment_type in ["all", "wallet"]:
                wallet_payments = self._get_wallet_payments(partner, date_from, date_to)
                all_payments.extend(wallet_payments)

            # -------------------------------------------------------------
            # --- السحر هنا: فلتر تحويل كل الأوقات لتوقيت السعودية (الرياض) ---
            # -------------------------------------------------------------
            saudi_tz = pytz.timezone('Asia/Riyadh')

            for payment in all_payments:
                # أ. تحويل وقت الدفعة الأساسي
                date_str = payment.get("date")
                if date_str and len(date_str) > 10:  # نتأكد إنه تاريخ ووقت مش تاريخ بس
                    try:
                        dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
                        saudi_dt = pytz.utc.localize(dt).astimezone(saudi_tz)
                        payment["date"] = saudi_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass  # لو حصل خطأ في الفورمات، سيبه زي ما هو

                # ب. تحويل وقت الطلب الداخلي (لو موجود جوه تفاصيل الطلب)
                order_details = payment.get("order_details")
                if order_details:
                    # بنشوف هل الوقت متسجل باسم date_order ولا date
                    order_date_key = "date_order" if "date_order" in order_details else "date"
                    order_date_str = order_details.get(order_date_key)

                    if order_date_str and len(order_date_str) > 10:
                        try:
                            dt_order = datetime.strptime(order_date_str[:19], '%Y-%m-%d %H:%M:%S')
                            saudi_dt_order = pytz.utc.localize(dt_order).astimezone(saudi_tz)
                            order_details[order_date_key] = saudi_dt_order.strftime('%Y-%m-%d %H:%M:%S')
                        except Exception:
                            pass
            # -------------------------------------------------------------

            # ترتيب المدفوعات من الأحدث للأقدم (هتترتب صح لأن الفورمات بتاعنا ثابت YYYY-MM-DD)
            all_payments.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Get total count before pagination
            total_count = len(all_payments)

            # Apply pagination
            paginated_payments = all_payments[offset:offset + limit]

            return _json_ok(
                "Payment history retrieved successfully",
                data={
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "payments": paginated_payments
                }
            )

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.exception("Error fetching payment history: %s", e)
            return _json_err(str(e), status=500)

    def _get_wallet_payments(self, partner, date_from=None, date_to=None):
        """Get wallet payment transactions for the partner with order overview only."""
        payments = []
        try:
            # التأكد من وجود موديل المحفظة عشان الكود ما يضربش
            if "wallet.transaction" not in request.env:
                return payments

            WalletTx = request.env["wallet.transaction"].sudo()

            # جلب العمليات الخاصة بالعميل (سحب/دفع فقط)
            domain = [
                ("partner_id", "=", partner.id),
                # لو الموديول بتاعك بيسجل نوع العملية، ممكن نزود شرط هنا زي ("type", "=", "debit")
            ]

            if date_from:
                domain.append(("create_date", ">=", date_from))
            if date_to:
                domain.append(("create_date", "<=", date_to + " 23:59:59"))

            transactions = WalletTx.search(domain, order="create_date desc")

            for txn in transactions:
                order_details = None
                branch = None

                # محاولة جلب بيانات طلب البيع المرتبط بدفعة المحفظة
                if hasattr(txn, 'sale_order_id') and txn.sale_order_id:
                    sale_order = txn.sale_order_id
                    order_details = {
                        "order_id": sale_order.id,
                        "order_name": sale_order.name or "",
                        "date_order": str(sale_order.date_order)[:19] if sale_order.date_order else "",
                        "amount_total": sale_order.amount_total,
                        "amount_tax": sale_order.amount_tax,
                        "state": sale_order.state,
                    }
                    branch = self._get_branch_details(sale_order.company_id)

                # تحديد المبلغ (أحياناً بيكون مسجل بالسالب لو خصم، فبناخد القيمة المطلقة)
                txn_amount = 0.0
                if hasattr(txn, 'amount'):
                    txn_amount = abs(txn.amount)

                payments.append({
                    "id": txn.id,
                    "type": "wallet_payment",
                    "reference": txn.reference or "",
                    "date": str(txn.create_date)[:19] if txn.create_date else "",
                    "amount": txn_amount,
                    "currency": partner.currency_id.name if partner.currency_id else "SAR",
                    "state": txn.state if hasattr(txn, 'state') else "done",
                    "provider": "E-Wallet",  # اسم البوابة عشان الفرونت اند يفرقها
                    "order_details": order_details,
                    "items": [],  # راجعة فاضية زي ما طلبت عشان الداتا تكون خفيفة
                    "branch": branch,
                })

        except Exception as e:
            _logger.warning("Error fetching wallet transactions: %s", e)

        return payments
    def _get_account_payments(self, partner, date_from=None, date_to=None):
        """Get account.payment records for the partner with invoice/order details."""
        payments = []
        try:
            AccountPayment = request.env["account.payment"].sudo()

            domain = [
                ("partner_id", "=", partner.id),
                ("state", "in", ["posted", "sent", "reconciled"])
            ]

            if date_from:
                domain.append(("date", ">=", date_from))
            if date_to:
                domain.append(("date", "<=", date_to))

            account_payments = AccountPayment.search(domain, order="date desc")

            for payment in account_payments:
                # Get related invoice details
                invoice_details = []
                order_details = None
                items = []

                # Try to get related invoices
                if hasattr(payment, 'reconciled_invoice_ids') and payment.reconciled_invoice_ids:
                    for invoice in payment.reconciled_invoice_ids:
                        invoice_details.append({
                            "id": invoice.id,
                            "name": invoice.name or "",
                            "amount_total": invoice.amount_total,
                            "state": invoice.state,
                        })

                        # Get invoice lines for items
                        for line in invoice.invoice_line_ids:
                            product = line.product_id
                            if product:
                                items.append({
                                    "id": line.id,
                                    "product_id": product.id,
                                    "product_name": product.display_name or product.name or "",
                                    "product_type": _get_product_type(product),
                                    "product_image": _get_product_image_url(product),
                                    "quantity": line.quantity,
                                    "price_unit": line.price_unit,
                                    "price_subtotal": line.price_subtotal,
                                    "discount": line.discount if hasattr(line, 'discount') else 0,
                                })

                # Get branch/company details
                branch = self._get_branch_details(payment.company_id)

                payments.append({
                    "id": payment.id,
                    "type": "account_payment",
                    "name": payment.name or "",
                    "date": str(payment.date) if payment.date else "",
                    "amount": payment.amount,
                    "currency": payment.currency_id.name if payment.currency_id else "SAR",
                    "payment_type": payment.payment_type,
                    "state": payment.state,
                    "payment_method": payment.payment_method_id.name if payment.payment_method_id else "",
                    "journal": payment.journal_id.name if payment.journal_id else "",
                    "memo": payment.ref or "",
                    "invoice_details": invoice_details,
                    "items": items,
                    "branch": branch,
                })

        except Exception as e:
            _logger.warning("Error fetching account payments: %s", e)

        return payments

    def _get_pos_payments(self, partner, date_from=None, date_to=None):
        """Get POS order payments for the partner with full order details."""
        payments = []
        try:
            PosOrder = request.env["pos.order"].sudo()

            domain = [
                ("partner_id", "=", partner.id),
                ("state", "in", ["paid", "done", "invoiced"])
            ]

            if date_from:
                domain.append(("date_order", ">=", date_from))
            if date_to:
                domain.append(("date_order", "<=", date_to + " 23:59:59"))

            pos_orders = PosOrder.search(domain, order="date_order desc")

            for order in pos_orders:
                # Get order line items with product details
                items = []
                employees_data = []

                for line in order.lines:
                    product = line.product_id

                    item_data = {
                        "id": line.id,
                        "product_id": product.id if product else None,
                        "product_name": product.display_name or product.name or "" if product else line.full_product_name or "",
                        "product_type": _get_product_type(product) if product else "unknown",
                        "product_image": _get_product_image_url(product) if product else "",
                        "quantity": line.qty,
                        "price_unit": line.price_unit,
                        "price_subtotal": line.price_subtotal,
                        "price_subtotal_incl": line.price_subtotal_incl,
                        "discount": line.discount,
                        "full_product_name": line.full_product_name or "",
                    }

                    # Check for employee assigned to this line (if exists)
                    if hasattr(line, 'employee_id') and line.employee_id:
                        item_data["employee"] = self._get_employee_details(line.employee_id)
                        employees_data.append(item_data["employee"])

                    items.append(item_data)

                # Get appointments linked to this partner around the order date
                appointments = self._get_related_appointments(partner, order.date_order)

                # If we have appointments, add employee details from there
                for appt in appointments:
                    if appt.get("employee") and appt["employee"] not in employees_data:
                        employees_data.append(appt["employee"])

                # Get branch/company details
                branch = self._get_branch_details(order.company_id)

                # Get session branch if different
                session_branch = None
                if order.session_id and order.session_id.config_id:
                    config = order.session_id.config_id
                    if hasattr(config, 'company_id') and config.company_id:
                        session_branch = self._get_branch_details(config.company_id)

                # Order details
                order_details = {
                    "order_id": order.id,
                    "order_name": order.name or "",
                    "pos_reference": order.pos_reference or "",
                    "date_order": str(order.date_order)[:19] if order.date_order else "",
                    "amount_total": order.amount_total,
                    "amount_tax": order.amount_tax,
                    "amount_paid": order.amount_paid,
                    "amount_return": order.amount_return,
                    "state": order.state,
                    "session_name": order.session_id.name if order.session_id else "",
                    "note": order.note or "" if hasattr(order, 'note') else "",
                }

                # Get payment details from pos.payment
                for pos_payment in order.payment_ids:
                    payments.append({
                        "id": pos_payment.id,
                        "type": "pos_payment",
                        "date": str(order.date_order)[:19] if order.date_order else "",
                        "amount": pos_payment.amount,
                        "currency": order.currency_id.name if order.currency_id else "SAR",
                        "payment_method": pos_payment.payment_method_id.name if pos_payment.payment_method_id else "",
                        "state": order.state,
                        "order_details": order_details,
                        "items": items,
                        "employees": employees_data if employees_data else None,
                        "appointments": appointments if appointments else None,
                        "branch": session_branch or branch,
                    })

        except Exception as e:
            _logger.warning("Error fetching POS payments: %s", e)

        return payments

    def _get_online_payment_transactions(self, partner, date_from=None, date_to=None):
        """Get online payment transactions for the partner with order details."""
        payments = []
        try:
            # Check if payment.transaction model exists
            if "payment.transaction" not in request.env:
                return payments

            PaymentTransaction = request.env["payment.transaction"].sudo()

            domain = [
                ("partner_id", "=", partner.id),
                ("state", "in", ["authorized", "done"])
            ]

            if date_from:
                domain.append(("create_date", ">=", date_from))
            if date_to:
                domain.append(("create_date", "<=", date_to + " 23:59:59"))

            transactions = PaymentTransaction.search(domain, order="create_date desc")

            for txn in transactions:
                # Get related sale order details
                order_details = None
                items = []
                branch = None

                # Try to get linked sale order
                if hasattr(txn, 'sale_order_ids') and txn.sale_order_ids:
                    for sale_order in txn.sale_order_ids:
                        order_details = {
                            "order_id": sale_order.id,
                            "order_name": sale_order.name or "",
                            "date_order": str(sale_order.date_order)[:19] if sale_order.date_order else "",
                            "amount_total": sale_order.amount_total,
                            "amount_tax": sale_order.amount_tax,
                            "state": sale_order.state,
                            "origin": sale_order.origin or "",
                        }

                        # Get order lines
                        for line in sale_order.order_line:
                            product = line.product_id
                            if product:
                                items.append({
                                    "id": line.id,
                                    "product_id": product.id,
                                    "product_name": product.display_name or product.name or "",
                                    "product_type": _get_product_type(product),
                                    "product_image": _get_product_image_url(product),
                                    "quantity": line.product_uom_qty,
                                    "price_unit": line.price_unit,
                                    "price_subtotal": line.price_subtotal,
                                    "discount": line.discount if hasattr(line, 'discount') else 0,
                                })

                        # Get branch from sale order
                        branch = self._get_branch_details(sale_order.company_id)
                        break  # Just get the first order

                # If no sale order, try to get invoice
                if not order_details and hasattr(txn, 'invoice_ids') and txn.invoice_ids:
                    for invoice in txn.invoice_ids:
                        order_details = {
                            "invoice_id": invoice.id,
                            "invoice_name": invoice.name or "",
                            "date": str(invoice.invoice_date) if invoice.invoice_date else "",
                            "amount_total": invoice.amount_total,
                            "state": invoice.state,
                        }

                        for line in invoice.invoice_line_ids:
                            product = line.product_id
                            if product:
                                items.append({
                                    "id": line.id,
                                    "product_id": product.id,
                                    "product_name": product.display_name or product.name or "",
                                    "product_type": _get_product_type(product),
                                    "product_image": _get_product_image_url(product),
                                    "quantity": line.quantity,
                                    "price_unit": line.price_unit,
                                    "price_subtotal": line.price_subtotal,
                                })

                        branch = self._get_branch_details(invoice.company_id)
                        break

                # Get company/branch from transaction if not found
                if not branch and hasattr(txn, 'company_id') and txn.company_id:
                    branch = self._get_branch_details(txn.company_id)

                payments.append({
                    "id": txn.id,
                    "type": "online_payment",
                    "reference": txn.reference or "",
                    "date": str(txn.create_date)[:19] if txn.create_date else "",
                    "amount": txn.amount,
                    "currency": txn.currency_id.name if txn.currency_id else "SAR",
                    "state": txn.state,
                    "provider": txn.provider_id.name if hasattr(txn, 'provider_id') and txn.provider_id else (
                        txn.acquirer_id.name if hasattr(txn, 'acquirer_id') and txn.acquirer_id else ""
                    ),
                    "provider_reference": txn.provider_reference or "" if hasattr(txn, 'provider_reference') else (
                        txn.acquirer_reference or "" if hasattr(txn, 'acquirer_reference') else ""
                    ),
                    "order_details": order_details,
                    "items": items,
                    "branch": branch,
                })

        except Exception as e:
            _logger.warning("Error fetching online payment transactions: %s", e)

        return payments

    def _get_branch_details(self, company):
        """Get branch/company details."""
        if not company:
            return None

        try:
            address_parts = filter(None, [
                company.street,
                company.street2,
                company.city,
                company.state_id.name if company.state_id else "",
                company.country_id.name if company.country_id else "",
            ])

            return {
                "id": company.id,
                "name": company.name or "",
                "address": ", ".join(address_parts),
                "phone": company.phone or "",
                "mobile": company.mobile or "" if hasattr(company, 'mobile') else "",
                "email": company.email or "",
                "vat": company.vat or "",
                "latitude": company.latitude if hasattr(company, 'latitude') else None,
                "longitude": company.longitude if hasattr(company, 'longitude') else None,
                "logo_url": f"/web/image/res.company.py/{company.id}/logo" if company.id else "",
            }
        except Exception as e:
            _logger.warning("Error getting branch details: %s", e)
            return {"id": company.id, "name": company.name or ""} if company else None

    def _get_employee_details(self, employee):
        """Get employee details."""
        if not employee:
            return None

        try:
            return {
                "id": employee.id,
                "name": employee.name or "",
                "job_title": employee.job_title or "",
                "department": employee.department_id.name if employee.department_id else "",
                "work_email": employee.work_email or "",
                "work_phone": employee.work_phone or "",
                "mobile_phone": employee.mobile_phone or "" if hasattr(employee, 'mobile_phone') else "",
                "image_url": _get_employee_image_url(employee),
                "branch": employee.company_id.name if employee.company_id else "",
            }
        except Exception as e:
            _logger.warning("Error getting employee details: %s", e)
            return {"id": employee.id, "name": employee.name or ""} if employee else None

    def _get_related_appointments(self, partner, order_date):
        """Get appointments related to the partner around the order date."""
        appointments = []
        try:
            if "appointment.management" not in request.env:
                return appointments

            Appointment = request.env["appointment.management"].sudo()

            # Search for appointments on the same day
            if order_date:
                date_str = str(order_date)[:10]
                domain = [
                    ("partner_id", "=", partner.id),
                    ("date", ">=", date_str + " 00:00:00"),
                    ("date", "<=", date_str + " 23:59:59"),
                ]

                appts = Appointment.search(domain, limit=10)

                for appt in appts:
                    product = appt.product_id
                    employee = appt.employee_id
                    branch = appt.branch_id

                    appointments.append({
                        "id": appt.id,
                        "sequence": appt.sequence or "",
                        "date": str(appt.date)[:19] if appt.date else "",
                        "appointment_type": appt.appointment_type or "",
                        "state": appt.state or "",
                        "price_unit": appt.price_unit,
                        "notes": appt.notes or "",
                        "service": {
                            "id": product.id if product else None,
                            "name": product.display_name or product.name or "" if product else "",
                            "image_url": _get_product_image_url(product) if product else "",
                        } if product else None,
                        "employee": self._get_employee_details(employee) if employee else None,
                        "branch": self._get_branch_details(branch) if branch else None,
                    })

        except Exception as e:
            _logger.warning("Error getting related appointments: %s", e)

        return appointments

    @http.route("/api/customer/payment/summary", type="http", auth="public", methods=["GET"], csrf=False)
    def get_payment_summary(self, **kwargs):
        """
        Get customer payment summary/statistics.

        Headers:
            Authorization: Bearer <access_token>

        Response:
            {
                "status": "success",
                "message": "Payment summary retrieved successfully",
                "data": {
                    "total_paid": 1500.00,
                    "total_transactions": 10,
                    "by_type": {...},
                    "by_method": {...}
                }
            }
        """
        partner, err = _partner_from_token()
        if err:
            return err

        try:
            total_paid = 0.0
            total_transactions = 0
            by_type = {
                "account_payment": {"count": 0, "amount": 0.0},
                "pos_payment": {"count": 0, "amount": 0.0},
                "online_payment": {"count": 0, "amount": 0.0}
            }
            by_method = {}

            # Account Payments
            account_payments = self._get_account_payments(partner)
            for p in account_payments:
                if p.get("payment_type") == "inbound":
                    total_paid += p.get("amount", 0)
                    total_transactions += 1
                    by_type["account_payment"]["count"] += 1
                    by_type["account_payment"]["amount"] += p.get("amount", 0)

                    method = p.get("payment_method") or "Other"
                    if method not in by_method:
                        by_method[method] = {"count": 0, "amount": 0.0}
                    by_method[method]["count"] += 1
                    by_method[method]["amount"] += p.get("amount", 0)

            # POS Payments
            pos_payments = self._get_pos_payments(partner)
            for p in pos_payments:
                total_paid += p.get("amount", 0)
                total_transactions += 1
                by_type["pos_payment"]["count"] += 1
                by_type["pos_payment"]["amount"] += p.get("amount", 0)

                method = p.get("payment_method") or "Other"
                if method not in by_method:
                    by_method[method] = {"count": 0, "amount": 0.0}
                by_method[method]["count"] += 1
                by_method[method]["amount"] += p.get("amount", 0)

            # Online Payments
            online_payments = self._get_online_payment_transactions(partner)
            for p in online_payments:
                total_paid += p.get("amount", 0)
                total_transactions += 1
                by_type["online_payment"]["count"] += 1
                by_type["online_payment"]["amount"] += p.get("amount", 0)

                method = p.get("provider") or "Online"
                if method not in by_method:
                    by_method[method] = {"count": 0, "amount": 0.0}
                by_method[method]["count"] += 1
                by_method[method]["amount"] += p.get("amount", 0)

            return _json_ok(
                "Payment summary retrieved successfully",
                data={
                    "total_paid": round(total_paid, 2),
                    "total_transactions": total_transactions,
                    "currency": "SAR",
                    "by_type": by_type,
                    "by_method": by_method
                }
            )

        except Exception as e:
            _logger.exception("Error fetching payment summary: %s", e)
            return _json_err(str(e), status=500)
