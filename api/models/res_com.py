from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    # إضافة إحداثيات الموقع الجغرافي للشركة
    partner_latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
    partner_longitude = fields.Float(string='Geo Longitude', digits=(10, 7))
