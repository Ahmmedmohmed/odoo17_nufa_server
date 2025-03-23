# -*- coding: utf-8 -*-
# from openerp import models, fields, api
from odoo import models, fields, api #odoo13


class PosCategory(models.Model):
    _inherit = "pos.category"
    
    # @api.multi #odoo13
#    @api.depends('pos_is_apply')
    @api.depends()
    def _compute_is_apply(self):
#         commission_based_on = self.env['ir.values'].get_default('pos.config.settings', 'commission_based_on')
        #pos_config_id = self.env['pos.config'].search([], limit=1) #odoo11
       # pos_config_id = self.env['res.config.settings'].search([], limit=1) #odoo11
#        commission_based_on = self.env['ir.config_parameter'].sudo().get_param('pos_sales_commission.commission_based_on')
        commission_based_on = self.env.user.company_id.commission_based_on
        for rec in self:
            if commission_based_on == 'product_category':
                rec.pos_is_apply = True
            else: #odoo13
                rec.pos_is_apply = False #odoo13
        
    pos_sales_manager_commission = fields.Float(
        'Sales Manager Commission(%)'
    )
    pos_sales_person_commission = fields.Float(
        'Sales Person Commission(%)'
    )
    pos_is_apply = fields.Boolean(
        string='Is Apply ?',
        compute='_compute_is_apply'
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
