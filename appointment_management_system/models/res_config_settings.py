from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    slot_wait_time = fields.Integer(
        string="وقت الحجز المعلق داخل سلة المشتريات (بالدقائق)",
        config_parameter="appointment_management_system.slot_wait_time",
        default=10,
    )