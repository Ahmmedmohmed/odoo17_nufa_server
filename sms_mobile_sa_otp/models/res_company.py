from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    latitude = fields.Float(string="Latitude", digits=(10, 6))
    longitude = fields.Float(string="Longitude", digits=(10, 6))

    work_time_from = fields.Float(string="Work Time From (Hours)")
    work_time_to = fields.Float(string="Work Time To (Hours)")
