# -*- coding: utf-8 -*-

from odoo import models, fields


class HrContract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    att_policy_id = fields.Many2one('hr.attendance.policy', string='Attendance Policy')
    allowances = fields.Monetary('Allowances', required=True, tracking=True, help="Employee's monthly Allowances.")
    insurance_salary = fields.Monetary('Insurance Salary', required=False, tracking=True)

    def _compute_employee_taxes(self, contract_id, tax_base=0):
        # Get the contract object
        contract_obj = self.env['hr.contract'].sudo().search([('id', '=', contract_id)])

        # Calculate income and tax related values
        monthly_gross_income = (
                contract_obj.insurance_salary + contract_obj.allowances) if contract_obj.insurance_salary > 0 else (
                contract_obj.wage + contract_obj.allowances)
        annual_gross_income = monthly_gross_income * 12
        social_insurance_amount = contract_obj.insurance_salary if contract_obj.insurance_salary > 0 else \
            (contract_obj.wage + (contract_obj.allowances * 0.7))
        annual_social_insurance = social_insurance_amount * 12 * 0.11 if social_insurance_amount <= 12600 else \
            12600 * 12 * 0.11
        personal_tax_exemption = 15000 + 9000

        if tax_base > 0:
            annual_tax_base = tax_base * 12
        else:
            annual_tax_base = (annual_gross_income - annual_social_insurance - personal_tax_exemption)

        # Calculate tax amount based on different income ranges
        if annual_tax_base <= 21000:
            annual_tax_amount = 0
        elif annual_tax_base <= 30000:
            annual_tax_amount = (annual_tax_base - 21000) * 0.025
        elif annual_tax_base <= 45000:
            annual_tax_amount = (annual_tax_base - 30000) * 0.10 + 225
        elif annual_tax_base <= 60000:
            annual_tax_amount = (annual_tax_base - 45000) * 0.15 + (225 + 1500)
        elif annual_tax_base <= 200000:
            annual_tax_amount = (annual_tax_base - 60000) * 0.20 + (225 + 1500 + 2250)
        elif annual_tax_base <= 400000:
            annual_tax_amount = (annual_tax_base - 200000) * 0.225 + (225 + 1500 + 2250 + 28000)
        elif annual_tax_base <= 600000:
            annual_tax_amount = (annual_tax_base - 400000) * 0.25 + (225 + 1500 + 2250 + 28000 + 45000)
        elif annual_tax_base <= 700000:
            annual_tax_amount = (annual_tax_base - 400000) * 0.25 + (750 + 1500 + 2250 + 28000 + 45000)
        elif annual_tax_base <= 800000:
            annual_tax_amount = (annual_tax_base - 400000) * 0.25 + (4500 + 2250 + 28000 + 45000)
        elif annual_tax_base <= 900000:
            annual_tax_amount = (annual_tax_base - 400000) * 0.25 + (9000 + 28000 + 45000)
        elif annual_tax_base <= 1200000:
            annual_tax_amount = (annual_tax_base - 400000) * 0.25 + 85000
        else:
            annual_tax_amount = (annual_tax_base - 1200000) * 0.275 + 300000

        # Calculate monthly taxes amount
        employee_social_insurance = annual_social_insurance / 12
        company_social_insurance = social_insurance_amount * 0.1875 if social_insurance_amount <= 12600 else \
            12600 * 0.1875
        monthly_tax_amount = annual_tax_amount / 12

        return [employee_social_insurance, company_social_insurance, monthly_tax_amount]
