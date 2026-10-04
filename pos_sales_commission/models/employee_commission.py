# -*- coding: utf-8 -*-
from odoo import models, fields, api

class EmployeeServiceCommission(models.Model):
    _name = 'employee.service.commission'
    _description = 'Employee Service Commission Rate'

    employee_id = fields.Many2one('hr.employee', string='Service Provider', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Service', domain=[('type', '=', 'service')], required=True)
    commission_percentage = fields.Float(string='Commission (%)', required=True)

    _sql_constraints = [
        ('employee_product_uniq', 'unique (employee_id, product_id)', 'The commission rate for this service is already set for this employee!')
    ]