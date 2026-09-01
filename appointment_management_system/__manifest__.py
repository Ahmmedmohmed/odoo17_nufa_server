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


        # Views Files
        'views/appointment_management.xml',
        'views/appointment_refund_policy.xml',
        # 'views/Commissions_viwe.xml',
        'views/pos_category.xml',
        'views/product.xml',
        'views/hr_employee.xml',
        'views/hr_department.xml',
        'views/appointment_employee_slot.xml',
        'views/res_company.xml',
        # 'views/appointment_report.xml',
        'views/report_receipt_template.xml',
        'views/appointment_refund_request.xml',
        'views/res_config_settings_views.xml',
          'views/booking_client_action.xml',
        # Menu File
        'views/menus.xml',

        # قمنا برفع هذا الملف للأعلى لأنه يحتوي على كود إنشاء مقاس الورقة A4
        'Invoices/report_pos_receipt.xml',

        # الآن يمكن لهذه الملفات استخدام مقاس الورقة بأمان
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
        ],
    },

    'installable': True,

    'application': True,

}
