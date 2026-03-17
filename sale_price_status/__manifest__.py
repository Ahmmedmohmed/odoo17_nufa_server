# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Financial Status For Sales',
    'version': '1.0',
    'category': '',
    'summary': 'Create Custom',
    'description': """

""",
    'depends': ['account','sale','hr','stock'],
    'data': [
        'views/sale_order_view.xml',
        'views/stock_picking_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
