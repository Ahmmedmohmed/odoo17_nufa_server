# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
# from odoo.exceptions import Warning
from odoo.exceptions import UserError
class PosConfig(models.TransientModel):
    #_inherit = 'pos.config'
    _inherit = 'res.config.settings'
    
    apply_commission = fields.Boolean(
        string="Apply Commission?",
        default=True,
    )
    commission_based_on = fields.Selection([
        ('sales_team', 'Sales Team'),
        ('product_category', 'POS Product Category'),
        ('product_template', 'Product')], 
        string="Calculation Based On",
        related='company_id.commission_based_on',#ODOO13
        readonly=False,#ODOO13
    )
    when_to_pay = fields.Selection([
        ('sales_confirm', 'POS Order Paid'),
#         ('invoice_validate', 'Invoice Validate'),
#         ('invoice_payment', 'Customer Payment')
        ], 
        string="When To Pay",
        related='company_id.when_to_pay',#ODOO13
        readonly=False,#ODOO13
    )
#    
#    
#    @api.model
#    def get_values(self):
#        res = super(PosConfig, self).get_values()
#        params = self.env['ir.config_parameter'].sudo()
#        res.update(
#            when_to_pay = params.get_param('pos_sales_commission.when_to_pay'),
#            commission_based_on = params.get_param('pos_sales_commission.commission_based_on')
#        )
#        return res

#    # @api.multi #odoo13
#    def set_values(self):
#        super(PosConfig, self).set_values()
#        ICPSudo = self.env['ir.config_parameter'].sudo()
#        ICPSudo.set_param("pos_sales_commission.when_to_pay", self.when_to_pay)
#        if self.when_to_pay == 'invoice_payment':
#            if self.commission_based_on == 'product_category' or self.commission_based_on == 'product_template':
#                raise UserError(_("Sales Commission: You can not have commision based on product or category if you have selected when to pay is payment."))
#        ICPSudo.set_param("pos_sales_commission.commission_based_on", self.commission_based_on)
