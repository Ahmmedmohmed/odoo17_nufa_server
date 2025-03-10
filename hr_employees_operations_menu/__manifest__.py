# -*- coding: utf-8 -*-
{
    'name': "HR Employees Operations Menu",

    'summary': """
        HR Employees Operations Menu""",

    'description': """
    HR Employees Operations Menu
    """,

    'author': "DeeB",
    'license': 'LGPL-3',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '17.0.1.8',

    # any module necessary for this one to work correctly
    'depends': ['hr_payroll', 'account_accountant'],

    # always loaded
    'data': [
        'views/menu_employees_operations.xml'
    ]
}
