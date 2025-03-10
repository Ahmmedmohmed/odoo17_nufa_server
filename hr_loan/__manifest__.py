# -*- coding: utf-8 -*-
{
    'name': "HR Loans",

    'summary': """
        Loans give for employee""",

    'description': """
        Loans give for employee
    """,

    'author': "DeeB",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '17.0.1.8',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['hr_structure_advanced', 'account_accountant', 'hr_payslip_operations_menu',
                'hr_employees_operations_menu', 'hr_attendance', 'base', 'account'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/mail_subtypes.xml',
        'data/salary_rules.xml',
        'wizard/confirm_hr_loan_views.xml',
        'wizard/compute_installments_hr_loan_views.xml',
        'wizard/cancel_reject_hr_loan_views.xml',
        'wizard/hr_loan_installment_payment_views.xml',
        'views/account_payment_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_loan_views.xml',
        'views/menus.xml',
        'report/hr_loan_report.xml',
        'report/report.xml',
    ],
    'application': True,
}
