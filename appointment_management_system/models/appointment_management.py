# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, time
import base64
import logging
import qrcode
from io import BytesIO
from odoo.exceptions import UserError
import random

_logger = logging.getLogger(__name__)

class AppointmentManagement(models.Model):
    _name = 'appointment.management'
    _description = 'Appointment Management'
    _check_company_auto = True
    _rec_name = 'appointment_ref'
    _order = 'id desc'

    appointment_ref = fields.Char(
        'Appointment Reference',
        default=lambda self: _('New'),
        required=True,
        readonly=True,
        copy=False
    )
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    partner_phone = fields.Char(string='Partner Phone', related='partner_id.phone')
    date = fields.Datetime('Date', required=True)
    branch_id = fields.Many2one('res.company', string='Branch', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    product_id = fields.Many2one('product.product', string='Service', domain=[('is_appointment_service', '=', True)], required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', domain=[('is_appointment_employee', '=', True)], required=True)
    price_unit = fields.Float('Unit Price', required=True)
    service_rate = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], string='Rating')
    state = fields.Selection([
        ('1', 'Partial Approved'),
        ('2', 'Approved'),
        ('start', 'In Progress'),
        ('pause', 'Paused'),
        ('3', 'Completed'),
        ('4', 'Cancelled'),
        ('no_show', 'No Show')
    ])
    service_start_time = fields.Datetime(string='Service Start Time', readonly=True)
    service_end_time = fields.Datetime(string='Service End Time', readonly=True)
    service_duration = fields.Char(string='Duration (Minutes)', compute='_compute_service_duration', store=True)
    appointment_type = fields.Selection([
        ('inside', 'Internal Services'),
        ('outside', 'External Services')
    ], string='Appointment Type', default='inside', required=True)
    notes = fields.Text('Notes')
    slot_ids = fields.Many2many('appointment.employee.slot')
    cancelled_at = fields.Datetime('Cancelled At', readonly=True)
    deduction_percentage = fields.Float('Deduction %', readonly=True)
    refund_amount = fields.Float('Refund Amount', readonly=True)
    deduction_amount = fields.Float('Deduction Amount', readonly=True)
    pos_reference = fields.Char(string='POS Receipt Reference')
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    has_sale_order = fields.Boolean(string='Has Sale Order', default=False)
    is_printed = fields.Boolean(string='Is Printed', default=False, readonly=True)

    def action_appointment_cancel(self):
        self.write({'state': '4'})

    def action_admin_refund_exception(self):
        """Admin override: refund the deducted amount back to customer wallet."""
        for appointment in self:
            if appointment.state != '4':
                raise UserError(_('Only cancelled appointments can have a refund exception.'))
            if appointment.deduction_amount <= 0:
                raise UserError(_('No deduction was applied to this appointment.'))

            # Credit the deducted amount back to wallet
            appointment.partner_id.sudo().add_wallet_credit(
                amount=appointment.deduction_amount,
                source_type='refund',
                source_description='Admin exception refund for %s' % appointment.sequence,
                notes='Admin override: deduction of %.2f refunded' % appointment.deduction_amount,
            )

            # Update tracking
            appointment.write({
                'refund_amount': appointment.refund_amount + appointment.deduction_amount,
                'deduction_amount': 0.0,
                'deduction_percentage': 0.0,
            })

    def action_print_ticket(self):
        """دالة تقوم بتغيير الحالة للطباعة واستدعاء التقرير"""
        self.write({'is_printed': True})
        return self.env.ref('appointment_management_system.action_report_appointment_receipt').report_action(self)

    def action_appointment_complate(self):
        # تسجيل وقت الانتهاء فوراً
        self.write({
            'state': '3',
            'service_end_time': fields.Datetime.now()
        })

        if self.env.company.location_dest_id and self.employee_id.location_id and self.env.company.picking_type_id and self.product_id.product_component_ids:
            lines = []
            for record in self.product_id.product_component_ids:
                lines.append((0, 0, {
                    'product_id': record.component_id.id,
                    'name': self.appointment_ref,
                    'product_uom_qty': record.quantity,
                    'location_id': self.employee_id.location_id.id,
                    'location_dest_id': self.env.company.location_dest_id.id
                }))

            self.env['stock.picking'].create({
                'picking_type_id': self.env.company.picking_type_id.id,
                'location_id': self.employee_id.location_id.id,
                'location_dest_id': self.env.company.location_dest_id.id,
                'origin': self.appointment_ref,
                'state': 'confirmed',
                'move_ids_without_package': lines,
            })

    @api.depends('service_start_time', 'service_end_time')
    def _compute_service_duration(self):
        for rec in self:
            if rec.service_start_time and rec.service_end_time:
                delta = rec.service_end_time - rec.service_start_time
                minutes = int(delta.total_seconds() / 60)
                rec.service_duration = f"{minutes} دقيقة"
            else:
                rec.service_duration = "0 دقيقة"

    def action_start_service(self):
        """ زر بدء الخدمة وتسجيل وقت البداية """
        for record in self:
            if record.state != '2':
                raise UserError(_("لا يمكن بدء الخدمة إلا إذا كانت حالة الحجز 'مؤكد'."))
            record.write({
                'state': 'start',
                'service_start_time': fields.Datetime.now()
            })

    @api.model
    def create(self, vals):
        if vals.get('appointment_ref', _('New')) == _('New'):
            vals['appointment_ref'] = self.env['ir.sequence'].next_by_code('appointment.management.sequence') or _('New')

        # Validate slot_ids if provided to prevent foreign key constraint violations
        if 'slot_ids' in vals and vals['slot_ids']:
            slot_commands = vals['slot_ids']
            if isinstance(slot_commands, list):
                valid_slot_ids = []
                for command in slot_commands:
                    if isinstance(command, tuple) and len(command) >= 3:
                        if command[0] == 6:  # (6, 0, [ids]) - replace all
                            slot_ids_to_check = command[2] if command[2] else []
                            existing_slots = self.env['appointment.employee.slot'].search([('id', 'in', slot_ids_to_check)])
                            valid_slot_ids = existing_slots.ids
                            if valid_slot_ids != slot_ids_to_check:
                                vals['slot_ids'] = [(6, 0, valid_slot_ids)]
                        elif command[0] == 4:  # (4, id) - add existing record
                            if self.env['appointment.employee.slot'].browse(command[1]).exists():
                                valid_slot_ids.append(command[1])

        return super(AppointmentManagement, self).create(vals)

    def _create_auto_pos_refund(self, order):
        """دالة لمحاكاة مرتجع الكاشير أوتوماتيكياً بإنشاء فاتورة سالبة ودفعها"""
        session = self.env['pos.session'].sudo().search([
            ('config_id', '=', order.config_id.id),
            ('state', '=', 'opened')
        ], limit=1)

        if not session:
            return False

        refund_lines = []
        refund_total = 0.0
        refund_tax = 0.0

        for line in order.lines.filtered(lambda l: l.appointment_id.id == self.id):
            refund_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'qty': -line.qty,
                'price_unit': line.price_unit,
                'price_subtotal': -line.price_subtotal,
                'price_subtotal_incl': -line.price_subtotal_incl,
                'refunded_orderline_id': line.id,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'is_appointment_line': line.is_appointment_line,
                'appointment_id': line.appointment_id.id,
            }))
            refund_total += -line.price_subtotal_incl
            refund_tax += -(line.price_subtotal_incl - line.price_subtotal)

        if not refund_lines:
            return False

        try:
            dummy_uid = f"{random.randrange(10000, 99999)}-{random.randrange(100, 999)}-{random.randrange(1000, 9999)}"

            refund_order = self.env['pos.order'].sudo().create({
                'session_id': session.id,
                'partner_id': order.partner_id.id,
                'pos_reference': f'Refund {dummy_uid}',
                'lines': refund_lines,
                'amount_total': refund_total,
                'amount_paid': refund_total,
                'amount_tax': refund_tax,
                'amount_return': 0.0,
            })
        except Exception as e:
            _logger.error(f"فشل إنشاء المرتجع الأوتوماتيكي لـ {order.name}: {str(e)}")
            return False

    def write(self, vals):
        if vals.get('state') == 'start':
            vals['service_start_time'] = fields.Datetime.now()
        elif vals.get('state') == '3':
            vals['service_end_time'] = fields.Datetime.now()

        if 'slot_ids' in vals and vals['slot_ids']:
            slot_commands = vals['slot_ids']
            if isinstance(slot_commands, list):
                validated_commands = []
                for command in slot_commands:
                    if isinstance(command, tuple) and len(command) >= 2:
                        if command[0] == 6:
                            slot_ids_to_check = command[2] if len(command) >= 3 and command[2] else []
                            existing_slots = self.env['appointment.employee.slot'].search(
                                [('id', 'in', slot_ids_to_check)])
                            validated_commands.append((6, 0, existing_slots.ids))
                        elif command[0] == 4:
                            if self.env['appointment.employee.slot'].browse(command[1]).exists():
                                validated_commands.append(command)
                        elif command[0] == 3:
                            validated_commands.append(command)
                        elif command[0] == 5:
                            validated_commands.append(command)
                        else:
                            validated_commands.append(command)
                    else:
                        validated_commands.append(command)
                vals['slot_ids'] = validated_commands

        res = super(AppointmentManagement, self).write(vals)

        for record in self:
            # 1. التزامن العكسي للتعديلات
            if any(key in vals for key in ['date', 'employee_id', 'branch_id', 'appointment_type', 'slot_ids']):
                pos_lines = self.env['pos.order.line'].sudo().search([('appointment_id', '=', record.id)])
                if pos_lines:
                    pos_lines.write({
                        'date': str(record.date.date()) if record.date else '',
                        'slot_name': ', '.join(record.slot_ids.mapped('name')) if record.slot_ids else '',
                        'employee_name': record.employee_id.name if record.employee_id else '',
                        'branch_name': record.branch_id.name if record.branch_id else '',
                        'appointment_type': record.appointment_type or '',
                    })

                if 'sale.order.line' in self.env:
                    sale_lines = self.env['sale.order.line'].sudo().search([('appointment_id', '=', record.id)])
                    if sale_lines:
                        sale_vals = {}
                        sol_fields = self.env['sale.order.line']._fields
                        if 'date' in sol_fields: sale_vals['date'] = str(record.date.date()) if record.date else ''
                        if 'slot_name' in sol_fields: sale_vals['slot_name'] = ', '.join(
                            record.slot_ids.mapped('name')) if record.slot_ids else ''
                        if 'employee_name' in sol_fields: sale_vals[
                            'employee_name'] = record.employee_id.name if record.employee_id else ''
                        if 'branch_name' in sol_fields: sale_vals[
                            'branch_name'] = record.branch_id.name if record.branch_id else ''
                        if 'appointment_type' in sol_fields: sale_vals[
                            'appointment_type'] = record.appointment_type or ''

                        if sale_vals:
                            sale_lines.write(sale_vals)

            # 2. التزامن العكسي للحالة (تأكيد، إغلاق، أو إلغاء)
            if 'state' in vals:
                if vals['state'] in ['2', 'start', '3']:
                    if record.slot_ids:
                        record.slot_ids.sudo().write({
                            'state': 'done',
                            'reserved_by': record.id
                        })

                elif vals['state'] == '4':
                    if record.slot_ids:
                        record.slot_ids.sudo().write({
                            'state': 'draft',
                            'reserved_by': False,
                            'reserved_until': False
                        })

                    linked_orders = self.env['pos.order'].sudo().search(
                        [('appointment_id', '=', record.id), ('state', '!=', 'cancel')])
                    for order in linked_orders:
                        if order.state == 'draft':
                            order.action_pos_order_cancel()
                        else:
                            refund_success = record._create_auto_pos_refund(order)

                            if not refund_success:
                                existing_refund = self.env['appointment.refund.request'].sudo().search(
                                    [('appointment_id', '=', record.id)])
                                if not existing_refund:
                                    self.env['appointment.refund.request'].sudo().create({
                                        'appointment_id': record.id,
                                        'refund_amount': record.price_unit,
                                        'refund_method': 'wallet',
                                        'state': 'pending',
                                        'reason': 'لم يتم العثور على جلسة كاشير مفتوحة لإنشاء المرتجع التلقائي.'
                                    })

                    if 'sale.order.line' in self.env:
                        sale_lines = self.env['sale.order.line'].sudo().search([('appointment_id', '=', record.id)])
                        linked_sale_orders = sale_lines.mapped('order_id').filtered(lambda o: o.state != 'cancel')

                        for sale_order in linked_sale_orders:
                            try:
                                sale_order.with_context(disable_cancel_warning=True).action_cancel()
                            except Exception as e:
                                pass

        return res

    zatca_qr_code = fields.Binary(string="ZATCA QR Code", compute="_compute_zatca_qr_code", store=True)

    @api.depends('price_unit', 'date', 'branch_id', 'company_id', 'partner_id')
    def _compute_zatca_qr_code(self):
        for rec in self:
            try:
                seller_name = rec.branch_id.name or rec.company_id.name or "Kaya Clinic"
                vat_no = rec.branch_id.vat or rec.company_id.vat or "312345678901233"
                timestamp = rec.date.isoformat() if rec.date else datetime.now().isoformat()
                total_amount = f"{rec.price_unit:.2f}"
                vat_amount = f"{(rec.price_unit - (rec.price_unit / 1.15)):.2f}"

                def get_tlv_bin(tag, value):
                    value_str = str(value)
                    return bytes([tag]) + bytes([len(value_str.encode('utf-8'))]) + value_str.encode('utf-8')

                tlv_data = (get_tlv_bin(1, seller_name) +
                            get_tlv_bin(2, vat_no) +
                            get_tlv_bin(3, timestamp) +
                            get_tlv_bin(4, total_amount) +
                            get_tlv_bin(5, vat_amount))

                qr_data = base64.b64encode(tlv_data).decode('utf-8')

                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                temp = BytesIO()
                img.save(temp, format="PNG")
                rec.zatca_qr_code = base64.b64encode(temp.getvalue())
            except Exception as e:
                _logger.error("ZATCA QR Error: %s", str(e))
                rec.zatca_qr_code = False

    @api.model
    def get_booking_initial_data(self):
        categories = self.env['pos.category'].search_read(
            [('is_appointment_category', '=', True)],
            ['id', 'name']
        )
        if not categories:
            categories = self.env['pos.category'].search_read([], ['id', 'name'], limit=20)

        for cat in categories:
            cat['image_url'] = f"/web/image?model=pos.category&id={cat['id']}&field=image_128"

        partners = self.env['res.partner'].search_read(
            [('customer_rank', '>', 0)],
            ['id', 'name', 'phone'], limit=100
        )
        if not partners:
            partners = self.env['res.partner'].search_read([], ['id', 'name', 'phone'], limit=50)

        pos_configs = self.env['pos.config'].search([('company_id', 'in', [self.env.company.id, False])])
        valid_pm_ids = pos_configs.mapped('payment_method_ids.id')

        payment_methods = self.env['pos.payment.method'].search_read(
            [('id', 'in', valid_pm_ids), ('active', '=', True)],
            ['id', 'name']
        )

        return {
            'categories': categories,
            'partners': partners,
            'payment_methods': payment_methods,
        }

    @api.model
    def get_category_services(self, category_id=False):
        domain = ['|', ('is_appointment_service', '=', True), ('is_appointment_package', '=', True)]
        if category_id:
            domain = ['&', ('pos_categ_ids', 'in', [int(category_id)])] + domain

        products = self.env['product.product'].search(domain)

        services_data = []
        for p in products:
            services_data.append({
                'id': p.id,
                'name': p.display_name or p.name,
                'price': p.lst_price,
                'is_package': p.is_appointment_package,
                'image_url': f"/web/image?model=product.product&id={p.id}&field=image_128",
            })
        return services_data

    @api.model
    def get_package_services(self, package_id):
        package = self.env['product.product'].browse(int(package_id))
        lines = package.appointment_package_line_ids
        services_data = []
        for line in lines:
            if line.product_id:
                p = line.product_id
                services_data.append({
                    'id': p.id,
                    'name': p.display_name or p.name,
                    'image_url': f"/web/image?model=product.product&id={p.id}&field=image_128",
                })
        return services_data

    @api.model
    def get_employee_available_dates(self, employee_id):
        from datetime import date, timedelta
        today = date.today()
        end_date = today + timedelta(days=60)
        slots = self.env['appointment.employee.slot'].search_read([
            ('employee_id', '=', int(employee_id)),
            ('state', '=', 'draft'),
            ('date', '>=', today),
            ('date', '<=', end_date)
        ], ['date'])
        if not slots: return []
        unique_dates = sorted(list(set(s['date'] for s in slots if s.get('date'))))
        return [{'date': str(d), 'label': str(d)} for d in unique_dates]

    @api.model
    def create_direct_appointment(self, vals):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        partner_id = int(vals.get('partner_id'))
        package_id = int(vals.get('package_id')) if vals.get('package_id') else False
        price = float(vals.get('price', 0.0))
        appointments_data = vals.get('appointments', [])

        if not appointments_data:
            return {'status': 'error', 'message': 'No appointments data provided'}

        payment_method_id = int(vals.get('payment_method_id')) if vals.get('payment_method_id') else False
        journal_id = False
        if payment_method_id:
            pm = self.env['pos.payment.method'].browse(payment_method_id)
            journal_id = pm.journal_id.id if pm.journal_id else False

        sale_product_id = package_id if package_id else int(appointments_data[0]['product_id'])
        # الفرع الفعلي للحجز - لازم الفاتورة والـ sale order ياخدوا نفس company_id بتاعه
        # مش سياق المستخدم اللي بيعمل الحجز، عشان تفعيل فصل بيانات الفروع صح
        appointment_branch_id = int(appointments_data[0].get('branch_id'))
        invoice_id = False
        sale_order = False
        try:
            sale_order = self.env['sale.order'].sudo().with_company(appointment_branch_id).create({
                'partner_id': partner_id,
                'company_id': appointment_branch_id,
                'order_line': [(0, 0, {
                    'product_id': sale_product_id,
                    'product_uom_qty': 1.0,
                    'price_unit': price,
                })]
            })
            sale_order.action_confirm()

            invoice = sale_order._create_invoices()
            invoice.action_post()
            invoice_id = invoice.id

            if journal_id:
                payment_register = self.env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=invoice.ids
                ).create({
                    'journal_id': journal_id,
                    'amount': invoice.amount_residual,
                })
                payment_register._create_payments()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to process billing: {str(e)}")

        created_appointments = []
        first_ref = ""
        user_tz = self.env.user.tz or 'Asia/Riyadh'

        for app_data in appointments_data:
            slot_ids = app_data.get('slot_ids', [])
            if not slot_ids: continue

            slot_obj = self.env['appointment.employee.slot'].browse(slot_ids[0])
            date_obj = datetime.strptime(app_data.get('date'), "%Y-%m-%d").date()
            time_obj = datetime.strptime(slot_obj.name, "%H:%M").time()

            local_dt = datetime.combine(date_obj, time_obj).replace(tzinfo=ZoneInfo(user_tz))
            utc_dt = local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

            app_price = 0.0 if package_id else price

            appointment = self.create({
                'partner_id': partner_id,
                'branch_id': int(app_data.get('branch_id')),
                # company_id لازم يتساوى مع branch_id (الفرع الفعلي)، مش سياق المستخدم
                # اللي بيعمل الحجز، عشان فصل بيانات الفروع يشتغل صح وعشان يتفادى
                # تعارض _check_company_auto مع employee_id / product_id بتوع الفرع
                'company_id': int(app_data.get('branch_id')),
                'product_id': int(app_data.get('product_id')),
                'employee_id': int(app_data.get('employee_id')),
                'date': utc_dt,
                'price_unit': app_price,
                'notes': vals.get('notes', ''),
                'appointment_type': app_data.get('appointment_type', 'inside'),
                'state': '2',
                'slot_ids': [(6, 0, slot_ids)]
            })
            appointment.slot_ids.write({'state': 'done', 'reserved_by': appointment.id})

            if sale_order and hasattr(appointment, 'sale_order_id'):
                appointment.write({'sale_order_id': sale_order.id, 'has_sale_order': True})

            created_appointments.append(appointment)
            if not first_ref:
                first_ref = appointment.appointment_ref

        res_id = created_appointments[0].id if created_appointments else False
        return {'status': 'success', 'res_id': res_id, 'ref': first_ref, 'invoice_id': invoice_id}