

from odoo import models, fields, api
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # جعل حقل الحالة قابل للاستيراد والتعديل مؤقتاً
    state = fields.Selection(selection_add=[], readonly=False, import_eligible=True)
    invoice_status = fields.Selection(selection_add=[], readonly=False, store=True)