# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AppointmentManagement(models.Model):
    _name = 'appointment.management'
    _description = 'Appointment Management'
    _check_company_auto = True
    _rec_name = 'sequence'


    sequence = fields.Char('Appointment Sequence', default=lambda self: _('New'), required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    date = fields.Datetime('Date', required=True)
    branch_id = fields.Many2one('res.company', string='Branch', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    product_id = fields.Many2one('product.product', string='Service', domain=[('is_appointment_service', '=', True)], required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', domain=[('is_appointment_employee', '=', True)], required=True)
    price_unit = fields.Float('Unit Price', required=True)
    service_rate = fields.Selection([('0', 'Low'), ('1', 'Medium'), ('2', 'High'), ('3', 'Very High')], string='Rating')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    appointment_id = fields.Many2one('appointment.management', string='Appointment', required=True)
    state = fields.Selection([('draft', 'Draft'), ('partial', 'Partial Approved'), ('approved', 'Approved'), ('complated', 'Complated'), ('cancelled', 'Cancelled')], default='draft')
    appointment_type = fields.Selection([('inside', 'Inside'), ('outside', 'Outside')], default='inside', required=True)
    notes = fields.Text('Notes')


    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('appointment.management.sequence') or _('New')
        return super(AppointmentManagement, self).create(vals)