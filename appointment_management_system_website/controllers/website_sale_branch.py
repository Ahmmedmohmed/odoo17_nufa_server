# -*- coding: utf-8 -*-

import base64
import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class WebsiteSaleBranch(WebsiteSale):

    @http.route(['/shop/cart/update'], type='http', auth='public', methods=['POST'], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0,
                    product_custom_attribute_values=None, no_variant_attribute_values=None,
                    express=False, **kwargs):
        branch_id = kwargs.pop('branch_id', False)
        res = super().cart_update(
            product_id, add_qty=add_qty, set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            express=express, **kwargs
        )
        if branch_id:
            order = request.website.sale_get_order()
            if order:
                last_line = order.order_line.filtered(
                    lambda l: l.product_id.id == int(product_id)
                ).sorted('id', reverse=True)[:1]
                if last_line:
                    last_line.sudo().write({'branch_id': int(branch_id)})
        return res

    @http.route(['/shop/cart/update_json'], type='json', auth='public', methods=['POST'], website=True, csrf=False)
    def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None,
                         display=True, product_custom_attribute_values=None,
                         no_variant_attribute_values=None, **kw):
        branch_id = kw.pop('branch_id', False)
        res = super().cart_update_json(
            product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty,
            display=display, product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values, **kw
        )
        if branch_id:
            order = request.website.sale_get_order()
            if order:
                last_line = order.order_line.filtered(
                    lambda l: l.product_id.id == int(product_id)
                ).sorted('id', reverse=True)[:1]
                if last_line:
                    last_line.sudo().write({'branch_id': int(branch_id)})
        return res


class BranchPopupController(http.Controller):

    @http.route('/shop/branches', type='json', auth='public', website=True)
    def get_branches(self):
        companies = request.env['res.company'].sudo().search([
            ('show_in_branch_popup', '=', True)
        ])
        result = []
        for company in companies:
            logo_url = False
            if company.logo:
                logo_url = f'/web/image/res.company/{company.id}/logo'
            result.append({
                'id': company.id,
                'name': company.name,
                'logo': logo_url,
            })
        return result
