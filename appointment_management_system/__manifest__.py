# -*- coding: utf-8 -*-
{
    'name': 'Appointment Management System',

    'version': '1.0',

    'category': 'Custom',

    'summary': 'A system for managing appointments.',

    'depends': ['base', 'hr', 'product', 'stock', 'point_of_sale'],

    'data': [
        # Data Files
        'data/ir_sequence.xml',
        'data/ir_cron.xml',


        # Security Files
        'security/ir.model.access.csv',


        # Views Files
        'views/appointment_management.xml',
        'views/appointment_refund_policy.xml',
        'views/pos_category.xml',
        'views/product.xml',
        'views/hr_employee.xml',
        'views/hr_department.xml',
        'views/appointment_employee_slot.xml',
        'views/res_company.xml',

        # Menu File
        'views/menus.xml',
    ],

    'installable': True,

    'application': True,
}
