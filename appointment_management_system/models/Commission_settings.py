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
        """Test-evaluate the formula on save so a typo can't silently
        zero out every commission later."""
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