# -*- coding: utf-8 -*-
from odoo import models, fields, api


class Hr_Medical_Insurance(models.Model):

    _name = 'hr.medical.insurance'
    _description = 'Hr Medical Insurance'

    name = fields.Char(string="Name")
    code = fields.Char(string="Code")
    amount = fields.Float(string="Amount")



