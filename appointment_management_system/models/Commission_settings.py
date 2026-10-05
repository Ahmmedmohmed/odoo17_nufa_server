# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

DEFAULT_COMMISSION_FORMULA = '(price - cost) * (percentage / 100.0)'


class ResCompany(models.Model):
    _inherit = 'res.company'

    commission_calc_mode = fields.Selection(
        [
            ('service', 'Per-Service Percentage (نسبة كل خدمة)'),
            ('formula', 'Dynamic Formula (معادلة مرنة)'),
        ],
        string='Commission Calculation',
        default='service',
        required=True,
    )
    commission_formula = fields.Char(
        string='Commission Formula',
        default=DEFAULT_COMMISSION_FORMULA,
    )

    @api.constrains('commission_calc_mode', 'commission_formula')
    def _check_commission_formula(self):
        for company in self:
            if company.commission_calc_mode != 'formula':
                continue
            formula = (company.commission_formula or '').strip()
            if not formula:
                raise ValidationError(_("Please enter a commission formula."))
            try:
                float(safe_eval(formula, {'price': 100.0, 'cost': 10.0, 'percentage': 10.0}))
            except Exception as e:
                raise ValidationError(_(
                    "Invalid commission formula: %(err)s\n"
                    "Allowed variables: price, cost, percentage",
                    err=e,
                ))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    commission_calc_mode = fields.Selection(
        related='company_id.commission_calc_mode', readonly=False)

    commission_formula = fields.Char(
        related='company_id.commission_formula', readonly=False)

    # 🚀 الحقل الجديد للقوالب الجاهزة 🚀
    formula_template = fields.Selection([
        ('net', 'العمولة على الصافي (السعر - التكلفة)'),
        ('gross', 'العمولة على الإجمالي (السعر بالكامل)'),
        ('net_fixed', 'العمولة على الصافي + 50 ريال ثابتة'),
        ('custom', 'كتابة معادلة مخصصة (Custom)'),
    ], string="قوالب جاهزة (Templates)", default='custom')

    # 🚀 الدالة التي تكتب المعادلة تلقائياً عند تغيير القالب 🚀
    @api.onchange('formula_template')
    def _onchange_formula_template(self):
        if self.formula_template == 'net':
            self.commission_formula = "(price - cost) * (percentage / 100.0)"
        elif self.formula_template == 'gross':
            self.commission_formula = "price * (percentage / 100.0)"
        elif self.formula_template == 'net_fixed':
            self.commission_formula = "(price - cost) * (percentage / 100.0) + 50.0"
        elif self.formula_template == 'custom':
            pass  # يترك الحقل للمستخدم ليكتب ما يريد