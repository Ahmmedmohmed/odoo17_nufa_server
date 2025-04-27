# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AppointmentRefundPolicy(models.Model):
    _name = 'appointment.refund.policy'
    _description = 'Appointment Refund Policy'


    hours_before_appointment = fields.Integer(string='Hours Before Appointment', required=True)
    percentage = fields.Float(string='Percentage (%)', required=True)