# -*- coding: utf-8 -*-
{
    'name': 'Customer Loyalty Tiers',
    'version': '17.0.1.0.0',
    'summary': '',
    'author': 'ahmed mohmed ',
    'category': 'Sales/Sales',
    'depends': ['base', 'sale_management', 'loyalty', 'point_of_sale', 'sale_loyalty', 'sale_loyalty_delivery', 'sms_mobile_sa_otp'],
    'data': [
        'security/ir.model.access.csv',
        'views/loyalty_tier_views.xml',
        'views/res_partner_views.xml',
        'views/loyalty_reward_views.xml',
        'views/loyalty_rule_views.xml',
        'views/codeprifx.xml',

    ],

'assets': {
        'point_of_sale._assets_pos': [
            'partner_loyalty_tiers/static/src/js/pos_loyalty_patch.js',
             # 'partner_loyalty_tiers/static/src/js/pos_loyalty_diag.js',
             # 'partner_loyalty_tiers/views/OrderReceipt.xml',

        ],
    },
    'installable': True,
    'application': False,
}