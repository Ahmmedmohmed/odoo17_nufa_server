# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    credit_limit_loan = fields.Float("Loan Credit Limit")
    credit_limit_advance = fields.Float("Advance Credit Limit")
    total_loans = fields.Float(string="Total Loans", compute="_compute_total_loans")
    remaining_loans = fields.Float(string="Remaining Loans", compute="_compute_total_loans")
    paid_loans = fields.Float(string="Paid Loans", compute="_compute_total_loans")
    total_advances = fields.Float(string="Total Advances", compute="_compute_total_loans")
    remaining_advances = fields.Float(string="Remaining Advances", compute="_compute_total_loans")
    paid_advances = fields.Float(string="Paid Advances", compute="_compute_total_loans")
    loan_and_advance_user = fields.Many2one("res.users", string="Advance  and Loan User",  required=False,
                              default=lambda self: self.env.user )


    @api.constrains("credit_limit_loan")
    def _check_credit_limit_loan(self):
        for employee in self:
            if employee.credit_limit_loan < 0:
                raise ValidationError(_("Credit Limit Loan must be greater than or equal to zero"))

    @api.constrains("credit_limit_advance")
    def _check_credit_limit_advance(self):
        for employee in self:
            if employee.credit_limit_advance < 0:
                raise ValidationError(_("Credit Limit Advance must be greater than or equal to zero"))

    def _compute_total_loans(self):
        hr_loan_obj = self.sudo().env["hr.loan"]
        for employee in self:
            total_loans = 0
            remaining_loans = 0
            paid_loans = 0
            total_advances = 0
            remaining_advances = 0
            paid_advances = 0

            loans = hr_loan_obj.search([("employee_id", "=", employee.id), ("done_state", "=", "approve"),
                                        ("complete_disbursement", "=", True)])

            for loan in loans:
                if loan.type == "loan":
                    total_loans += loan.amount
                    remaining_loans += loan.total_remaining
                    paid_loans += loan.total_paid
                else:
                    total_advances += loan.amount
                    remaining_advances += loan.total_remaining
                    paid_advances += loan.total_paid

            employee.total_loans = total_loans
            employee.remaining_loans = remaining_loans
            employee.paid_loans = paid_loans
            employee.total_advances = total_advances
            employee.remaining_advances = remaining_advances
            employee.paid_advances = paid_advances
