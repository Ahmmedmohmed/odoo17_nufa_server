{
    "name": "Contact First Name and Last Name",
    "summary": "First Name And Last Name for Contacts",
    "description": """
               First Name And Last Name for Contacts
    """,
    "version": "17.0.1.0.0",
     "author": "One Stop Odoo",
    "website": "https://onestopodoo.com",
    "maintainer": "One Stop Odoo",
    "category": "Extra Tools",
    "license": "LGPL-3",
    "depends": ["base_setup"],
    # "post_init_hook": "post_init_hook",
    "data": [
        "views/base_config_view.xml",
        "views/res_partner.xml",
        "views/res_user.xml",
    ],
    "images": [
        'static/description/banner.gif',
        'static/description/icon.png',
    ],
    "auto_install": False,
    "installable": True,
}
