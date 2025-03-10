# -*- coding: utf-8 -*-

{
    'name': 'Biometric Device Integration PyZk',
    'version': '17.0.1.0',
    'summary': """Integrating Biometric Device With HR Attendance (Face + Thumb)""",
    'description': 'This module integrates Odoo with the biometric device. (Check below or README.md for compatible devices.)',
    'category': 'Generic Modules/Human Resources',
    'author': '10 Orbits',
    'company': '10 Orbits',
    'website': "https://",
    'depends': ['base_setup', 'hr_attendance', 'hr_attendance_contract_custom'],
    'data': [
        'security/ir.model.access.csv',
        'views/zk_machine_view.xml',
        'views/zk_machine_attendance_view.xml',
        'data/download_data.xml',

    ],
    'css': ['static/src/description.css'],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
