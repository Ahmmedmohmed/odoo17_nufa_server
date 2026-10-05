# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _empty_row():
    return {
        'services_count': 0,
        'products_sales': 0.0,
        'inside_revenue': 0.0,
        'outside_revenue': 0.0,
        'services_cost': 0.0,
        'products_cost': 0.0,
        'commission_calc': 0.0,
        'commission_posted': 0.0,
    }


class AppointmentEmployeeReportWizard(models.TransientModel):
    _name = 'appointment.employee.report.wizard'
    _description = 'Employee Revenue / Expenses / Commission Report'

    date_from = fields.Date(
        string='Date From (من تاريخ)', required=True,
        default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        string='Date To (إلى تاريخ)', required=True,
        default=fields.Date.today)
    branch_ids = fields.Many2many(
        'res.company', string='Branches (الفروع)',
        help="Leave empty to include all branches you currently have access to.")
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees (الموظفين)',
        domain=[('is_appointment_employee', '=', True)],
        help="Leave empty to include all employees.")
    show_empty = fields.Boolean(
        string='Show employees without activity (إظهار الموظفين بدون نشاط)')
    line_ids = fields.One2many(
        'appointment.employee.report.line', 'wizard_id', string='Lines')

    # ------------------------------------------------------------------
    def _utc_range(self):
        """حدود الفترة بتوقيت المستخدم محوّلة لـ UTC (لأن تاريخ الحجز بيتخزن UTC)."""
        tz = ZoneInfo(self.env.user.tz or 'Asia/Riyadh')
        utc = ZoneInfo('UTC')
        start = datetime.combine(self.date_from, time.min).replace(tzinfo=tz)
        end = datetime.combine(self.date_to, time.max).replace(tzinfo=tz)
        return (start.astimezone(utc).replace(tzinfo=None),
                end.astimezone(utc).replace(tzinfo=None))

    def action_generate(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("'Date From' must be before 'Date To'."))

        start, end = self._utc_range()
        companies = self.branch_ids or self.env.companies
        emp_filter = self.employee_ids.ids
        data = defaultdict(_empty_row)

        # ── 1) الخدمات المكتملة: الإيراد + تكلفة الخدمة + تكلفة المنتجات + العمولة المحسوبة
        domain = [
            ('state', '=', '3'),
            ('date', '>=', start),
            ('date', '<=', end),
            ('branch_id', 'in', companies.ids),
        ]
        if emp_filter:
            domain.append(('employee_id', 'in', emp_filter))
        appointments = self.env['appointment.management'].sudo().search(domain)
        for appt in appointments:
            appt = appt.with_company(appt.company_id)
            row = data[appt.employee_id.id]
            price = appt._get_effective_price()
            row['services_count'] += 1
            if appt.appointment_type == 'outside':
                row['outside_revenue'] += price
            else:
                row['inside_revenue'] += price
            row['services_cost'] += appt.product_id.standard_price
            row['products_cost'] += appt._get_service_cost()
            row['commission_calc'] += appt._compute_commission_amount()

        # ── 2) العمولة المسجّلة فعلاً في محفظة الموظف (الموجب فقط، بدون السحب)
        cl_domain = [
            ('commission_employee_id', '!=', False),
            ('amount', '>', 0),
            ('date', '>=', start),
            ('date', '<=', end),
            ('company_id', 'in', companies.ids),
        ]
        if emp_filter:
            cl_domain.append(('commission_employee_id', 'in', emp_filter))
        grouped = self.env['pos.sales.commission.line'].sudo()._read_group(
            cl_domain, ['commission_employee_id'], ['amount:sum'])
        for employee, total in grouped:
            data[employee.id]['commission_posted'] += total

        # ── 3) مبيعات المنتجات من الكاشير (غير الخدمات) لكل موظف
        PosLine = self.env['pos.order.line'].sudo()
        by_employee = 'employee_id' in self.env['pos.order']._fields  # pos_hr
        pos_domain = [
            ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
            ('order_id.date_order', '>=', start),
            ('order_id.date_order', '<=', end),
            ('order_id.company_id', 'in', companies.ids),
            ('product_id.is_appointment_service', '=', False),
            ('product_id.is_appointment_package', '=', False),
        ]
        if 'appointment_id' in PosLine._fields:
            pos_domain.append(('appointment_id', '=', False))
        user_map = {}
        if not by_employee:
            user_map = {
                e.user_id.id: e.id
                for e in self.env['hr.employee'].sudo().search([('user_id', '!=', False)])
            }
        for line in PosLine.search(pos_domain):
            order = line.order_id
            emp_id = order.employee_id.id if by_employee else user_map.get(order.user_id.id)
            if not emp_id or (emp_filter and emp_id not in emp_filter):
                continue
            data[emp_id]['products_sales'] += line.price_subtotal

        # ── 4) إظهار الموظفين اللي ملهمش نشاط (اختياري)
        if self.show_empty:
            emp_domain = [('id', 'in', emp_filter)] if emp_filter else [('is_appointment_employee', '=', True)]
            for emp in self.env['hr.employee'].sudo().search(emp_domain):
                data[emp.id]  # noqa: يكفي الوصول عشان يتكوّن الصف

        # ── 5) إنشاء السطور
        vals_list = []
        for emp_id, r in data.items():
            total_revenue = r['products_sales'] + r['inside_revenue'] + r['outside_revenue']
            total_expenses = r['services_cost'] + r['products_cost']
            vals_list.append({
                'wizard_id': self.id,
                'employee_id': emp_id,
                'services_count': r['services_count'],
                'products_sales': r['products_sales'],
                'inside_revenue': r['inside_revenue'],
                'outside_revenue': r['outside_revenue'],
                'total_revenue': total_revenue,
                'services_cost': r['services_cost'],
                'products_cost': r['products_cost'],
                'total_expenses': total_expenses,
                'commission_calc': r['commission_calc'],
                'commission_posted': r['commission_posted'],
                'net_profit': total_revenue - total_expenses - r['commission_calc'],
            })
        self.line_ids.unlink()
        self.env['appointment.employee.report.line'].create(vals_list)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Employee Report (%(f)s → %(t)s)', f=self.date_from, t=self.date_to),
            'res_model': 'appointment.employee.report.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', self.id)],
            'target': 'current',
        }


class AppointmentEmployeeReportLine(models.TransientModel):
    _name = 'appointment.employee.report.line'
    _description = 'Employee Report Line'
    _order = 'net_profit desc, employee_id'

    wizard_id = fields.Many2one(
        'appointment.employee.report.wizard', ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee (الموظف)')
    services_count = fields.Integer(string='Services (عدد الخدمات)')
    products_sales = fields.Float(string='Products Sales (إيراد مبيعات المنتجات)')
    inside_revenue = fields.Float(string='Inside Services (إيراد الخدمات داخل الصالون)')
    outside_revenue = fields.Float(string='Outside Services (إيراد الخدمات الخارجية)')
    total_revenue = fields.Float(string='Total Revenue (إجمالي الإيراد)')
    services_cost = fields.Float(string='Services Cost (تكلفة الخدمات)')
    products_cost = fields.Float(string='Products Cost (تكلفة المنتجات)')
    total_expenses = fields.Float(string='Expenses (إجمالي المصروفات)')
    commission_calc = fields.Float(string='Commission (العمولة)')
    commission_posted = fields.Float(string='Commission in Wallet (المسجّل بالمحفظة)')
    net_profit = fields.Float(string='Net (الصافي)')