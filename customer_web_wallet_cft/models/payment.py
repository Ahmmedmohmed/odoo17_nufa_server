# -*- coding: utf-8 -*-

import logging
import json

from odoo import models, fields, api, SUPERUSER_ID, _

_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    wallet_acquirer = fields.Boolean('Wallet Acquirer')


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    wallet_transaction = fields.Boolean('Wallet Transaction')
    wallet_transaction_type = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit')], string='Wallet Transaction Type')
    wallet_reference = fields.Char('Wallet Reference')

    @api.model
    def create(self, vals):
        acquirer_id = None
        if vals.get('acquirer_id', False):
            acquirer_id = self.env['payment.acquirer'].browse(
                vals['acquirer_id'])
        if self._context.get('wallet_transaction', False) or \
                ('reference' in vals and 'tx' in vals.get('reference')) or \
                (acquirer_id and acquirer_id.wallet_acquirer):
            vals['wallet_reference'] = self.env['ir.sequence'].next_by_code(
                'wallet.payment.transaction')
            vals['wallet_transaction'] = True
            if acquirer_id and acquirer_id.wallet_acquirer:
                vals['wallet_transaction_type'] = 'debit'
        return super(PaymentTransaction, self).create(vals)

    def _transfer_form_validate(self, data):
        if self.acquirer_id.provider == 'transfer' and (
                self.acquirer_id.wallet_acquirer or self.env.context.get(
            'wire_wallet_transaction')):
            _logger.info('Validated Wallet payment for tx %s: set as done' % (
                self.reference))
            self._set_transaction_done()
            return True
        else:
            return super(PaymentTransaction, self)._transfer_form_validate(
                data)

    def _reconcile_after_transaction_done(self):
        for rec in self:
            if rec.acquirer_id.provider == 'transfer' and \
                    rec.acquirer_id.wallet_acquirer:
                sales_orders = rec.mapped('sale_order_ids').filtered(
                    lambda sale_id: sale_id.state in ('draft', 'sent'))
                for so in sales_orders:
                    so.with_context(send_email=True).action_confirm()
                rec._invoice_sale_orders()
                invoices = rec.mapped('invoice_ids').filtered(
                    lambda invoice: invoice.state == 'draft')
                invoices.post()
                invoices |= rec.mapped('invoice_ids').filtered(
                    lambda invoice: invoice.state == 'posted')
                for inv in invoices:
                    if inv.invoice_has_outstanding:
                        outstanding_info = json.loads(
                            inv.invoice_outstanding_credits_debits_widget)
                        if 'content' in outstanding_info:
                            for item in outstanding_info['content']:
                                credit_aml_id = item.get('id', False)
                                if credit_aml_id and inv.state == 'posted':
                                    inv.js_assign_outstanding_line(
                                        credit_aml_id)

                if self.env['ir.config_parameter'].sudo().get_param(
                        'sale.automatic_invoice'):
                    default_template = self.env[
                        'ir.config_parameter'].sudo().get_param(
                        'sale.default_email_template')
                    if default_template:
                        ctx_company = {
                            'company_id': rec.acquirer_id.company_id.id,
                            'force_company': rec.acquirer_id.company_id.id,
                            'mark_invoice_as_sent': True,
                        }
                        if rec.sale_order_ids:
                            rec = rec.with_context(ctx_company)
                            for invoice in rec.invoice_ids.with_user(SUPERUSER_ID):
                                invoice.message_post_with_template(
                                    int(default_template),
                                    email_layout_xmlid="mail.mail_notification_paynow")
            else:
                return super(PaymentTransaction,
                             self)._reconcile_after_transaction_done()

    def action_confirm_wallet(self):
        for record in self:
            if record.wallet_transaction and \
                    record.wallet_transaction_type == 'credit':
                record._post_process_after_done()
                record._set_transaction_done()
