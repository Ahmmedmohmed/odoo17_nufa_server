from odoo import models, fields

class CustomBanner(models.Model):
    _name = 'custom.banner'
    _description = 'Banner Model'

    name = fields.Char(string='Name', required=True) # Mandatory [cite: 10]
    description = fields.Text(string='Description') # Optional [cite: 11]
    image = fields.Binary(string='Image')           # Optional 
    external_url = fields.Char(string='External URL') # Optional