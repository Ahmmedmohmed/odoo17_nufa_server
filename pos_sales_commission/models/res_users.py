# -*- coding: utf-8 -*-

# from openerp import models, fields, api
from odoo import models, fields, api #odoo13

class User(models.Model):
    _inherit = 'res.users'
    
    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()
    
    team_id = fields.Many2one(
        'crm.team',
        'Sales Team',
        default=_get_default_team,
    )