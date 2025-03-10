{
    'name': "Inter Warehouse Transfer",
    'version' : '1.2',
    'author': 'Preciseways',
    'summary': """Internal transfer of goods from one warehouse to another warehouse""",
    'description': "Internal transfer of goods from one warehouse to another warehouse",
    "category": "warehouse",
    'depends': ['stock','base'],
    'data': [
        'data/stock_data.xml',
        'views/groups_security.xml',
        'security/ir.model.access.csv',
        'views/stock_transfer_view.xml',
    ],
    'application': False,
    'installable': True,
    'price': 17,
    'currency': 'EUR',
    "images": ['static/description/banner.jpg'],
     'license': 'LGPL-3',
}

