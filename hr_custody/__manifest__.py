# -*- coding: utf-8 -*-
{
    'name': "HR Custodies",
    'summary': """Custodies for Employees""",
    'description': """
        Custodies for Employees
    """,
    'author': "DeeB",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '0.1',
    'odoo_version': '17.0.1.8',
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['sale_stock', 'hr_payslip_operations_menu', 'hr_employees_operations_menu'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/mail_subtypes.xml',
        'wizard/cancel_reject_hr_custody_views.xml',
        'wizard/approve_hr_custody_views.xml',
        'views/employee.xml',
        'views/hr_custody_views.xml',
        'views/res_config_views.xml',
        'views/templates.xml',
        'views/menus.xml'
    ],
    'application': True,
    'assets': {

    }
}
