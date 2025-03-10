# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ComputeInstallmentsHRLoanWizard(models.TransientModel):
    _name = "compute.installments.hr.loan"
    _description = "Compute Installments HR Loan"

    number_installments = fields.Integer(string="Number Installments", required=True)
    installment_type = fields.Selection([("monthly", "Monthly"), ("quarterly", "Quarterly")], string="Installment Type",
                                        required=True)

    @api.constrains("number_installments")
    def _check_number_installments(self):
        for line in self:
            if line.number_installments <= 0:
                raise ValidationError(_("Number Installments must be positive"))

    def action_compute_installments(self):
        loan = self.env["hr.loan"].search([("id", "=", self._context["active_id"])])

        if loan.state != "in_progress":
            return

        # remove old installments if exits
        if loan.line_ids:
            loan.line_ids.unlink()

        # create new installments
        number_installments = self.number_installments
        base_amount = round(loan.amount / number_installments, 2)
        date = loan.start_date
        installment_line_obj = self.env["hr.loan.installment.line"]
        number_months = self.installment_type == "monthly" and 1 or 3

        for i in range(number_installments):
            if i != 0:
                date = date + relativedelta(months=number_months)

            if i == (self.number_installments - 1):
                base_amount = round(loan.amount - (base_amount * (number_installments - 1)), 2)

            installment_line_obj.create(loan._prepare_installment_line(base_amount, date))

        loan.write({"number_installments": self.number_installments, "installment_type": self.installment_type})

        return True
