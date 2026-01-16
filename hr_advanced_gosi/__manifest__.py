# -*- coding: utf-8 -*-
{
    'name': "HR Advanced GOSI",

    'summary': """HR Advanced GOSI""",

    'description': """
    add fields of gosi to contract
    """,

    'author': "Mohammed Reffat",
    'license': 'LGPL-3',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '17.0.1.8',

    # any module necessary for this one to work correctly
    'depends': ['hr_payroll', 'hr_structure_advanced', 'hr'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payroll_data.xml',
        'views/hr_contract_views.xml',
        'views/gosi_saudi.xml',
    ]
}
