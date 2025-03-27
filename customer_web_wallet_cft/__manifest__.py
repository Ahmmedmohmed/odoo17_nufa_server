# -*- coding: utf-8 -*-

{
    'name': 'Website Wallet Management',
    'version': '1.0',
    'author': 'Craftsync Technologies',
    'category': 'Website',
    'maintainer': 'Craftsync Technologies',
    'summary': """Manage customer wallet on website. Customer can add money to 
                  wallet and use it for online shopping or can pay for due
                  invoices. Customer can add money in wallet using any Payment 
                  acquirer active on website.
                  Keywords
                  customer wallet e-wallet fund money website web wallet stripe
                  autorize.net paypal payment acquirer payment gateway
                  """,
    'description': """
        [1] Add funds to Wallet.
        [2] Use wallet funds in shopping and paying invoices.
        [3] Track wallet transaction on website.
    """,
    'website': 'https://www.craftsync.com/',
    'license': 'OPL-1',
    'support': 'info@craftsync.com',
    'depends': ['website_sale'],
    'data': [
        'data/wallet_payment_transaction_sequence.xml',
        'data/wallet_acquirer.xml',
        'views/assets.xml',
        'views/res_partner.xml',
        'views/payment_view.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/main_screen.png'],
    'price': 49.98,
    'currency': 'USD'
}
