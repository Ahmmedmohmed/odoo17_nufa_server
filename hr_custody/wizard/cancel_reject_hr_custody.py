# -*- coding: utf-8 -*-

from odoo import fields, models


class CancelRejectHRCustodyWizard(models.TransientModel):
    _name = "cancel.reject.hr.custody"
    _description = "Cancel Or Reject HR Custody"

    reason = fields.Text("Reason", required=True)

    def action_cancel_reject(self):
        custody = self.env["hr.custody"].search([("id", "=", self._context["active_id"])])

        if self._context.get("cancel_custody", False):
            if custody.state not in ["draft", "validate", "in_progress"]:
                return

            vals = {"state": "cancel", "cancel_reason": self.reason}

        else:
            if custody.state not in ["validate", "in_progress"]:
                return

            vals = {"state": "done", "done_state": "reject", "reject_reason": self.reason}

        custody.write(vals)

        return True
