# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResPartner(models.Model):
	_inherit = "res.partner"


	cr_number = fields.Char(string='CR Number')