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
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    services_line_ids = fields.One2many('appointment.management.line', 'appointment_id', string='Services Lines')


    @api.model
    def create(self, vals):
        if vals.get('sequence', _('New')) == _('New'):
            vals['sequence'] = self.env['ir.sequence'].next_by_code('appointment.management.sequence') or _('New')
        return super(AppointmentManagement, self).create(vals)