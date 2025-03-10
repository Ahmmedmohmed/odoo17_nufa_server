# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HRLoanInstallmentPaymentLineWizard(models.TransientModel):
    _name = "hr.loan.installment.payment.line.wizard"
    _description = "HR Loan Installment Payment Lines Wizard"

    installment_payment_wizard_id = fields.Many2one("hr.loan.installment.payment.wizard",
                                                    string="Installment Payment Wizard", ondelete="cascade",
                                                    required=True)
    loan_installment_line_id = fields.Many2one("hr.loan.installment.line", string="Installment", required=True,
                                               readonly=True)
    remaining_amount = fields.Float(string="Remaining Amount", readonly=True)
    amount = fields.Float(string="Amount", required=True)

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_("Amount must be positive or equal to zero"))


class HRLoanInstallmentPaymentWizard(models.TransientModel):
    _name = "hr.loan.installment.payment.wizard"
    _description = "HR Loan Installment Payment Wizard"

    amount = fields.Float(string="Amount", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one("account.journal", string="Journal", required=True,
                                 domain=[("type", "in", ["bank", "cash"])])
    line_ids = fields.One2many("hr.loan.installment.payment.line.wizard", "installment_payment_wizard_id",
                               string="Lines")

    @api.constrains("amount")
    def _check_amount(self):
        if self.amount <= 0:
            raise ValidationError(_("Amount must be positive"))

    @api.onchange("amount")
    def onchange_amount(self):
        loan = self.env["hr.loan"].search([("id", "=", self._context["active_id"])])
        self.line_ids = False
        total_remaining = self.amount
        lines = []
        for loan_installment_line in loan.mapped("line_ids").filtered(lambda l: not l.is_paid):
            if total_remaining == 0:
                lines.append((0, 0, {
                    "loan_installment_line_id": loan_installment_line.id,
                    "remaining_amount": loan_installment_line.remaining_amount,
                    "amount": 0}))
            else:
                amount = total_remaining > loan_installment_line.remaining_amount and loan_installment_line.remaining_amount or total_remaining
                total_remaining -= amount

                lines.append((0, 0, {
                    "loan_installment_line_id": loan_installment_line.id,
                    "remaining_amount": loan_installment_line.remaining_amount,
                    "amount": amount}))

        if lines:
            self.line_ids = lines

    def _prepare_account_payment(self, loan):
        loan_installment_lines = []
        for line in self.line_ids:
            if line.amount != 0:
                loan_installment_lines.append((0, 0, {
                    "loan_installment_line_id": line.loan_installment_line_id.id,
                    "amount": line.amount
                }))

        vals = {
            "date": self.date,
            "amount": self.amount,
            "payment_type": "inbound",
            "ref": loan.name,
            "journal_id": self.journal_id.id,
            "currency_id": loan.currency_id.id,
            "company_id": loan.company_id.id,
            "payment_loan_installment_line_ids": loan_installment_lines
        }

        address_home_id = loan.employee_id.private_street
        if address_home_id:
            vals.update({"partner_id": address_home_id.id,
                         "destination_account_id": address_home_id.property_account_receivable_id.id})
        return vals

    def action_payment(self):
        loan = self.env["hr.loan"].search([("id", "=", self._context["active_id"])])
        if not loan.complete_disbursement or loan.is_paid:
            return

        if self.amount > loan.total_remaining:
            raise ValidationError(_("Invalid loan amount.\nYou can Payment maximum %s") % loan.total_remaining)

        account_payment_obj = self.env["account.payment"]
        if self.line_ids:
            total_paid = sum(line.amount for line in self.line_ids)
            if total_paid != self.amount:
                raise ValidationError(
                    _("Total Amount of Installment %s must be equal to payment amount %s") % (total_paid, self.amount))

            account_payment = account_payment_obj.create(self._prepare_account_payment(loan))
            account_payment.action_post()

        return True
