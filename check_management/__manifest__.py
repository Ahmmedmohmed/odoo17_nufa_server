# -*- coding: utf-8 -*-
{
    'name': "Check Management",
    'summary': """ Check Management accounting  """,
    'description': """This Module is used for check \n It includes creation of check receipt ,check cycle ,Holding ....... \n
    """,
    'author': "Ahmed Farid ( KAMAH ),ahmed mokhlef upgrade to 13e",
    'website': "01008339922",
    'category': 'Accounting',
    'version': '17.0.1.0.8',
    'depends': ['base', 'account', 'account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'data/sms_temp.xml',
        'views/account_journal_view.xml',
        'views/checks_fields_view.xml',
        'views/check_payment.xml',
        'views/check_menus.xml',
        'wizard/check_cycle_wizard_view.xml',
        'views/payment_report.xml',
        'views/report_check_cash_payment_receipt_templates.xml',
    ],
    'qweb': [],
    'demo': [],
    'license': 'GPL-3',
    'price': 249.0,
    'currency': 'EUR',
    'application': True,

}
