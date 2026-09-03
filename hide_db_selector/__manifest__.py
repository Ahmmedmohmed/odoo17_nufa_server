# -*- coding: utf-8 -*-
{
    'name': 'Hide Database Selector',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'إخفاء حقل قاعدة البيانات من صفحة تسجيل الدخول',
    'author': 'Custom',
    'depends': ['web'],
    'assets': {
        'web.assets_frontend': [
            'hide_db_selector/static/src/css/hide_db.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
