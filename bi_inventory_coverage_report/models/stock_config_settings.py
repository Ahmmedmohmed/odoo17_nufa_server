# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockConfigurationSettings(models.TransientModel):
    _inherit = "res.config.settings"

    forcast_sales = fields.Boolean(string='Use Forcasted Sales For requisition')
    day_forcast = fields.Integer(string='Keep Stock in Days')
    past_sale = fields.Integer(string='Use Past Days')
    forcast_warehouse = fields.Boolean(string='Forcast Sales only For Warehouses')

    def get_values(self):
        res = super(StockConfigurationSettings, self).get_values()
        forcast_sales = self.env['ir.config_parameter'].sudo().get_param('bi_inventory_coverage_report.forcast_sales')
        day_forcast = int(self.env['ir.config_parameter'].sudo().get_param('bi_inventory_coverage_report.day_forcast'))
        forcast_warehouse = int(self.env['ir.config_parameter'].sudo().get_param('bi_inventory_coverage_report.forcast_warehouse'))
        past_sale = int(self.env['ir.config_parameter'].sudo().get_param('bi_inventory_coverage_report.past_sale'))
        res.update(
            forcast_sales = forcast_sales,
            day_forcast = day_forcast,
            forcast_warehouse = forcast_warehouse,
            past_sale = past_sale
        )
        return res

    def set_values(self):
        super(StockConfigurationSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('bi_inventory_coverage_report.forcast_sales', self.forcast_sales)
        self.env['ir.config_parameter'].sudo().set_param('bi_inventory_coverage_report.day_forcast', self.day_forcast)
        self.env['ir.config_parameter'].sudo().set_param('bi_inventory_coverage_report.forcast_warehouse', self.forcast_warehouse)
        self.env['ir.config_parameter'].sudo().set_param('bi_inventory_coverage_report.past_sale', self.past_sale)
