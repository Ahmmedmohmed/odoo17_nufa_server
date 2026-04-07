from odoo import models, fields

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    checkout_id = fields.Char('HyperPay Checkout ID')
    payment_method = fields.Char('Payment Method')

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('hyperpay', 'HyperPay')],
        ondelete={'hyperpay': 'set default'}
    )