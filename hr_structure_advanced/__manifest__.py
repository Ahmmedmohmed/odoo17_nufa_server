# -*- coding: utf-8 -*-
{
    'name': "HR Structure Advanced",

    'summary': """HR Structure Advanced""",

    'description': """HR Structure Advanced""",

    'author': "DeeB",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '17.0.1.8',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['hr_payroll'],

    # always loaded
    'data': ['data/data.xml']
}
