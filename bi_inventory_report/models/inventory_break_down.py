# -*- coding: utf-8 -*-

import base64
from io import StringIO
from odoo import api, fields, models,_
import io
import calendar
from itertools import groupby
import datetime
import math
from datetime import datetime
from datetime import date,timedelta
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from operator import itemgetter
try:
    import xlwt
except ImportError:
    xlwt = None

class ResCompany(models.Model):
    _inherit = "res.company"
    
    breakdown_days_ids = fields.One2many('breakdown.days', 'company_id', string='Breakdown Configuration')
    

class BreakdownDays(models.Model):
    _name = "breakdown.days"
    _description = "Breakdown Days"
    
    day_start = fields.Integer(string="Day start")
    day_end = fields.Integer(string="Day End")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.user.company_id)
    inventory_bd_id = fields.Many2one('inventory.breakdown', string="Inventory")

    def print_exl_report(self):
        return True



class InventoryBreakdownExcel(models.TransientModel):
    _name = "inventory.break.down.excel"
    _description = "Inventory Breakdown Excel"
    
    excel_file = fields.Binary('Report file ')
    file_name = fields.Char('Excel file', size=64)


class InventoryBreakdown(models.Model):
    _name = "inventory.breakdown"
    _description = "Inventory Breakdown"
    
    generate_type = fields.Selection([('warehouse','Warehouse'),('location','Location')],'Report Based On',default='warehouse')
    warehouse_ids = fields.Many2many('stock.warehouse', string='Warehouse')
    location_ids = fields.Many2many('stock.location', string= 'Locations')
    breakdown_days_ids = fields.One2many('breakdown.days','inventory_bd_id')

    
    def get_product_stock(self):
        if not self.breakdown_days_ids:
            raise ValidationError(_("Please enter valid Period Lines !"))
        ware_loc_list = []
        if self.location_ids:
            for loc in self.location_ids:
                for quant in loc.quant_ids.search([]):
                    ware_loc_list.append(quant.product_id.id)
        if self.warehouse_ids:
            for ware in self.warehouse_ids:
                for quant in ware.lot_stock_id.quant_ids.search([]):
                    ware_loc_list.append(quant.product_id.id)

        list_days = []
        if self.breakdown_days_ids:
            for days in self.breakdown_days_ids:
                start = days.day_start
                end = days.day_end
                st = datetime.now() - timedelta(days=start)
                en = datetime.now() - timedelta(days=end)
                product_obj = self.env['product.product'].search([('id','in',ware_loc_list),('write_date','>=',str(en)),('write_date','<=',str(st))])
                if product_obj:
                    list_days.append(product_obj)
            return list_days

    
    def get_ware_loc(self):
        if self.generate_type == 'warehouse':
            return self.warehouse_ids
        if self.generate_type == 'location':
            return self.location_ids


      
    def print_exl_report(self):
        filename = 'Inventory Breakdown Report.xls'
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
        worksheet.write_merge(0, 1, 0, 4, "Inventory Breakdown Report", style=style_title)
        worksheet.write(6, 0, 'Products', style_table_header)
        worksheet.write(6, 1, 'Qty', style_table_header)
        worksheet.write(6, 2, 'Qty(% of all Inventory)', style_table_header)
        worksheet.write(6, 3, 'Value ($)', style_table_header)
        worksheet.write(6, 4, 'Value(% of all Inventory)', style_table_header)
        
        if self.breakdown_days_ids:
            c= 0
            for days in self.breakdown_days_ids:
                c+=1
                if c == 1:
                    total_days = str(days.day_start) +" - " + str(days.day_end) + " Days Old"
                    worksheet.write_merge(5,5,0,4, total_days, style_table_header)
                if c == 2:
                    total_days = str(days.day_start) +" - " + str(days.day_end) + " Days Old"
                    worksheet.write_merge(5,5,5,9, total_days, style_table_header)
                if c == 3:
                    total_days = str(days.day_start) +" - " + str(days.day_end) + " Days Old"
                    worksheet.write_merge(5,5,10,14, total_days, style_table_header)
                if c == 4:
                    total_days = str(days.day_start) +" - " + str(days.day_end) + " Days Old"
                    worksheet.write_merge(5,5,15,19, total_days, style_table_header)
                if c > 4:
                        raise ValidationError(_('Please enter maximum four(4) period lines !'))

        if self.generate_type == 'warehouse':
            worksheet.write_merge(3,3,0,1, 'Warehouses ', style_table_header)
        else:
            worksheet.write_merge(3,3,0,1, 'Locations ', style_table_header)
        col = 2
        for wl in get_ware_loc:
            worksheet.write(3,col, wl.name)
            col+=1
        total_qty = 0
        total_value = 0.0
        if get_product_stock:
            rec_c = 0
            for quants in get_product_stock:
                rec_c+=1
                if rec_c == 1:
                    row = 7
                    col = 0
                    for pro_id in quants:
                        if pro_id.qty_available:
                            total_qty += pro_id.qty_available

                        if pro_id.value_svl:
                            total_value += pro_id.value_svl
                    for quant in quants:
                        worksheet.write(row, col, quant.display_name, style)
                        worksheet.write(row, col+1, quant.qty_available, style)
                        if quant.qty_available:
                            #total_qty += quant.qty_available
                            qty_per_inv = ((quant.qty_available * 100)/total_qty)
                            worksheet.write(row, col+2, str("{:.2f}".format(qty_per_inv)), style)
                        
                        worksheet.write(row, col+3, quant.value_svl, style)
                        if quant.value_svl:
                            #total_value += quant.value_svl
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                            worksheet.write(row, col+4, value_per_inv, style)
                        row += 1
                if rec_c == 2:
                    row = 7
                    worksheet.write(6, 5, 'Products', style_table_header)
                    worksheet.write(6, 6, 'Qty', style_table_header)
                    worksheet.write(6, 7, 'Qty(% of all Inventory)', style_table_header)
                    worksheet.write(6, 8, 'Value ($)', style_table_header)
                    worksheet.write(6, 9, 'Value(% of all Inventory)', style_table_header)
                    for quant in quants:
                        worksheet.write(row, 5, quant.name, style)
                        worksheet.write(row, 6, quant.qty_available, style)
                        if quant.qty_available:
                            total_qty += quant.qty_available
                            qty_per_inv = ((quant.qty_available * 100)/total_qty)
                            worksheet.write(row, 7, str("{:.2f}".format(qty_per_inv)), style)
                        worksheet.write(row, 8, quant.value_svl, style)
                        if quant.value_svl:
                            total_value += quant.value_svl
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                            worksheet.write(row, 9, value_per_inv, style)
                        row += 1
                if rec_c == 3:
                    row = 7
                    worksheet.write(6, 10, 'Products', style_table_header)
                    worksheet.write(6, 11, 'Qty', style_table_header)
                    worksheet.write(6, 12, 'Qty(% of all Inventory)', style_table_header)
                    worksheet.write(6, 13, 'Value ($)', style_table_header)
                    worksheet.write(6, 14, 'Value(% of all Inventory)', style_table_header)
                    for quant in quants:
                        if quant.value_svl:
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                        worksheet.write(row, 10, quant.name, style)
                        worksheet.write(row, 11, quant.qty_available, style)
                        if quant.qty_available:
                            total_qty += quant.qty_available
                            qty_per_inv = ((quant.qty_available * 100)/total_qty)
                            worksheet.write(row, 7, str("{:.2f}".format(qty_per_inv)), style)
                        worksheet.write(row, 13, quant.value_svl, style)
                        if quant.value_svl:
                            total_value += quant.value_svl
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                            worksheet.write(row, 9, value_per_inv, style)
                        row += 1
                if rec_c == 4:
                    row = 7
                    worksheet.write(6, 15, 'Products', style_table_header)
                    worksheet.write(6, 16, 'Qty', style_table_header)
                    worksheet.write(6, 17, 'Qty(% of all Inventory)', style_table_header)
                    worksheet.write(6, 18, 'Value ($)', style_table_header)
                    worksheet.write(6, 19, 'Value(% of all Inventory)', style_table_header)
                    for quant in quants:
                        total_qty += quant.qty_available
                        qty_per_inv = ((quant.qty_available * 100)/total_qty)
                        total_value += quant.value_svl
                        if quant.value_svl:
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                        worksheet.write(row, 15, quant.name, style)
                        worksheet.write(row, 16, quant.qty_available, style)
                        if quant.qty_available:
                            total_qty += quant.qty_available
                            qty_per_inv = ((quant.qty_available * 100)/total_qty)
                            worksheet.write(row, 7, str("{:.2f}".format(qty_per_inv)), style)
                        worksheet.write(row, 18, quant.value_svl, style)
                        if quant.value_svl:
                            total_value += quant.value_svl
                            value_per_inv = ((quant.value_svl * 100)/total_value)
                            worksheet.write(row, 9, value_per_inv, style)
                        row += 1
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['inventory.age.report.excel'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        res = {
                        'view_mode': 'form',
                        'res_id': export_id.id,
                        'name': 'Inventory Breakdown Report',
                        'res_model': 'inventory.age.report.excel',
                        'view_type': 'form',
                        'type': 'ir.actions.act_window',
                        'target':'new'
                }
        return res
