# -*- coding: utf-8 -*-
from odoo import models, fields, api
import datetime
from dateutil.relativedelta import relativedelta

# 1. إضافة الموظف (مقدم الخدمة) لسطر أمر البيع
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    employee_id = fields.Many2one('hr.employee', string='Service Provider')


# 2. إضافة مرجع أمر البيع في جدول العمولات عشان نعرف الفلوس جاية منين
class PosSalesCommissionLine(models.Model):
    _inherit = 'pos.sales.commission.line'

    src_sale_order_id = fields.Many2one('sale.order', string='Source Sale Order')


# 3. ماكينة حساب العمولة عند تأكيد أمر البيع
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def get_provider_commission(self):
        """ حساب عمولة الموظفين في أمر البيع بناءً على المصفوفة """
        provider_commissions = {}
        for line in self.order_line:
            if line.employee_id and line.price_subtotal > 0:
                # البحث عن نسبة الموظف في هذه الخدمة
                rate = self.env['employee.service.commission'].search([
                    ('employee_id', '=', line.employee_id.id),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if rate and rate.commission_percentage > 0:
                    amount = (line.price_subtotal * rate.commission_percentage) / 100
                    provider_commissions[line.employee_id] = provider_commissions.get(line.employee_id, 0.0) + amount

        return provider_commissions

    def _action_confirm(self):
        """ اعتراض دالة التأكيد لإنشاء العمولة """
        res = super(SaleOrder, self)._action_confirm()

        # التأكد من إعدادات الشركة (متى يتم الدفع؟)
        when_to_pay = self.env.user.company_id.when_to_pay
        if when_to_pay == 'sales_confirm':
            for order in self:
                provider_commissions = order.get_provider_commission()

                for employee, amount in provider_commissions.items():
                    if amount > 0:
                        # البحث عن محفظة مفتوحة للموظف في هذا الشهر
                        commission = self.env['pos.sales.commission'].search([
                            ('commission_employee_id', '=', employee.id),
                            ('start_date', '<=', order.date_order),
                            ('end_date', '>=', order.date_order),
                            ('state', '=', 'draft'),
                            ('company_id', '=', order.company_id.id),
                        ], limit=1)

                        # إنشاء محفظة جديدة إذا لم تكن موجودة
                        if not commission:
                            today = fields.Date.today()
                            first_day = today.replace(day=1)
                            last_day = datetime.datetime(today.year, today.month, 1) + relativedelta(months=1, days=-1) + datetime.timedelta(hours=23, minutes=59, seconds=59)

                            commission = self.env['pos.sales.commission'].create({
                                'start_date': first_day,
                                'end_date': last_day,
                                'commission_employee_id': employee.id,
                                'company_id': order.company_id.id,
                                'currency_id': order.company_id.currency_id.id,
                            })

                        # تسجيل العملية في سطور العمولة
                        commission_product = self.env['product.product'].search([('pos_is_commission_product', '=', 1)], limit=1)
                        self.env['pos.sales.commission.line'].create({
                            'commission_employee_id': employee.id,
                            'amount': amount,
                            'origin': order.name,
                            'type': 'service_provider',
                            'product_id': commission_product.id if commission_product else False,
                            'date': order.date_order,
                            'src_sale_order_id': order.id, # الربط بأمر البيع
                            'sales_commission_id': commission.id,
                            'company_id': order.company_id.id,
                            'currency_id': order.company_id.currency_id.id,
                        })
        return res