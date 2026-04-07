{
    'name': 'Banner Module',
    'version': '1.0',
    'category': 'Tools',
    'author': 'Kabir',
    'summary': 'Manage banners and expose them via API',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/banner_views.xml',
        'views/banner_menus.xml',
    ],
    'installable': True,
    'application': True,
}