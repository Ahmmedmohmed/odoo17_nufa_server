# models/app_config.py
from odoo import models, fields

class MobileAppConfig(models.Model):
    _name = 'mobile.app.config'
    _description = 'Mobile App Update Controls'

    platform = fields.Selection([
        ('android', 'Android'),
        ('ios', 'iOS')
    ], string='Platform', required=True, default='android')

    exact_blocked_version = fields.Char(string='Exact Blocked Version', help='Example: 5.2.7')
    min_supported_version = fields.Char(string='Minimum Supported Version', help='Example: 5.3.0')
    maintenance_mode = fields.Boolean(string='Maintenance Mode', default=False)
    maintenance_message = fields.Text(string='Maintenance Message', default="Scheduled maintenance. We'll be back soon.")

    # Metadata
    updated_by = fields.Many2one('res.users', string='Updated By', default=lambda self: self.env.user, readonly=True)
    change_reason = fields.Char(string='Change Reason')
    updated_at = fields.Datetime(string='Updated At', auto_now=True)