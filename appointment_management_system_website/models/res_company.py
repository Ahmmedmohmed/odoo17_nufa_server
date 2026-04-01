# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    show_in_branch_popup = fields.Boolean(string='Show in Branch Selection', default=False)
