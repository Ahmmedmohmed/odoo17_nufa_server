# -*- coding: utf-8 -*-
{
    'name': "HR Saudi Contract",

    'summary': """HR Advanced Contract""",

    'description': """
    add fields of gosi to contract
    """,

    'author': "Neotic Hub",

    'category': 'Human Resources',
    'version': '17.0',

    # any module necessary for this one to work correctly
    'depends': ['hr_payroll'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payroll_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_medical_insurance.xml',
    ]
}
