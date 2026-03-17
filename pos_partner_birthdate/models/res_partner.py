# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"


    first_name = fields.Char("Partner First Name")
    last_name = fields.Char("Partner Last Name")
    birth_date = fields.Date("Birth Date")
    married_date = fields.Date("Married Date")
    age = fields.Integer(readonly=True, compute="_compute_age")
    phone = fields.Char(required=True)


    @api.depends("birth_date")
    def _compute_age(self):
        for record in self:
            age = 0
            if record.birth_date:
                age = relativedelta(fields.Date.today(), record.birth_date).years
            record.age = age


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('first_name') and vals.get('last_name'):
                vals['name'] = vals.get('first_name') + ' ' + vals.get('last_name')
            elif vals.get('first_name'):
                vals['name'] = vals.get('first_name')
            elif vals.get('last_name'):
                vals['name'] = vals.get('last_name')
        
        return super(ResPartner, self).create(vals_list)