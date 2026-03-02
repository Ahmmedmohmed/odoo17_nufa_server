{
    'name': 'Product Merge Tool',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Merge duplicate products by internal reference and name',
    'depends': ['base', 'product', 'appointment_management_system'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_merge_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
