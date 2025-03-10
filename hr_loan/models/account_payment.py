# -*- coding: utf-8 -*-
import ast

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


# @api.depends('journal_id', 'payment_type', 'payment_method_line_id')
# def _compute_outstanding_account_id(self):
#     for pay in self:
#         if pay.check_id.is_partial_collect:
#             pay.outstanding_account_id = pay.check_id.partial_journal_id.default_account_id.id
#         else:
#             if not pay.check_id.not_partial and pay.check_id.partial_check:
#                 pay.outstanding_account_id = pay.check_id.journal_id.inbound_payment_method_line_ids[
#                     0].payment_account_id.id
#             elif pay.check_id.not_partial:
#                 pay.outstanding_account_id = pay.check_id.journal_id.default_account_id.id
#             elif pay.check_id:
#                 # pay.outstanding_account_id = pay.check_id.journal_id.default_account_id.id
#                 pay.outstanding_account_id = self.env.ref('qasatlii_checks.main_acc_payment_account').id
#             else:
#                 super()._compute_outstanding_account_id()
class AccountPayment(models.Model):
    _inherit = "account.payment"

    loan_id = fields.Many2one("hr.loan", string="Loan", help="Loan", copy=False)
    payment_loan_installment_line_ids = fields.One2many("account.payment.loan.installment.line", "account_payment_id",
                                                        string="Payment Loan Installment Lines", copy=False)
    is_loan = fields.Boolean(
        string='',
        required=False)

    @api.constrains("amount")
    def _check_amount(self):
        for account_payment in self:
            loan = account_payment.loan_id
            if loan:
                remaining_disbursement = loan.amount - loan.total_disbursement
                if remaining_disbursement < account_payment.amount:
                    raise ValidationError(
                        _("Amount must be less than or equal to remaining form disbursement %s" % remaining_disbursement))

    def action_post(self):
        # check amount of payment if from loan
        loan = self.loan_id
        if loan:
            remaining_disbursement = loan.amount - loan.total_disbursement

            if remaining_disbursement == 0:
                raise ValidationError(_("Complete disbursement has been done for loan %s") % loan.name)

            if remaining_disbursement < self.amount:
                raise ValidationError(
                    _("Amount must be less than or equal to remaining form disbursement %s" % remaining_disbursement))

            loan.write({"total_disbursement": loan.total_disbursement + self.amount})

        if self.payment_loan_installment_line_ids:
            loan = self.payment_loan_installment_line_ids[0].loan_installment_line_id.loan_id

            total_paid = sum(
                payment_installment_line.amount for payment_installment_line in self.payment_loan_installment_line_ids)

            if total_paid != self.amount:
                raise ValidationError(
                    _("Total Amount %s of Installments loan %s must be equal to payment amount %s") % (
                        total_paid, loan.name, self.amount))

        for payment_installment_line in self.payment_loan_installment_line_ids:
            loan_installment_line = payment_installment_line.loan_installment_line_id

            loan = loan_installment_line.loan_id
            if loan.total_disbursement != loan.amount:
                raise ValidationError(_("Cannot pay before complete disbursement for loan %s") % loan.name)

            if loan_installment_line.is_paid:
                raise ValidationError("Cannot pay installment of %s for loan %s which is already paid" % (
                    loan.loan_installment_line, loan.name))

            if payment_installment_line.amount > loan_installment_line.remaining_amount:
                raise ValidationError(
                    _("Invalid Amount installment of %s for loan %s.\n You can Payment maximum %s") % (
                        loan_installment_line.date, loan.name, loan_installment_line.remaining_amount))

            loan_installment_line.write(
                {"paid_amount": loan_installment_line.paid_amount + payment_installment_line.amount})

        return super(AccountPayment, self).action_post()

    def action_draft(self):
        # check total paid of loan is not equal or not if payment is  disbursement from loan
        loan = self.loan_id
        if loan and loan.total_paid != 0:
            raise ValidationError(_("Cannot reset to draft for disbursement after employee pay for loan") % loan.name)

        if loan:
            loan.write({"total_disbursement": loan.total_disbursement - self.amount})

        for payment_installment_line in self.payment_loan_installment_line_ids:
            loan_installment_line = payment_installment_line.loan_installment_line_id

            loan_installment_line.write(
                {"paid_amount": loan_installment_line.paid_amount - payment_installment_line.amount})

        return super(AccountPayment, self).action_draft()

    loan_account = fields.Many2one(
        comodel_name='account.account',
        string='Loan Account',
        related='company_id.loan_account',
        readonly=False,
    )



    @api.depends('journal_id', 'partner_id', 'partner_type', 'is_internal_transfer', 'destination_journal_id', 'is_loan')
    def _compute_destination_account_id(self):
        for pay in self:
            if pay.is_loan:
                pay.destination_account_id = pay.journal_id.loan_account.id
                print("loan_account_id", pay.destination_account_id)
            else:
                res = super(AccountPayment, self)._compute_destination_account_id()
                return res

    # @api.depends('journal_id', 'payment_type', 'payment_method_line_id', 'is_loan')
    # def _compute_outstanding_account_id(self):
    #     for pay in self:
    #         if pay.is_loan:
    #             # pay.destination_account_id = pay.journal_id.company_id.loan_account.id
    #             pay.outstanding_account_id = pay.journal_id.loan_account.id
    #             print("loan_account_id", pay.outstanding_account_id)
    #         else:
    #             res = super(AccountPayment, self)._compute_outstanding_account_id()
    #             return res





class SettingLoan(models.TransientModel):
    _inherit = 'res.config.settings'


    loan_account = fields.Many2one(
        comodel_name='account.account',
        string='Loan Account',
        related='company_id.loan_account',
        readonly=False,
        )
    advance_account  = fields.Many2one(
        comodel_name='account.account',
        string='Advance Account',
        required=False,
        )

    def set_values(self):
        super(SettingLoan, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('hr_loan.loan_account', self.loan_account.id)






class AccountCompany(models.Model):
    _inherit = 'res.company'

    loan_account = fields.Many2one(
        comodel_name='account.account',
        string='Loan Account',
        required=False,
    )



class AccountPaymentLoanInstallmentLine(models.Model):
    _name = "account.payment.loan.installment.line"
    _description = "Account Payment Loan Installment Lines"

    account_payment_id = fields.Many2one("account.payment", string="Account Payment", ondelete="cascade", copy=False,
                                         required=True)
    loan_installment_line_id = fields.Many2one("hr.loan.installment.line", string="Loan Installment", required=True)
    amount = fields.Monetary(string="Amount", required=True, digits="Account", copy=False)
    currency_id = fields.Many2one(related="account_payment_id.currency_id", string="Currency", readonly=True,
                                  store=True)



class LoanJournal(models.Model):
    _inherit = 'account.journal'

    loan_account = fields.Many2one(
        comodel_name='account.account',
        string='Loan Account',
        related='company_id.loan_account',
        readonly=False,
    )

