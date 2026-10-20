{
    'name': 'HyperPay API Integration',
    'version': '1.0',
    'category': 'Accounting/Payment Providers', # إضافة التصنيف بيسهل ظهوره في الـ Apps
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_provider_views.xml',
        'views/templates.xml',
'views/payment_hyperpay_templates.xml',
        'data/payment_provider_data.xml',

        # 'data/payment_provider_data.xml',  <-- لو عندك ملف داتا فعل السطر ده
    ],
    'assets': {
        'web.assets_frontend': [
            'hyperpay_api_integration/static/src/js/hyperpay_fix.js',
        ],
    },
    'installable': True,
    'application': True, # خليه Application عشان يظهر في فلتر التطبيقات بسهولة
    'license': 'LGPL-3',
}