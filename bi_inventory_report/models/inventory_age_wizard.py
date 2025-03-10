# -*- coding: utf-8 -*-

import base64
from io import StringIO
from odoo import api, fields, models,_
import io
from itertools import groupby
import time
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from operator import itemgetter
try:
    import xlwt
except ImportError:
    xlwt = None
    
class InventoryAgeReport(models.Model):
    _name = "inventory.age.wizard"
    _description = "Inventory Age Report"
    
    generate_type = fields.Selection([('warehouse','Warehouse'),('location','Location')],'Report Based On',default='warehouse')
    warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouse')
    location_ids = fields.Many2many('stock.location',string= 'Location')
    include_all_product = fields.Boolean("Include All Products")
    product_ids = fields.Many2many('product.product', string='Products')

    
    @api.constrains('product_ids')
    def validate_days(self):
        if not self.include_all_product and not self.product_ids: 
            raise ValidationError(("Please enter valid Products !"))
    
    
    def get_product_stock(self):
        ware_loc_list = []
        product_list = []
        obj = self.env['product.product']
        if self.location_ids:
            for loc in self.location_ids:
                for quant in loc.quant_ids.search([]):
                    ware_loc_list.append(quant.product_id.id)
        if self.warehouse_ids:
            for ware in self.warehouse_ids:
                for quant in ware.lot_stock_id.quant_ids.search([]):
                    ware_loc_list.append(quant.product_id.id)
        if self.product_ids:
            for prd in self.product_ids:
                product_list.append(prd.id)
            product_obj = self.product_ids.search([('id','in',ware_loc_list),('id','in',product_list)])
            obj = product_obj
            return obj
        if self.include_all_product:
            product_obj = self.env['product.product'].search([('id','in',ware_loc_list)])
            obj = product_obj
            return obj
    
    def get_ware_loc(self):
        if self.generate_type == 'warehouse':
            return self.warehouse_ids
        else:
            return self.location_ids

      
    def print_exl_report(self):
        filename = 'Inventory Age Report.xls'
        get_product_stock = self.get_product_stock()
        get_ware_loc = self.get_ware_loc()
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
        worksheet.write_merge(0, 1, 0, 11, "Inventory Age Report", style=style_title)
        worksheet.write(6, 0, 'Id', style_table_header)
        worksheet.write(6, 1, 'Reference', style_table_header)
        worksheet.write(6, 2, 'Product Name', style_table_header)
        worksheet.write(6, 3, 'Total Qty', style_table_header)
        worksheet.write(6, 4, 'Qty(% of Overall Inventory)', style_table_header)
        worksheet.write(6, 5, 'Oldest Qty', style_table_header)
        worksheet.write(6, 6, 'Value ($)', style_table_header)
        worksheet.write(6, 7, 'Value(% of Overall Inventory)', style_table_header)
        worksheet.write(6, 8, 'Average Cost', style_table_header)
        worksheet.write(6, 9, 'Average Sale Price', style_table_header)
        worksheet.write(6, 10, 'Current Sale Price', style_table_header)
        worksheet.write(6, 11, 'Current Cost', style_table_header)
        if self.generate_type == 'warehouse':
            worksheet.write_merge(3,3,0,1, 'Warehouses ', style_table_header)
        else:
            worksheet.write_merge(3,3,0,1,'Locations ', style_table_header)
        col = 2
        for wl in get_ware_loc:
            worksheet.write(3, col, wl.name)
            col+=1
        row = 7
        col = 0
        count = 1
        if get_product_stock:
            total_qty = 0
            total_value = avg_cost = total_price = total_cost = avg_cost = avg_price = 0.0
            for product in get_product_stock:
                total_qty += product.qty_available
                if product.qty_available and total_qty:
                    qty_per_inv = ((product.qty_available * 100)/total_qty)
                    worksheet.write(row, col+4, qty_per_inv, style)
                total_value += product.value_svl
                if product.value_svl and total_value:
                    value_per_inv = ((product.value_svl * 100)/total_value)
                    worksheet.write(row, col+7, value_per_inv, style)
                total_cost += product.product_tmpl_id.standard_price
                total_price += product.product_tmpl_id.list_price
                if total_price: 
                    avg_price = (len(get_product_stock)/total_price)
                    worksheet.write(row, col+9, avg_price, style)
                if total_cost:
                    avg_cost = (len(get_product_stock)/total_cost)
                    worksheet.write(row, col+8, avg_cost, style)
                worksheet.write(row, col, count, style)
                worksheet.write(row, col+1, product.default_code, style)
                worksheet.write(row, col+2, product.name, style)
                worksheet.write(row, col+3, product.qty_available, style)
                worksheet.write(row, col+5, product.qty_available, style)
                worksheet.write(row, col+6, product.value_svl, style)
                
                
                
                worksheet.write(row, col+10, product.product_tmpl_id.list_price, style)
                worksheet.write(row, col+11, product.product_tmpl_id.standard_price, style)
                row += 1
                count += 1
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['inventory.age.report.excel'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        res = {
                        'view_mode': 'form',
                        'res_id': export_id.id,
                        'name': 'Inventory Age Report',
                        'res_model': 'inventory.age.report.excel',
                        'view_type': 'form',
                        'type': 'ir.actions.act_window',
                        'target':'new'
                }
        return res

class InventoryAgeExcel(models.TransientModel):
    _name = "inventory.age.report.excel"
    _description = "Inventory Age Excel"
    
    excel_file = fields.Binary('Report file ')
    file_name = fields.Char('Excel file', size=64)
