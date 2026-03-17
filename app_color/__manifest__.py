{
    'name': 'App Color',
    'version': '17.01',
    'category': 'Custom',
    "author": "Ahmed Ali",
    'description': 'Custom module for managing colors in app categories',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/app_color_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
