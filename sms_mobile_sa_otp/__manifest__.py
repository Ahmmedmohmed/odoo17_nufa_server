{
    "name": "SMS OTP via Mobile.sa (mobile.net.sa)",
    "version": "17.0.1.0.1",
    "summary": "OTP generation & verification using Mobile.sa SMS Gateway",
    "category": "Tools",
    "author": "Ahmed Ali",
    "license": "LGPL-3",
    "depends": ["base", "web", "account", "app_color", "stock", "point_of_sale", "appointment_management_system"],
    "data": [
        "security/ir.model.access.csv",
        "data/wallet_sequence.xml",
        "data/ewallet_program_data.xml",
        "data/stock_notification_data.xml",
        "views/report_pos_receipt.xml",
        "views/report_invoice_template.xml",
        "views/saleorder_report.xml",
        "views/res_paratner_views.xml",
        "views/product.xml",
        "views/produect_reviwe.xml",
        # "views/res_company.xml",
        "views/sale_order.xml",
        "views/wallet_transfer_request_views.xml",
        # "views/partenerwalat.xml",
    ],
    "post_init_hook": "_post_init_hook",
    "installable": True,
    "application": False,

    # التعديل هنا 👇
    'assets': {
        'point_of_sale._assets_pos': [
            'sms_mobile_sa_otp/static/src/xml/pos_reperot.xml',
        ],
    }
}