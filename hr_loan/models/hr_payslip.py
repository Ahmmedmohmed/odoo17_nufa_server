# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _prepare_input_loan_installment_line(self, loan_installment_line, type):
        print(loan_installment_line)
        print(type)
        hr_loan_input_type = type == "loan" and  self.env.ref("hr_loan.hr_loan_other_input") or self.env.ref("hr_loan.hr_loan_advanced_other_input")
        vals = {
            "payslip_id": self.id,
            "input_type_id": hr_loan_input_type.id,
            'amount': loan_installment_line.remaining_amount,
            "loan_installment_line_id": loan_installment_line.id
        }
        return vals

    def compute_sheet(self):
        loan_installment_line_obj = self.sudo().env["hr.loan.installment.line"]
        hr_payslip_input_obj = self.env['hr.payslip.input']

        for payslip in self.filtered(lambda slip: slip.state in ["draft", "verify"]):
            # get installments of loan is not paid for employee
            loan_installment_lines = loan_installment_line_obj.search(
                [("loan_id.employee_id", "=", payslip.employee_id.id), ("loan_id.done_state", "=", "approve"),
                 ("is_paid", "=", False), ("date", ">=", payslip.date_from), ("date", "<=", payslip.date_to)])
            print(loan_installment_lines)

            old_loan_input_lines = hr_payslip_input_obj.search([("loan_installment_line_id", "!=", False), (
                "loan_installment_line_id", "not in", loan_installment_lines.ids), ("payslip_id", "=", payslip.id)])
            if old_loan_input_lines:
                old_loan_input_lines.unlink()

            for loan_installment_line in loan_installment_lines:
                loan = loan_installment_line.loan_id

                if loan.total_disbursement != loan.amount:
                    continue

                if loan.total_disbursement == loan.amount:
                    installment_line_input = hr_payslip_input_obj.search(
                        [("loan_installment_line_id", "=", loan_installment_line.id), ("payslip_id", "=", payslip.id)],
                        limit=1)
                    if not installment_line_input:
                        hr_payslip_input_obj.create(payslip._prepare_input_loan_installment_line(loan_installment_line,loan.type))

        return super(HrPayslip, self).compute_sheet()

    def action_payslip_done(self):
        for payslip in self:
            if payslip.state == "cancel":
                continue

            for input_line in payslip.input_line_ids:
                if input_line.loan_installment_line_id:
                    loan = input_line.loan_installment_line_id.loan_id
                    loan_installment_line = input_line.loan_installment_line_id

                    if loan.total_disbursement != loan.amount:
                        raise ValidationError(_("Cannot pay before complete disbursement for loan %s") % loan.name)

                    if loan_installment_line.is_paid:
                        raise ValidationError("Cannot pay installment for loan %s which is already paid" % loan.name)

                    if input_line.amount <= 0:
                        raise ValidationError(_("Input Amount loan installment %s must be positive") % loan.name)

                    if input_line.amount > loan_installment_line.remaining_amount:
                        raise ValidationError(_("Invalid loan installment %s amount.\n You can Payment maximum %s") % (
                            loan.name, loan_installment_line.remaining_amount))

                    loan_installment_line.write({"paid_amount": loan_installment_line.paid_amount + input_line.amount})

        return super(HrPayslip, self).action_payslip_done()


class HrPayslipInput(models.Model):
    _inherit = "hr.payslip.input"

    loan_installment_line_id = fields.Many2one("hr.loan.installment.line", string="Loan Installment")
