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
            # result.append('hr.employee.appointment')
            result.append('appointment.service.price.plan')
        return result

    def _loader_params_appointment_service_price_plan(self):
        domain = []
        # domain = [('branch_id', '=', self.company_id.id)]
        return {'search_params': {'domain': domain, 'fields': ['service_id','service_product_name', 'id', 'department_id', 'branch_id'], 'load': False}}

    def _get_pos_ui_appointment_service_price_plan(self, params):
        result = self.env['appointment.service.price.plan'].search_read(**params['search_params'])
        print(result)
        appointment_services = []
        appointment_service_price_plans_by_id = {}
        appointment_service_price_plans_by_product_id = {}
        for rec in result:
            appointment_service_price_plans_by_id[rec['id']] = rec
            if rec['service_id'] in appointment_service_price_plans_by_product_id:
                appointment_service_price_plans_by_product_id[rec['service_id']].append(rec)
            else:
                appointment_services.append({'id':rec['service_id'],'name':rec['service_product_name']})
                appointment_service_price_plans_by_product_id[rec['service_id']] = []
                appointment_service_price_plans_by_product_id[rec['service_id']].append(rec)
        print(appointment_services)
        print(appointment_service_price_plans_by_product_id)

        final_result = {
            'appointment_services':appointment_services,
            'appointment_service_price_plans':result,
            'appointment_service_price_plans_by_id':appointment_service_price_plans_by_id,
			'appointment_service_price_plans_by_product_id':appointment_service_price_plans_by_product_id,
		}
        return final_result

    # def _loader_params_product_product(self):
    #     result = super()._loader_params_product_product()
    #     result['search_params']['fields'].extend(["is_appointment_service"])
    #     return result
