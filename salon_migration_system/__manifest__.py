{
    'name': 'Salon Migration System',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Migrate salon data between Odoo databases',
    'depends': ['base', 'product', 'appointment_management_system'],
    'data': [
        'security/ir.model.access.csv',
        'views/salon_migration_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
