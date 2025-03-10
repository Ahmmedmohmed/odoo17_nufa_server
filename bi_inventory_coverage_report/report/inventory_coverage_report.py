# -*- coding: utf-8 -*-

from odoo import api, models, _
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from datetime import date
from dateutil import parser


class ReportInventoryCoverage(models.AbstractModel):
    _name = 'report.bi_inventory_coverage_report.template_report'
    _description = "Report Inventory Coverage"

    @api.model
    def _get_report_values(self, docids, data=None):
        analysis_days = data['form']['analysis_days']
        report_date = data['form']['report_date'] 
        product_type = data['form']['product_type']
        product_list =  data['form']['product_ids']
        ware_list = data['form']['warehouse']
        docs = []
        curr_date = date.today()
        ware_prd_list = []
        
        for ware in ware_list:
            ware_brow_id = self.env['stock.warehouse'].browse(ware)
            for quant in ware_brow_id.lot_stock_id.quant_ids.search([]):
                ware_prd_list.append(quant.product_id.id)
        conv_date_str = str(curr_date.strftime("%Y-%m-%d %H:%M:%S"))
        if product_type == "all":
            quant_obj = self.env['stock.quant'].search([('product_id','in',ware_prd_list),('product_id','in',product_list),('in_date','<=',report_date),('location_id.usage','=','internal')])
        if product_type == "out":
            quant_obj = self.env['stock.quant'].search([('product_id','in',ware_prd_list),('product_id','in',product_list),('in_date','<=',report_date),('location_id.usage','=','internal'),('quantity','<=',  0)])
        if product_type == "in":
            quant_obj = self.env['stock.quant'].search([('product_id','in',ware_prd_list),('product_id','in',product_list),('in_date','>=',conv_date_str),('in_date','<=',report_date),('location_id.usage','=','internal'),('quantity','>',  0)])
        for quant in quant_obj:
            cl_st = ((quant.quantity + quant.product_id.purchased_product_qty)- quant.product_id.sales_count)
            docs.append({
                'product': quant.product_id.name,
                'quantity': quant.quantity,
                'from_date': curr_date,
                'end_date': parser.parse(report_date).strftime("%Y-%m-%d"),
                'opening_stock':quant.quantity,
                'sale':quant.product_id.sales_count,
                'purchase':quant.product_id.purchased_product_qty,
                'forecasted_sale': quant.product_id.virtual_available,
                'closing_stock':cl_st
            })
        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'analysis_days': analysis_days,
            'report_date': report_date,
            'from_date':date.today(),
            'docs': docs,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
