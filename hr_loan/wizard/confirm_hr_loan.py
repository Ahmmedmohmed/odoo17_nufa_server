# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ConfirmHRLoanWizard(models.TransientModel):
    _name = "confirm.hr.loan"
    _description = "Confirm HR Loan"

    amount = fields.Float(string="Amount", required=True)
    start_date = fields.Date("Start Date", required=True)
    credit_limit = fields.Float("Credit Limit", readonly=True)
    amount_total = fields.Float("Total", readonly=True)
    remaining_amount = fields.Float("Remaining Amount", readonly=True)
    paid_amount = fields.Float("Paid Amount", readonly=True)

    def action_add_follower(self, loan, partner_id):
        default_subtypes, _, _ = self.env["mail.message.subtype"].default_subtypes("hr.loan")

        vals = {
            "res_id": loan.id,
            "res_model": "hr.loan",
            "partner_id": partner_id.id,
            "subtype_ids": [(6, 0, default_subtypes.ids)]
        }

        self.env["mail.followers"].create(vals)

        return True

    def action_confirm(self):
        loan = self.env["hr.loan"].search([("id", "=", self._context["active_id"])])

        if loan.state != "validate":
            return

        if not self.env.user.has_group("hr_loan.group_manage_exceed_credit_limit"):
            employee = loan.employee_id

            if loan.type == "loan" and employee.credit_limit_loan != 0 and employee.credit_limit_loan <= employee.remaining_loans:
                raise ValidationError(
                    _("Cannot exceed credit limit %s of employee \n Please pay remaining loans %s to confirm other loan" % (
                        employee.credit_limit_loan, employee.remaining_loans)))

            if loan.type == "advance" and employee.credit_limit_advance != 0 and employee.credit_limit_advance <= employee.remaining_advances:
                raise ValidationError(
                    _("Cannot exceed credit limit %s of employee \n Please pay remaining advances %s to confirm other advance" % (
                        employee.credit_limit_advance, employee.remaining_advances)))

        # add assigned user in followers if not exists
        if loan.user_id.partner_id.id not in loan.message_partner_ids.ids:
            self.action_add_follower(loan, loan.user_id.partner_id)

        # manager of employee if not exists
        user_manager = loan.manager_id.user_id
        if user_manager and user_manager.partner_id.id not in loan.message_partner_ids.ids:
            self.action_add_follower(loan, user_manager.partner_id)

        loan.write({"state": "in_progress", "amount": self.amount, "start_date": self.start_date})

        return True
