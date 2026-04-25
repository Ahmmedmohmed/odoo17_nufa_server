# -*- coding: utf-8 -*-
{
    'name': 'POS Loyalty Component Fix',
    'version': '1.0.0',
    'category': 'Point of Sale',
    'sequence': 5,  # Higher priority than pos_loyalty
    'summary': 'Fix component destruction error in POS loyalty',
    'depends': ['pos_loyalty'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_loyalty_fix/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}