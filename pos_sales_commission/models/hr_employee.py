# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    # الحقل الذي يبحث عنه أودو ويسبب الخطأ
    service_commission_ids = fields.One2many(
        'employee.service.commission',
        'employee_id',
        string='Service Commissions'
    )