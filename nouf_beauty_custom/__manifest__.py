{
    'name': 'Nouf Beauty Customizations',
    'version': '17.0.1.0.0',
    'category': 'Customization',
    'summary': 'Unified customizations for Nouf Beauty (POS, Appointments, etc.) ',
    'author': 'Kaya Tech',
    'depends': ['base', 'contacts'],
    'data': [
        'views/res_partner_views.xml',
    ],

    'assets': {
            'point_of_sale._assets_pos': [
                'nouf_beauty_custom/static/src/js/partner_editor_validation.js',
            ],
        },
    'installable': True,
    'application': False,
    'auto_install': False,
}