# -*- coding: utf-8 -*-
{
    'name': 'Appointment Management System',

    'version': '1.0',

    'category': 'Custom',

    'summary': 'A system for managing appointments.',

    'depends': ['base', 'hr', 'product', 'stock'],

    'data': [
        # Data Files
        'data/ir_sequence.xml',

        # Security Files
        'security/ir.model.access.csv',

        # Views Files
        'views/appointment_management.xml',
        'views/product.xml',
        'views/hr_employee.xml',

        'views/menus.xml',
    ],

    'installable': True,

    'application': True,
}