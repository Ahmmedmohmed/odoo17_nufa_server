{
    'name': 'Mobile App Update Controls',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage Mobile App Versions and Maintenance Mode via API',
    'description': """
        This module allows admins to:
        - Force update specific app versions.
        - Set minimum supported versions.
        - Enable/Disable maintenance mode for Android and iOS.
    """,
    'author': 'Ahmed Mohamed',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/app_config_view.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}