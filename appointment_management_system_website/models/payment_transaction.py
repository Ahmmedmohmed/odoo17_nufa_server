# -*- coding: utf-8 -*-

from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_pending(self, state_message=None, **kwargs):
        txs_to_process = super()._set_pending(state_message=state_message, **kwargs)
        for tx in txs_to_process:
            website_orders = tx.sale_order_ids.filtered(
                lambda so: so.website_id and so.state in ('draft', 'sent')
            )
            if website_orders:
                website_orders.sudo().action_confirm()
        return txs_to_process
