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
        'data/appointment_employee_slot_cron.xml',


        # Security Files
        'security/ir.model.access.csv',


        # Views Files
        'views/appointment_management.xml',
        'views/appointment_refund_policy.xml',
        'views/product.xml',
        'views/hr_employee.xml',
        'views/appointment_employee_slot.xml',

        # Menu File
        'views/menus.xml',
    ],

    'installable': True,

    'application': True,
}