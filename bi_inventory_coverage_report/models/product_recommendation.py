# -*- coding: utf-8 -*-

import base64
from io import StringIO
from odoo import api, fields, models,_
import io
import calendar
from itertools import groupby
from datetime import date,timedelta
import time
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from operator import itemgetter
try:
    import xlwt
except ImportError:
    xlwt = None
    
    
class ProductRecommendation(models.TransientModel):
    _name = "product.recommendation"
    _description = "Product Recommendation"
    
    @api.model
    def default_get_analysis_days(self):
        res_obj = self.env['res.config.settings']
        res_ids = res_obj.search([],limit=1)
        return res_ids.day_forcast

    @api.onchange('analysis_days')
    def days_change(self):
        if self.analysis_days:
            self.past_sale_date = (date.today() - timedelta(days=self.analysis_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)

    @api.model
    def default_get_past_date(self):
        res_obj = self.env['res.config.settings']
        res_ids = res_obj.search([],limit=1)
        diff = (date.today() - timedelta(days=res_ids.past_sale)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        return diff

    analysis_days = fields.Integer(string='Analysis in Days',default=default_get_analysis_days, required=True)
    partners = fields.Many2one('res.partner', string='Choose Vendor', required=True)
    past_sale_date = fields.Date("Past Sales Start From",default=default_get_past_date)
    warehouse = fields.Many2many('stock.warehouse', string='Warehouses')
    product_ids = fields.Many2many('product.product', string='Products')

    
    @api.constrains('product_ids')
    def validate_products(self):
        if not self.product_ids: 
            raise ValidationError(_("Please enter valid Products !"))
    
    
    def open_table(self):
        self.ensure_one()
        new_record = self.env['get.product.recommendation']
        product_list =[]
        for product in self.product_ids:
            product_list.append(product.id)
        order_line_obj = self.env['sale.order.line'].search([('product_id','in',product_list),('order_partner_id','=',self.partners.id),('order_id.date_order','>=',self.past_sale_date),('order_id.date_order','<=',str(date.today()))])
        for line in order_line_obj:
            new_record.create({
                'product_id': line.product_id.id,
                'warehouse_id': line.product_id.warehouse_id.id,
                'supplier_id':line.order_partner_id.id,
            })

        ware_part_list =[]
        for ware in self.warehouse.search([('partner_id','=',self.partners.id)]):
            ware_part_list.append(ware.partner_id.id)
        order_line_obj = self.env['sale.order.line'].search([('order_partner_id','in',ware_part_list),('order_id.date_order','>=',self.past_sale_date),('order_id.date_order','<=',str(date.today()))])
        for line in order_line_obj:
            new_record.create({
                'product_id': line.product_id.id,
                'warehouse_id': line.product_id.warehouse_id.id,
                'supplier_id':line.order_partner_id.id,
            })

        tree_view_id = self.env.ref('bi_inventory_coverage_report.view_tree_get_product_recommendation').id
        form_view_id = self.env.ref('bi_inventory_coverage_report.view_get_product_recommendation').id
        action = {
            'type': 'ir.actions.act_window',
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'view_mode': 'tree,form',
            'name': _('Products'),
            'res_model': 'get.product.recommendation',
            'context': dict(self.env.context),
            'res_id': new_record.id,
        }
        return action

      
    def print_exl_report(self):
        filename = 'Product Recommendation Report.xls'
        workbook = xlwt.Workbook()
        stylePC = xlwt.XFStyle()
        alignment = xlwt.Alignment()
        alignment.horz = xlwt.Alignment.HORZ_CENTER
        fontP = xlwt.Font()
        fontP.bold = True
        fontP.height = 200
        stylePC.font = fontP
        stylePC.num_format_str = '@'
        stylePC.alignment = alignment
        style_title = xlwt.easyxf("font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center;pattern: pattern solid, fore_colour aqua;")
        style_table_header = xlwt.easyxf("font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center")
        style = xlwt.easyxf("font:height 200; font: name Liberation Sans,color black;")
        worksheet = workbook.add_sheet('Sheet 1')
        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        worksheet.write_merge(0, 1, 0, 5, "Product Recommendation Report", style=style_title)
        worksheet.write(3, 1, 'Days', style_table_header)
        worksheet.write(3,2, str(self.analysis_days))
        worksheet.write(3,4, 'Vendor', style_table_header)
        worksheet.write(3,5,self.partners.name)
        worksheet.write(5, 1, 'Start Date', style_table_header)
        worksheet.write(5,2, current_date)
        worksheet.write(5, 4, 'End Date', style_table_header)
        worksheet.write(5,5, self.past_sale_date.strftime('%Y-%m-%d'))
        worksheet.write(7, 0, 'Id', style_table_header)
        worksheet.write(7, 1, 'Reference', style_table_header)
        worksheet.write(7, 2, 'Product', style_table_header)
        worksheet.write(7, 3, 'Warehouse', style_table_header)
        worksheet.write(7, 4, 'Current Stock', style_table_header)
        worksheet.write(7, 5, 'Sales Count', style_table_header)
        ware_list = []
        product_list = []
        for ware in self.warehouse:
            ware_list.append(ware.lot_stock_id.id)
        for product in self.product_ids:
            product_list.append(product.id)
        current_date = str(date.today())
        d=self.env['stock.quant'].search([])
        quant_obj = self.env['stock.quant'].search([('location_id','in',ware_list),('product_id','in',product_list),('in_date','>=',self.past_sale_date),('in_date','<=',current_date)])
        if quant_obj:
            row = 8
            col = 0
            count = 1
            for quant in quant_obj:
                worksheet.write(row, col, count, style)
                worksheet.write(row, col+1, quant.product_id.default_code, style)
                worksheet.write(row, col+2, quant.product_id.name, style)
                worksheet.write(row, col+3, quant.location_id.company_id.partner_id.name, style)
                worksheet.write(row, col+4, quant.quantity, style)
                worksheet.write(row, col+5, quant.product_id.sales_count, style)
                row += 1
                count += 1
        fp = io.BytesIO()
        workbook.save(fp)

        export_id = self.env['cover.report.excel'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        res = {
                        'view_mode': 'form',
                        'res_id': export_id.id,
                        'name':'Product Recommendation Report',
                        'res_model': 'cover.report.excel',
                        'view_type': 'form',
                        'type': 'ir.actions.act_window',
                        'target':'new'
                }
        return res


class CoverageReportExcel(models.TransientModel):
    _name = "cover.report.excel"
    _description = "Coverage Report Excel"
    
    excel_file = fields.Binary('Report file ')
    file_name = fields.Char('Excel file', size=64)


class GetProductRecommendation(models.Model):
    _name = "get.product.recommendation"
    _rec_name = "product_id"
    _description = "Product Recommendation"

    product_id = fields.Many2one('product.product', string='Product')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    supplier_id = fields.Many2one('res.partner', string='Supplier')
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: