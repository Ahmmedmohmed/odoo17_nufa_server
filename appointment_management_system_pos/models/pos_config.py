# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.osv.expression import AND


class PosConfig(models.Model):
    _inherit = 'pos.config'

    allow_appointment = fields.Boolean(
        string="Allow Appointments")

    def _employee_domain_appointment(self):
        domain = self._check_company_domain(self.company_id)
        domain = AND([
            domain,
            [('is_appointment_employee', '=', True)]
        ])
        return domain

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_appointment = fields.Boolean(related='pos_config_id.allow_appointment', readonly=False,
        string="Allow Appointments")
