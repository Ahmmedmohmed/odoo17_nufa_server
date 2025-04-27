# -*- coding: utf-8 -*-
{
    'name': 'Appointment Management System POS',

    'version': '1.0',

    'category': 'Custom',

    'summary': 'A system for managing appointments.',

    'depends': ['appointment_management_system','point_of_sale'],

    'data': [

        'views/pos_config.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'appointment_management_system_pos/static/src/**/*',
        ],
    },
    'installable': True,

    'application': True,
}
