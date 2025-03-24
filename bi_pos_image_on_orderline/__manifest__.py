# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Order Line Image | Image in POS Order line',
    'version': '17.0',
    'category': 'Point of Sale',
    'summary': 'Image on POS Order Line show product image on POS Order line point of sales order line image on point of sales order line pos line product image on pos order line pos order line product image on point of sales order line product image on pos line',
    'description': """
       
       This Odoo App helps users to show product image on POS Order line. User can enable 'Show Image In Order line' checkbox from POS configuration to show image for each product in POS and back-end POS order also.
    
    """,
    'author': 'BrowseInfo',
    'website': 'https://www.browseinfo.com',
    'depends': ['base', 'point_of_sale'],
    'data': [
        'view/pos_config_view.xml',
        'view/pos_order_view.xml',
    ],
    'assets': {

        'point_of_sale._assets_pos': [
            'bi_pos_image_on_orderline/static/src/app/orderline.xml',
            'bi_pos_image_on_orderline/static/src/app/models.js',
        ],
        
    },
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/CdVnO_EiaAQ',
    "images":['static/description/Banner.gif'],
}
