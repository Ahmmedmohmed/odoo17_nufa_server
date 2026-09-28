# -*- coding: utf-8 -*-
{
    'name': 'Nouf Custom Translations',
    'version': '1.0',
    'category': 'Localization',
    'summary': 'Custom Arabic translations for Nouf Group',
    'depends': [
        'base',
        'point_of_sale',
        'sale_management',
        'hr',
        'account',
        'stock',
        'appointment_management_system'
    ],
    'data': [
        'data/update_countries_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}