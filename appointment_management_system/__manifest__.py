# -*- coding: utf-8 -*-
{
    'name': 'Appointment Management System',

    'version': '1.0',

    'category': 'Custom',

    'summary': 'A system for managing appointments.',

    'depends': ['base', 'hr', 'product', 'stock', 'point_of_sale' , 'pos_sales_commission'],

    'data': [
        # Data Files
        'data/ir_sequence.xml',
        'data/ir_cron.xml',

        # Security Files
        'security/ir.model.access.csv',
        'security/ir.rule.xml',

        # Views اللي بتعرّف الـ actions (لازم قبل menus.xml)
        'views/appointment_management.xml',
        'views/appointment_refund_policy.xml',
        'views/pos_category.xml',
        'views/product.xml',
        'views/hr_employee.xml',
        'views/hr_department.xml',
        'views/appointment_employee_slot.xml',
        'views/res_company.xml',
        'views/report_receipt_template.xml',
        'views/appointment_refund_request.xml',
        'views/booking_client_action.xml',

        # القائمة الرئيسية الأول، عشان أي ملف بعدها يضيف submenus يلاقيها
        'views/menus.xml',

        # ملفات بتضيف قوائم تحت menu_appointment_root / menu_appointment_configuration
        'views/Commissions_viwe.xml',
        'views/employee_report.xml',
        'views/res_config_settings_views.xml',
        'views/Commission_settings_views.xml',  # لازم بعد res_config_settings_views.xml (بيورّث منه)

        'Invoices/report_pos_receipt.xml',
        'Invoices/report_invoice_template.xml',
        'Invoices/saleorder_report.xml',
    ],

'assets': {
        'web.assets_backend': [
            'appointment_management_system/static/src/views/calendar/calendar_controller.xml',
            'appointment_management_system/static/src/xml/calendar_header.xml',
            'appointment_management_system/static/src/css/kanban.css',
            'appointment_management_system/static/src/js/booking_screen.js',
            'appointment_management_system/static/src/xml/booking_screen.xml',
            'appointment_management_system/static/src/js/override_create_button.js',
        ],
        'point_of_sale._assets_pos': [
            'appointment_management_system/static/src/xml/pos_reperot.xml',
            'appointment_management_system/static/src/js/pos_receipt_fix.js',
        ],
    },

    'installable': True,

    'application': True,

}