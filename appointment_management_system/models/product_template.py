# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'


    is_appointment_service = fields.Boolean(string='Appointment Service')
    plan_ids = fields.One2many('appointment.service.price.plan', 'service_id', string='Associated Plans')


    def action_get_associated_branch(self):
        for record in self:
            return record.plan_ids.mapped('branch_id')


    def action_get_associated_employee(self, branch_id):
        for record in self:
            return record.plan_ids.filtered(lambda r: r.branch_id.id == branch_id).mapped('employee_id')


    def action_get_service_price(self, branch_id, employee_id, type):
        for record in self:
            if type == 'inside':
                return record.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.employee_id.id == employee_id).service_price_inside
            else:
                return record.plan_ids.filtered(lambda r: r.branch_id.id == branch_id and r.employee_id.id == employee_id).service_price_outside