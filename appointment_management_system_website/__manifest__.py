# -*- coding: utf-8 -*-
{
    'name': 'Appointment Management System Website',

    'version': '17.0.1.0.0',

    'category': 'Website/Website',

    'summary': 'Website booking system for salon appointments',

    'description': """ Appointment Management System Website """,
    
    'depends': [
        'base',
        'base_automation',
        'website',
        'website_sale',
        'sale',
        'portal',
        'account',
        'appointment_management_system',
    ],


    'data': [
        # Security - Load groups first, then access rights
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Views
        'views/website_templates.xml',
        'views/portal_templates.xml',
        'views/authentication_required_template.xml',
        'views/sale_order_line_views.xml',
        'views/appointment_views.xml',
        'views/res_company_views.xml',
        
        # Data
        'data/website_menu.xml',
        'data/sample_categories.xml',
        'data/ir_cron.xml',
    ],


    'assets': {
        'web.assets_frontend': [
            'appointment_management_system_website/static/src/css/booking.css',
            'appointment_management_system_website/static/src/css/branch_popup.css',
            'appointment_management_system_website/static/src/js/branch_popup.js',
        ],
    },


    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}