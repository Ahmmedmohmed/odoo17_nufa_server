from odoo import http
from odoo.http import request

class PartnerLocationController(http.Controller):

    @http.route('/api/partner/locations', type='json', auth='public', methods=['POST'], csrf=False)
    def list_locations(self, **vals):
        """ List all locations for a specific partner """
        # Extract partner_id from the vals dictionary
        partner_id = vals.get('partner_id')

        if not partner_id:
            return {'error': 'partner_id is required'}

        locations = request.env['res.partner.location'].sudo().search([
            ('partner_id', '=', partner_id)
        ])

        return [{
            'id': loc.id,
            'label': loc.label,
            'address': loc.address,
            'buildingName': loc.building_name,
            'apartmentNumber': loc.apartment_number,
            'floor': loc.floor,
            'street': loc.street,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'additionalInfo': loc.additional_info,
        } for loc in locations]

    @http.route('/api/partner/location/add', type='json', auth='public', methods=['POST'])
    def add_location(self, partner_id, **vals):
        """ Create a new address for a partner """
        # Map API field names to Odoo field names
        data = {
            'partner_id': partner_id,
            'label': vals.get('label'),
            'address': vals.get('address'),
            'building_name': vals.get('buildingName'),
            'apartment_number': vals.get('apartmentNumber'),
            'floor': vals.get('floor'),
            'street': vals.get('street'),
            'latitude': vals.get('latitude'),
            'longitude': vals.get('longitude'),
            'additional_info': vals.get('additionalInfo'),
        }
        new_loc = request.env['res.partner.location'].sudo().create(data)
        return {'status': 'success', 'location_id': new_loc.id}

    @http.route('/api/partner/location/update', type='json', auth='public', methods=['POST'], csrf=False)
    def update_location(self, **vals):
        """ Update an existing location using data from the params dictionary """
        # Extract location_id from vals instead of the function signature
        location_id = vals.get('location_id')
        
        if not location_id:
            return {'status': 'error', 'message': 'location_id is required'}
            
        loc = request.env['res.partner.location'].sudo().browse(location_id)
        if not loc.exists():
            return {'status': 'error', 'message': 'Location not found'}
        
        # Mapping API fields to Odoo snake_case fields
        mapping = {
            'label': 'label', 
            'address': 'address',
            'buildingName': 'building_name', 
            'apartmentNumber': 'apartment_number', 
            'floor': 'floor', 
            'street': 'street',
            'latitude': 'latitude', 
            'longitude': 'longitude', 
            'additionalInfo': 'additional_info'
        }
        
        update_data = {odoo_key: vals[api_key] for api_key, odoo_key in mapping.items() if api_key in vals}
        
        if update_data:
            loc.write(update_data)
            
        return {'status': 'success'}

    @http.route('/api/partner/location/delete', type='json', auth='public', methods=['POST'], csrf=False)
    def delete_location(self, **vals):
        """ Delete a location using location_id from the params dictionary """
        location_id = vals.get('location_id')
        
        if not location_id:
            return {'status': 'error', 'message': 'location_id is required'}
            
        loc = request.env['res.partner.location'].sudo().browse(location_id)
        if loc.exists():
            loc.unlink()
            return {'status': 'success'}
            
        return {'status': 'error', 'message': 'Location not found'}