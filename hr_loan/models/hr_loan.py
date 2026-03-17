# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError


class HRLoan(models.Model):
    _name = "hr.loan"
    _description = "HR Loan Requests"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Number", readonly=True, default="/", index=True, tracking=True, copy=False)
    date = fields.Date("Date", required=True, default=fields.Date.context_today, index=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True, tracking=True,
                                  domain=[('contract_id', '!=', False)])
    user_employee_id = fields.Many2one(related="employee_id.user_id", string="User Employee", readonly=True, store=True)
    department_id = fields.Many2one(related="employee_id.department_id", string="Department", readonly=True, store=True)
    manager_id = fields.Many2one(related="employee_id.parent_id", string="Manager", store=True)
    job_id = fields.Many2one(related="employee_id.job_id", string="Job Position", store=True, readonly=True)
    amount = fields.Monetary(string="Amount", required=True, tracking=True)
    number_installments = fields.Integer(string="Number Installments", default=1, required=True, readonly=True,
                                         tracking=True)
    installment_type = fields.Selection([("monthly", "Monthly"), ("quarterly", "Quarterly")], string="Installment Type",
                                        default="monthly", readonly=True, required=True, tracking=True)
    start_date = fields.Date("Start Date", required=True, default=fields.Date.context_today, index=True, tracking=True)
    description = fields.Char(string="Description")
    type = fields.Selection([("loan", "Loan"), ("advance", "Advance")], string="Type", required=True, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("validate", "Validated"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancel", "Canceled")], string="Status", required=True, index=True, tracking=True, default="draft", copy=False)
    done_state = fields.Selection([("approve", "Approved"), ("reject", "Rejected")], string="Done Status",
                                  tracking=True, copy=False)
    line_ids = fields.One2many("hr.loan.installment.line", "loan_id", string="Lines", copy=False)
    currency_id = fields.Many2one("res.currency", "Currency", required=True, copy=False,
                                  default=lambda self: self.env.user.company_id.currency_id.id, tracking=True)
    company_id = fields.Many2one("res.company", "Company", required=True, index=True, copy=False,
                                 default=lambda self: self.env.user.company_id.id, tracking=True)
    # user_id = fields.Many2one("res.users", string="Assigned To", tracking=True, required=True, index=True,
    #                           default=lambda self: self.env.user,
    #                           domain=lambda self: [("groups_id", "=", self.env.ref("hr_loan.group_hr_loan_user").id)])
    user_id = fields.Many2one("res.users", related='employee_id.loan_and_advance_user',string="Assigned To",readonly=True)
    cancel_reason = fields.Text("Cancel Reason", readonly=True, copy=False)
    reject_reason = fields.Text("Reject Reason", readonly=True, copy=False)
    balance = fields.Float(string="Balance", compute="_compute_balance", store=True, readonly=True)
    total_paid = fields.Monetary(string="Total Paid", compute="_compute_total_paid", store=True, readonly=True)
    total_remaining = fields.Monetary(string="Total Remaining", compute="_compute_total_paid", store=True,
                                      readonly=True)
    is_paid = fields.Boolean(string="Is Paid", compute="_compute_total_paid", store=True, readonly=True)
    total_disbursement = fields.Monetary(string="Total Disbursement", readonly=True, copy=False)
    complete_disbursement = fields.Boolean(string="Complete Disbursement", compute="_compute_complete_disbursement",
                                           store=True, readonly=True)
    payslips_count = fields.Integer(string="Payslips Count", compute="_compute_payslips_count")
    payments_count = fields.Integer(string="Payments Count", compute="_compute_payments_count")


    @api.constrains("amount")
    def _check_amount(self):
        for loan in self:
            if loan.amount <= 0:
                raise ValidationError(_("Amount must be positive"))

    @api.constrains("line_ids")
    def _check_total_installments(self):
        for loan in self:
            if loan.line_ids:
                installments_amount = sum(line.amount for line in loan.line_ids)

                if installments_amount != loan.amount:
                    raise ValidationError(_("Total Amount of installments must be equal to %s" % loan.amount))

    @api.depends("employee_id")
    def _compute_balance(self):
        move_line_obj = self.sudo().env["account.move.line"]
        for loan in self:
            balance = 0
            address_home_id = self.employee_id.private_street
            if address_home_id:
                balance = move_line_obj.read_group([("partner_id", "=", address_home_id.id),
                                                    ("account_id.account_type", "in", ['asset_receivable', 'liability_payable']),
                                                    ("move_id.state", "=", "posted")], ["balance"], [])[0][
                              "balance"] or 0

        loan.balance = balance

    @api.depends("line_ids.paid_amount", "line_ids.remaining_amount")
    def _compute_total_paid(self):
        for loan in self:
            total_paid = 0
            total_remaining = 0

            for line in loan.line_ids:
                total_paid += line.paid_amount
                total_remaining += line.remaining_amount

            loan.total_paid = total_paid
            loan.total_remaining = total_remaining
            loan.is_paid = (loan.total_remaining == 0 and loan.done_state == "approve")

    @api.depends("amount", "total_disbursement")
    def _compute_complete_disbursement(self):
        for loan in self:
            loan.complete_disbursement = (loan.amount == loan.total_disbursement)

    def _compute_payslips_count(self):
        hr_payslip_input_obj = self.sudo().env["hr.payslip.input"]
        for loan in self:
            loan.payslips_count = len(
                hr_payslip_input_obj.search(
                    [("loan_installment_line_id", "in", loan.line_ids.ids), ("payslip_id.state", "=", "done")]).mapped(
                    "payslip_id"))

    def _compute_payments_count(self):
        payment_loan_installment_line_obj = self.sudo().env["account.payment.loan.installment.line"]
        for loan in self:
            loan.payments_count = len(
                payment_loan_installment_line_obj.search(
                    [("loan_installment_line_id", "in", loan.line_ids.ids)]).mapped("account_payment_id"))

    @api.model
    def default_get(self, fields):
        res = super(HRLoan, self).default_get(fields)

        employee_id = self.env["hr.employee"].search([("user_id", "=", self.env.user.id), ('contract_id', '!=', False)],
                                                     limit=1).id
        res.update({"employee_id": employee_id})

        return res

    def unlink(self):
        for loan in self:
            if loan.state != "draft":
                if loan.type == "loan":
                    raise UserError(_("You cannot delete loan or %s which is not draft") % loan.display_name)
                else:
                    raise UserError(_("You cannot delete advance or %s which is not draft") % loan.display_name)

        return super(HRLoan, self).unlink()

    def action_send_email(self):
        self.ensure_one()
        form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model="hr.loan",
            default_res_id=self.id,
            default_composition_mode="comment",
            custom_layout="mail.mail_notification_light",
            force_email=True,
        )
        return {
            'name': _("Compose Email"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(form.id, 'form')],
            'view_id': form.id,
            'target': 'new',
            'context': ctx,
        }

    def action_validate(self):
        if self.state != "draft":
            return

        if self.type == "loan":
            name = self.env["ir.sequence"].next_by_code("hr.loan")
        else:
            name = self.env["ir.sequence"].next_by_code("hr.advance")

        return self.write({"state": "validate", "name": name})

    def action_confirm(self):
        if self.state != "validate":
            return

        action = self.sudo().env.ref("hr_loan.action_confirm_hr_loan_wizard")
        result = action.read()[0]

        employee = self.employee_id
        if self.type == "loan":
            credit_limit = employee.credit_limit_loan
            amount_total = employee.total_loans
            remaining_amount = employee.remaining_loans
            paid_amount = employee.paid_loans
        else:
            credit_limit = employee.credit_limit_advance
            amount_total = employee.total_advances
            remaining_amount = employee.remaining_advances
            paid_amount = employee.paid_advances

        result["context"] = {
            "default_amount": self.amount,
            "default_start_date": self.start_date,
            "default_credit_limit": credit_limit,
            "default_amount_total": amount_total,
            "default_remaining_amount": remaining_amount,
            "default_paid_amount": paid_amount
        }
        return result

    def _prepare_installment_line(self, amount, date):
        vals = {
            "date": date,
            "amount": amount,
            "loan_id": self.id
        }
        return vals

    def action_compute_installments(self):
        if self.state != "in_progress":
            return

        action = self.sudo().env.ref("hr_loan.action_compute_installments_hr_loan_wizard")
        result = action.read()[0]

        result["context"] = {"default_number_installments": self.number_installments,
                             "default_installment_type": self.installment_type}
        return result

    def action_approve(self):
        if self.state != "in_progress":
            return

        if not self.env.user.has_group("hr_loan.group_manage_exceed_credit_limit"):
            employee = self.employee_id

            if self.type == "loan" and employee.credit_limit_loan != 0 and employee.credit_limit_loan <= employee.remaining_loans:
                raise ValidationError(
                    _("Cannot exceed credit limit %s of employee \n Please pay remaining loans %s to approve other loan" % (
                        employee.credit_limit_loan, employee.remaining_loans)))

            if self.type == "advance" and employee.credit_limit_advance != 0 and employee.credit_limit_advance <= employee.remaining_advances:
                raise ValidationError(
                    _("Cannot exceed credit limit %s of employee \n Please pay remaining advances %s to approve other advance" % (
                        employee.credit_limit_advance, employee.remaining_advances)))

        if self.type == "advance":
            self.env["hr.loan.installment.line"].create(self._prepare_installment_line(self.amount, self.start_date))

        if not self.line_ids:
            raise ValidationError(_("Loan not have installments"))

        return self.write({"state": "done", "done_state": "approve"})

    def _prepare_default_disbursement_payment(self):
        return {
            "default_loan_id": self.id,
            "default_currency_id": self.currency_id.id,
            "default_company_id": self.company_id.id,
            "default_payment_type": "outbound",
            "default_partner_type": "supplier",
            "default_partner_id": self.employee_id.address_id.id,
            "default_move_journal_types": ("bank", "cash"),
            "default_amount": self.amount - self.total_disbursement,
            "default_ref": self.name,
            "default_is_loan":True
        }

    def action_get_disbursement_payments(self):
        action = self.sudo().env.ref("hr_loan.action_account_disbursement_payments")
        result = action.read()[0]

        result["context"] = self._prepare_default_disbursement_payment()

        result["domain"] = [("loan_id", "=", self.id)]

        return result

    def action_disbursement(self):
        form = self.env.ref('hr_loan.view_account_payment_hr_loan_form', False)

        return {
            "name": _("Loan Disbursement"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "account.payment",
            "views": [(form.id, "form")],
            "view_id": form.id,
            "context": self._prepare_default_disbursement_payment(),
        }

    def action_payment(self):
        if not self.complete_disbursement or self.is_paid:
            return

        action = self.sudo().env.ref("hr_loan.action_hr_loan_installment_payment_wizard")
        result = action.read()[0]

        result["context"] = {"default_amount": self.total_remaining}

        return result

    def action_get_payments(self):
        action = self.sudo().env.ref("account.action_account_payments")
        result = action.read()[0]

        payment_ids = self.sudo().env["account.payment.loan.installment.line"].search(
            [("loan_installment_line_id", "in", self.line_ids.ids)]).mapped("account_payment_id").ids

        result["domain"] = [("id", "in", payment_ids)]
        return result

    def action_get_payslips(self):
        action = self.sudo().env.ref("hr_payroll.hr_payslip_action_view_to_pay")
        result = action.read()[0]

        payslip_ids = self.sudo().env["hr.payslip.input"].search(
            [("loan_installment_line_id", "in", self.line_ids.ids), ("payslip_id.state", "=", "done")]).mapped(
            "payslip_id").ids

        result["domain"] = [("id", "in", payslip_ids)]

        return result

    def _track_subtype(self, init_values):
        self.ensure_one()
        if self.type == "loan":
            if "state" in init_values and self.state == "validate":
                return self.env.ref("hr_loan.mt_hr_loan_validated")
            elif "state" in init_values and self.state == "in_progress":
                return self.env.ref("hr_loan.mt_hr_loan_confirmed")
            elif "state" in init_values and self.state == "cancel":
                return self.env.ref("hr_loan.mt_hr_loan_canceled")

            if "done_state" in init_values and self.done_state == "approve":
                return self.env.ref("hr_loan.mt_hr_loan_approved")
            elif "done_state" in init_values and self.done_state == "reject":
                return self.env.ref("hr_loan.mt_hr_loan_rejected")
        else:
            if "state" in init_values and self.state == "validate":
                return self.env.ref("hr_loan.mt_hr_advance_validated")
            elif "state" in init_values and self.state == "in_progress":
                return self.env.ref("hr_loan.mt_hr_advance_confirmed")
            elif "state" in init_values and self.state == "cancel":
                return self.env.ref("hr_loan.mt_hr_advance_canceled")

            if "done_state" in init_values and self.done_state == "approve":
                return self.env.ref("hr_loan.mt_hr_advance_approved")
            elif "done_state" in init_values and self.done_state == "reject":
                return self.env.ref("hr_loan.mt_hr_advance_rejected")

        return super(HRLoan, self)._track_subtype(init_values)


class HRLoanInstallmentLine(models.Model):
    _name = "hr.loan.installment.line"
    _description = "HR Loan Installment Lines"
    _order = "date, id"
    _rec_name = "date"

    loan_id = fields.Many2one("hr.loan", string="Loan", ondelete="cascade", copy=False, required=True)
    date = fields.Date("Date", required=True, copy=False)
    amount = fields.Monetary(string="Amount", required=True, copy=False)
    currency_id = fields.Many2one(related="loan_id.currency_id", string="Currency", readonly=True, store=True)
    paid_amount = fields.Monetary(string="Paid Amount", copy=False, readonly=True)
    remaining_amount = fields.Monetary(string="Remaining Amount", compute="_compute_remaining_amount", store=True,
                                       readonly=True)
    is_paid = fields.Boolean(string="Is Paid", compute="_compute_remaining_amount", store=True, readonly=True)

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Amount must be positive"))

    @api.depends("amount", "paid_amount")
    def _compute_remaining_amount(self):
        for line in self:
            line.remaining_amount = line.amount - line.paid_amount
            line.is_paid = (line.remaining_amount == 0)
