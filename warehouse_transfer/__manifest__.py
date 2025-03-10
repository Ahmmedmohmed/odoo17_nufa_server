# -*- coding: utf-8 -*-
{
    'name': 'Warehouse Transfer',

    'version': '1.0',

    'category': 'Inventory/Inventory',

    'author': 'Sanad Technologies',

    'maintainer': 'Sanad Technologies',

    'summary': 'Transfer stock from one company to other company without SO/PO',

    'description': """ Warehouse Transfer """,

    'depends': ['base', 'web', 'stock_account', 'product_expiry'],

    'data': ['data/stock_location.xml', 'security/ir.model.access.csv', 'wizards/warehouse_transfer.xml', 'views/stock_picking.xml'],
}
