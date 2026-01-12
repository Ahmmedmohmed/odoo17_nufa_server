# -*- coding: utf-8 -*-

from . import controllers
from . import models

# Post-install hook
def post_init_hook(env):
    """Called after module installation to create menu"""
    # Check if menu already exists
    existing_menu = env['website.menu'].search([
        ('name', '=', 'Book Appointment'),
        ('url', '=', '/book-appointment')
    ])
    
    if existing_menu:
        return existing_menu
    
    # Get main menu
    try:
        main_menu = env.ref('website.main_menu')
    except:
        return False
    
    # Create the menu
    menu_vals = {
        'name': 'Book Appointment',
        'url': '/book-appointment',
        'parent_id': main_menu.id,
        'sequence': 25,
    }
    
    return env['website.menu'].create(menu_vals)