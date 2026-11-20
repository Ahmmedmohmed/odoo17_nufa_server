from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    location_ids = fields.One2many('res.partner.location', 'partner_id', string='Locations')

class ResPartnerLocation(models.Model):
    _name = 'res.partner.location'
    _description = 'Partner Location'

    partner_id = fields.Many2one('res.partner', ondelete='cascade')
    label = fields.Char('Label', required=True)
    address = fields.Char('Address')
    building_name = fields.Char('Building Name')
    apartment_number = fields.Char('Apartment Number')
    floor = fields.Char('Floor')
    street = fields.Char('Street')
    latitude = fields.Float('Latitude')
    longitude = fields.Float('Longitude')
    additional_info = fields.Text('Additional Info')