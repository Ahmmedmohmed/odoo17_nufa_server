# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Stock Delivery Custom',
    'version': '1.0',
    'category': '',
    'summary': 'Create Custom',
    'description': """

""",
    'depends': ['account','sale','hr','stock'],
    'data': [
        'views/stock_picking_view.xml',
        'reports/delivery_slip_signature.xml',

    ],
    'installable': True,
    'auto_install': False,
}
