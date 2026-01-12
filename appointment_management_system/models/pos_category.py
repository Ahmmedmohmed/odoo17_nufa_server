# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PosCategoryAppointment(models.Model):
    _inherit = 'pos.category'

    is_appointment_category = fields.Boolean(string='Appointment Category')
    image = fields.Image(string='Category Image', max_width=512, max_height=512)

    def action_available_in_appointment(self):
        self.write({'is_appointment_category': True})

    def action_unavailable_in_appointment(self):
        self.write({'is_appointment_category': False})
