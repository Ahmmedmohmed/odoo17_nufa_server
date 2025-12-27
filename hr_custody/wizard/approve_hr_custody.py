# -*- coding: utf-8 -*-

from odoo import fields, models


class ApproveHRCustodyLineWizard(models.TransientModel):
    _name = "approve.hr.custody.line"
    _description = "Approve HR Custody Lines"

    approve_hr_custody_id = fields.Many2one("approve.hr.custody", string="Approve HR Custody", ondelete="cascade",
                                            required=True)
    custody_line_id = fields.Many2one("hr.custody.line", string="Line", required=True, readonly=True)
    quantity = fields.Float(related="custody_line_id.quantity", string="Quantity", readonly=True, store=True)
    uom_id = fields.Many2one(related="custody_line_id.uom_id", string="Unit of Measure", readonly=True, store=True)
    reason = fields.Text(related="custody_line_id.reason", string="Reason", readonly=True, store=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)


class ApproveHRCustodyWizard(models.TransientModel):
    _name = "approve.hr.custody"
    _description = "Approve HR Custody"

    line_ids = fields.One2many("approve.hr.custody.line", "approve_hr_custody_id", string="Lines")

    def action_approve(self):
        custody = self.env["hr.custody"].search([("id", "=", self._context["active_id"])])

        if custody.state != "in_progress":
            return

        for line in self.line_ids:
            line.custody_line_id.write({"product_id": line.product_id.id})

        return custody.write({"state": "done", "done_state": "approve"})
