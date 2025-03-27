# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.tools import float_round
from odoo.addons.payment.controllers.portal import PaymentProcessing

PPG = 10


class WebsiteWallet(http.Controller):

    @http.route('/wallet/dashboard', type='http', auth='user', website=True)
    def wallet_dashboard(self, **kwargs):
        return request.render('customer_web_wallet_cft.wallet_dashboard',
                              {'user': request.env.user})

    @http.route('/add_money_transaction/pay', type='http', auth='user',
                website=True)
    def add_money_wallet_payment(self, amount=False, currency_id=None,
                                 acquirer_id=None, **kw):
        user = request.env.user.sudo()

        # Default values
        values = {
            'amount': 0.0,
            'currency': user.company_id.currency_id,
        }
        if currency_id:
            try:
                currency_id = int(currency_id)
                values['currency'] = request.env['res.currency'].browse(
                    currency_id)
            except:
                pass
        else:
            values['currency'] = request.website.currency_id

        # Check amount
        if amount:
            try:
                amount = float(amount)
                values['amount'] = amount
            except:
                pass

        # Check reference
        values['reference'] = request.env[
            'payment.transaction']._compute_reference()

        # Check acquirer
        acquirers = None
        if acquirer_id:
            acquirers = request.env['payment.acquirer'].browse(
                int(acquirer_id))
        if not acquirers:
            acquirers = request.env['payment.acquirer'].search(
                [('state', 'in', ['enabled', 'test']),
                 ('company_id', '=', user.company_id.id)])

        partner_id = user.partner_id.id if not user._is_public() else False
        values.update({
            'return_url': '/add_money_transaction/confirm',
            'partner_id': partner_id,
            'bootstrap_formatting': True,
            'error_msg': kw.get('error_msg'),
            'wallet_transaction': True,
        })
        valid_flows = ['form', 's2s'] if not user._is_public() else ['form']
        values['acquirers'] = [acq for acq in acquirers if
                               acq.payment_flow in valid_flows and
                               not acq.wallet_acquirer]
        if partner_id:
            values['pms'] = request.env['payment.token'].search([
                ('acquirer_id', 'in', acquirers.ids),
                ('partner_id', '=', partner_id)
            ])
        else:
            values['pms'] = []

        return request.render('customer_web_wallet_cft.wallet_transaction',
                              values)

    def _get_existing_transaction(self, reference, amount, partner_id,
                                  currency_id, acquirer_id, tx_id):
        PaymentTransaction = request.env['payment.transaction']
        tx = None
        if tx_id:
            tx = PaymentTransaction.sudo().browse(tx_id)
            if not tx.exists() or tx.reference != reference or tx.acquirer_id.id != acquirer_id:
                tx = None

        if not tx:
            tx = PaymentTransaction.sudo().search(
                [('reference', '=', reference),
                 ('acquirer_id', '=', acquirer_id)])

        if tx and (
                tx.state != 'draft' or tx.partner_id.id != partner_id or tx.amount != amount or tx.currency_id.id != currency_id):
            tx = None

        return tx

    @http.route(
        '/website_wallet_payment/transaction/<string:amount>/<string:currency_id>/<path:reference>',
        type='json', auth='public')
    def transaction(self, acquirer_id, reference, amount, currency_id,
                    **kwargs):
        partner_id = request.env.user.partner_id.id if not request.env.user._is_public() else False
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        tx = self._get_existing_transaction(reference, float(amount),
                                            partner_id,
                                            int(currency_id), int(acquirer_id),
                                            request.session.get(
                                                'wallet_transaction_id'))
        if not tx:
            values = {
                'acquirer_id': int(acquirer_id),
                'reference': reference,
                'amount': float(amount),
                'currency_id': int(currency_id),
                'partner_id': partner_id,
                'type': 'form_save' if acquirer.save_token != 'none' and partner_id else 'form',
                'wallet_transaction': True,
                'wallet_transaction_type': 'credit'
            }
            tx = request.env['payment.transaction'].sudo().with_context(
                lang=None, wallet_transaction=True).create(values)
            tx.return_url = '/website_wallet_payment/confirm?tx_id=%d' % tx.id
            PaymentProcessing.add_payment_transaction(tx)

        render_values = {
            'partner_id': partner_id,
        }
        return acquirer.sudo().render(reference, float(amount),
                                      int(currency_id), values=render_values)

    @http.route(
        '/website_wallet_payment/token/<string:amount>/<string:currency_id>/<path:reference>',
        type='http',
        auth='public', website=True)
    def payment_token(self, pm_id, reference, amount, currency_id,
                      return_url=None, **kwargs):
        token = request.env['payment.token'].browse(int(pm_id))
        order_id = kwargs.get('order_id')

        if not token:
            return request.redirect('/add_money_transaction/pay?error_msg=%s'
                                    % _('Cannot setup the payment.'))

        partner_id = request.env.user.partner_id.id if not \
            request.env.user._is_public() else False
        values = {
            'acquirer_id': token.acquirer_id.id,
            'reference': reference,
            'amount': float(amount),
            'currency_id': int(currency_id),
            'partner_id': partner_id,
            'payment_token_id': pm_id,
            'type': 'form_save' if token.acquirer_id.save_token != 'none'and
                                   partner_id else 'form',
            'wallet_transaction': True,
            'wallet_transaction_type': 'credit'
        }

        if order_id:
            values['sale_order_ids'] = [(6, 0, [order_id])]

        tx = request.env['payment.transaction'].sudo().with_context(
            lang=None, wallet_transaction=True).create(values)
        PaymentProcessing.add_payment_transaction(tx)

        try:
            res = tx.s2s_do_transaction()
            if tx.state == 'done':
                tx.return_url = return_url or '/website_wallet_payment/confirm?tx_id=%d' % tx.id
            valid_state = 'authorized' if tx.acquirer_id.capture_manually else 'done'
            if not res or tx.state != valid_state:
                tx.return_url = '/add_money_transaction/pay?error_msg=%s' % _(
                    'Payment transaction failed.')
            return request.redirect('/payment/process')
        except Exception as e:
            return request.redirect('/payment/process')

    @http.route(['/website_wallet_payment/confirm'], type='http',
                auth='public',
                website=True)
    def payment_confirm(self, **kw):
        tx_id = int(kw.get('tx_id', 0)) or request.session.pop(
            'wallet_transaction_id', 0)
        if tx_id:
            tx = request.env['payment.transaction'].browse(
                tx_id).sudo().exists()
            if tx.state in ['done', 'authorized']:
                status = 'success'
                message = tx.acquirer_id.done_msg
            elif tx.state == 'pending':
                status = 'warning'
                message = tx.acquirer_id.pending_msg
            else:
                status = 'danger'
                message = tx.acquirer_id.error_msg
            PaymentProcessing.remove_payment_transaction(tx)
            return request.render(
                'customer_web_wallet_cft.wallet_transaction_confirm', {
                    'tx': tx,
                    'status': status,
                    'message': message
                }
            )
        else:
            return request.redirect('/my/home')

    @http.route([
        '/website/wallet/transaction',
        '/website/wallet/transaction/page/<int:page>',
    ], type='http', auth='user', website=True)
    def transaction_history(self, page=0, **kw):
        values = {}
        Transaction = request.env['payment.transaction']
        domain = [
            ('wallet_transaction', '=', True),
            ('partner_id', '=', request.env.user.partner_id.id),
            ('state', '=', 'done')
        ]
        search_transaction = Transaction.sudo().search(domain)
        transaction_count = len(search_transaction)
        url = '/website/wallet/transaction'
        pager = request.website.pager(url=url, page=page, total=transaction_count, step=PPG)
        transaction_ids = Transaction.sudo().search(domain, limit=PPG, offset=pager['offset'])

        total_added = sum(search_transaction.filtered(
            lambda rec: rec.wallet_transaction_type == 'credit'
        ).mapped('amount'))
        total_paid = sum(search_transaction.filtered(
            lambda rec: rec.wallet_transaction_type == 'debit'
        ).mapped('amount'))

        values.update({
            'transaction_ids': transaction_ids,
            'pager': pager,
            'available': float_round(total_added - total_paid, precision_digits=2),
            'added': float_round(total_added, precision_digits=2),
            'paid': float_round(total_paid, precision_digits=2),
        })
        return request.render(
            'customer_web_wallet_cft.website_wallet_transaction_history',
            values)
