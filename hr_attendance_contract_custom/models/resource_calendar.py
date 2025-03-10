from odoo import fields, models


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    is_2days = fields.Boolean(string='Is 2Days?')
