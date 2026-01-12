{
    "name": "SMS OTP via Mobile.sa (mobile.net.sa)",
    "version": "17.0.1.0.0",
    "summary": "OTP generation & verification using Mobile.sa SMS Gateway",
    "category": "Tools",
    "author": "Ahmed Ali",
    "license": "LGPL-3",
    "depends": ["base", "web",'account','app_color','stock','sale_loyalty','point_of_sale','appointment_management_system'],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/product.xml",
        "views/res_company.xml",
        "views/sale_order.xml",
    ],
    "installable": True,
    "application": False,
}
