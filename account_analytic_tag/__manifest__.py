# Copyright 2023 Tecnativa - Yadier Quesada (https://www.tecnativa.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Account Analytic Tag",
    "version": "17.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "category": "Account",
    "website": "https://github.com/OCA/account-analytic",
    "depends": ["account_reports", "web", "analytic"],
    "data": [
        "security/analytic_security.xml",
        "security/ir.model.access.csv",
        "views/account_analytic_line_views.xml",
        "views/account_analytic_tag_views.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
        "views/views.xml",
    ],
    "license": "AGPL-3",
    "assets": {
        'web.assets_backend': [
            'account_analytic_tag/static/src/js/filters.js',
            'account_analytic_tag/static/src/xml/*.xml',
            ],
        },
        # 'web.assets_tests': [
        #     'account_analytic_tag/static/src/xml/custom_bank_rec_form1.xml',
        # ],
        # 'web.qunit_suite_tests': [
        #     'account_accountant/static/tests/*.js',
        #     'account_accountant/static/tests/helpers/*.js',
        # ],    
    "installable": True,
    "application": False,
}
