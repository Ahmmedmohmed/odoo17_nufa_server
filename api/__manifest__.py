# -*- coding: utf-8 -*-
{
    'name': "api",
    'author': "Ahmed Ali",
    'version': '17.01',
    'depends': ['base', 'sale_management', 'purchase', 'stock', "product", 'mail','sms_mobile_sa_otp','pos_loyalty','point_of_sale','appointment_management_system'],

    'data': [
        # 'security/ir.model.access.csv',
        'views/product.xml',
        'views/pos_combo.xml',

    ],

}
