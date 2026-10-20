{
    'name': 'HyperPay API Integration',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'depends': ['payment', 'website_sale', 'sale_loyalty'],  # + الموديول اللي فيه appointment.management
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_hyperpay_templates.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'hyperpay_api_integration/static/src/js/hyperpay_fix.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {'python': ['jwt', 'requests']},
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}