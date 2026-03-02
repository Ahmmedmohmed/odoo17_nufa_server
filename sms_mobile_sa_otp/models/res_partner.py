from odoo import models, fields, api, _
import random
from datetime import datetime, timedelta

from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    password = fields.Char()
    otp_code = fields.Char(string="OTP Code")
    otp_expiration = fields.Datetime(string="OTP Expiration")
    otp_sent = fields.Boolean(string="OTP Sent", default=False)
    fcm_token = fields.Char()
    long = fields.Char()
    late = fields.Char()

    refresh_token = fields.Char(string="Refresh Token")
    refresh_token_expiration = fields.Datetime(string="Refresh Token Expiration")

    birthday = fields.Date(string="Birthday")
    marriage_date = fields.Date(string="Marriage Date")
    verify = fields.Boolean(string="Verified", default=False, help="True when the user verifies OTP successfully.")
    exist = fields.Boolean(default=False)

    @api.constrains('phone', 'mobile', 'country_id')
    def _check_phone_length_by_country(self):
        for partner in self:
            country = partner.country_id
            if not country or not country.phone_length:
                continue

            for field_name, label in [('phone', _('Phone')), ('mobile', _('Mobile'))]:
                number = partner[field_name]
                if not number:
                    continue

                digits = ''.join(ch for ch in number if ch.isdigit())

                if len(digits) != country.phone_length:
                    raise ValidationError(_(
                        "%(field)s number must contain %(length)s digits for country %(country)s.",
                    ) % {
                                              'field': label,
                                              'length': country.phone_length,
                                              'country': country.name,
                                          })


class ResCountry(models.Model):
    _inherit = 'res.country'

    phone_length = fields.Integer(
        string='Phone Number Length',
        help='Required phone/mobile digits length for partners in this country.'
    )
