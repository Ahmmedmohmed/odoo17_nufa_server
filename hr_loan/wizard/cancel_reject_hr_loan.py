# -*- coding: utf-8 -*-

from odoo import fields, models


class CancelRejectHRLoanWizard(models.TransientModel):
    _name = "cancel.reject.hr.loan"
    _description = "Cancel Or Reject HR Loan"

    reason = fields.Text("Reason", required=True)

    def action_cancel_reject(self):
        loan = self.env["hr.loan"].search([("id", "=", self._context["active_id"])])

        if self._context.get("cancel_loan", False):
            if loan.state not in ["draft", "validate", "in_progress"]:
                return

            vals = {"state": "cancel", "cancel_reason": self.reason}

        else:
            if loan.state not in ["validate", "in_progress"]:
                return

            vals = {"state": "done", "done_state": "reject", "reject_reason": self.reason}

        loan.write(vals)

        return True
