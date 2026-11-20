{
    'name': 'Partner Location Extension',
    'author': 'Kabir',
    'version': '1.0',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',  # Added this
        'views/res_partner_view.xml',
    ],
    'installable': True,
    'application': False,
}