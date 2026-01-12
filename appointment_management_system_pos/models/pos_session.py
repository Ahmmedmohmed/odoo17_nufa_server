# -*- coding: utf-8 -*-

from odoo import models
from odoo.osv.expression import OR
import ast
import json


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if self.config_id.allow_appointment:
            result.append('appointment.product.category')
            result.append('appointment.product.service')
            result.append('appointment.package.line')
        return result


    def _loader_params_appointment_product_category(self):
        return {'search_params': {'domain': [('is_appointment_category', '=', True)], 'fields': ['name', 'id']}}


    def _get_pos_ui_appointment_product_category(self, params):
        categories = self.env['pos.category'].search_read(**params['search_params'])
        category_by_id = {category['id']: category for category in categories}
        return categories

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].extend(['is_appointment_service','is_appointment_package','appointment_package_line_ids'])
        return result


    def _loader_params_appointment_product_service(self):
        return {'search_params': {'domain': [('is_appointment_service', '=', True)], 'fields': ['name', 'id', 'categ_id','is_appointment_package','appointment_package_line_ids']}}


    def _get_pos_ui_appointment_product_service(self, params):
        services = self.env['product.product'].search_read(**params['search_params'])
        service_by_categ_id = {}
        for rec in services:
            if rec['categ_id'][0] in service_by_categ_id:
                service_by_categ_id[rec['categ_id'][0]].append(rec)
            else:
                service_by_categ_id[rec['categ_id'][0]] = []
                service_by_categ_id[rec['categ_id'][0]].append(rec)
        final_result = {'appointment_services':services, 'appointment_services_by_categ_id':service_by_categ_id}
        return final_result

    def _loader_params_appointment_package_line(self):
        return {'search_params': {'domain': [], 'fields': ['id','product_id']}}


    def _get_pos_ui_appointment_package_line(self, params):
        packages = self.env['appointment.package.line'].search_read(**params['search_params'])
        package_by_id = {package['id']: package for package in packages}
        final_result = {'appointment_packages':packages, 'appointment_package_by_id':package_by_id}
        return final_result
