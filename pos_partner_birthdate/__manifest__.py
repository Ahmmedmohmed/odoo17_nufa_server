# -*- coding: utf-8 -*-
{
    "name": "Point of Sale - Partner contact Additional Information",

    "summary": "Point of Sale - Partner contact Additional Information",

    "version": "17.0.1.0.4",

    "category": "Point of sale",

    "depends": ["base", "point_of_sale"],

    "data": ['views/res_partner.xml'],

    "assets": {"point_of_sale._assets_pos": ["pos_partner_birthdate/static/src/xml/PartnerDetailsEdit.xml", "pos_partner_birthdate/static/src/js/PartnerDetailsEdit.js"]},
}