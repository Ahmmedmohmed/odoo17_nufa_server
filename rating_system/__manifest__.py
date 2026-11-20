{
    'name': ' Rating System',
    'version': '1.0',
    'author': 'Kabir',
    'category': 'Inventory',
    'depends': ['base', 'stock', 'hr', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/rating_views.xml',
    ],
    'installable': True,
    'application': True,
}