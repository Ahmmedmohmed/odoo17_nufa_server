# -*- coding: utf-8 -*-
{
    'name': 'Sales Person On POS Order',
    'Version': '17.0.0',
    'summary': 'This module is used to set sales persons on pos order , pos order line',

    'author': 'Mahmoud Fathi, Said Maged',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_orderline_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
                'salesperson_pos_order_line/static/src/js/pos_load_data.js',
                'salesperson_pos_order_line/static/src/js/pos_screen.js',
                'salesperson_pos_order_line/static/src/js/orderline.js',
                'salesperson_pos_order_line/static/src/js/pos_orderline.js',
                'salesperson_pos_order_line/static/src/xml/pos_screen_templates.xml',
                'salesperson_pos_order_line/static/src/xml/orderline_templates.xml',
            ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
