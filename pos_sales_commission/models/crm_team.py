# -*- coding: utf-8 -*-
# from openerp import models, fields, api
from odoo import models, fields, api #odoo13


class Team(models.Model):
    _inherit = 'crm.team'
    
    # @api.multi #odoo13
#    @api.depends('pos_is_apply')
    @api.depends()
    def _compute_is_apply(self):
#         commission_based_on = self.env['ir.config_parameter'].get_default('pos.config', 'commission_based_on')
       # pos_config_id = self.env['pos.config'].search([], limit=1) #odoo11
#        commission_based_on = self.env['ir.config_parameter'].sudo().get_param('pos_sales_commission.commission_based_on') #odoo11
        commission_based_on = self.company_id.commission_based_on if self.company_id else self.env.user.company_id.commission_based_on
        for rec in self:
            if commission_based_on == 'sales_team':
                rec.pos_is_apply = True
            else: #odoo13
                rec.pos_is_apply = False #odoo13
                
    pos_sales_manager_commission = fields.Float(
        'POS Sales Manager Commission(%)'
    )
    pos_sales_person_commission = fields.Float(
        'POS Sales Person Commission(%)'
    )
    pos_is_apply = fields.Boolean(
        string='POS Is Apply ?',
        compute='_compute_is_apply'
    )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
