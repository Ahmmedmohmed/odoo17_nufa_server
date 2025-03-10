# -*- coding: utf-8 -*-
{
    'name': "Expense Personal",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'category': 'Uncategorized',
    'version' : '1.2',
    'license': 'LGPL-3',
    'depends': ['base','hr','account','account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        "security/expense_security.xml",
        'views/views.xml',
        'views/print.xml',
        'views/res_partner_edit.xml',
        'wizard/personal_expense.xml',
        'wizard/personal_expense_report.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
}
