# -*- coding: utf-8 -*-

import base64
from io import StringIO
from odoo import api, fields, models,_
import io
from itertools import groupby
import datetime
from datetime import date,timedelta
from dateutil import parser
import time
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from operator import itemgetter
try:
    import xlwt
except ImportError:
    xlwt = None

class InventorycoverReport(models.Model):
    _name = "inventory.coverage.wizard"
    _description = "Inventory Coverage Wizard"
    
    
    @api.depends('analysis_days')
    def get_past_date(self):
        self.report_date = (date.today() + timedelta(days=self.analysis_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        
    analysis_days = fields.Integer(string='Analysis in Days', required=True)
    report_date = fields.Date("To Date",compute=get_past_date)
    product_type = fields.Selection([('all','All'),('out','Out of Stock Products'),('in','Available Products')],'Filter Products',default='all')
    warehouse = fields.Many2many('stock.warehouse', string='Warehouse', required=True)
    product_ids = fields.Many2many('product.product', string='Products')

    
    def get_months(self):
        current_date = date.today()
        final_dict = {}
        curr_date = parser.parse(str(current_date))
        for i in range(self.analysis_days):
            date_delta = curr_date + timedelta(i)
            final_dict.setdefault(date_delta.strftime("%B-%Y"), []).append(date_delta.strftime('%d'))
        return final_dict

    
    @api.constrains('product_ids', 'analysis_days')
    def validate_product_days(self):
        if not self.product_ids or self.analysis_days <= 0 : 
            raise ValidationError(_('Please enter valid Analysis Days and Products !'))

    
    def get_product_stock(self):
        current_date = date.today()
        product_list = []
        ware_product_list = []
        for ware in self.warehouse:
            for quant in ware.lot_stock_id.quant_ids.search([]):
                ware_product_list.append(quant.product_id.id)

        for product in self.product_ids:
            product_list.append(product.id)
        conv_date_str = str(current_date.strftime("%Y-%m-%d %H:%M:%S"))
        if self.product_type == "all":
            obj = self.env['stock.quant'].search([('product_id','in',ware_product_list),('product_id','in',product_list),('in_date','<=',self.report_date),('location_id.usage','=','internal')])
            return obj
        if self.product_type == "out":
            obj = self.env['stock.quant'].search([('product_id','in',ware_product_list),('product_id','in',product_list),('in_date','<=',self.report_date),('location_id.usage','=','internal'),('quantity','<=',  0)])
            return obj
        if self.product_type == "in":
            obj = self.env['stock.quant'].search([('product_id','in',ware_product_list),('product_id','in',product_list),('in_date','>=',conv_date_str),('in_date','<',self.report_date),('location_id.usage','=','internal'),('quantity','>',  0)])
            return obj

    
    def get_report(self):
        prd_list = []
        ware_list = []
        for prd in self.product_ids:
            prd_list.append(prd.id)
        for ware in self.warehouse:
            ware_list.append(ware.id)
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': {
                'analysis_days': self.analysis_days,
                'report_date': self.report_date,
                'product_type': self.product_type,
                'product_ids': prd_list,
                'warehouse':ware_list,
            },
        }
        return self.env.ref('bi_inventory_coverage_report.inventory_report').report_action(self, data=data)

      
    def print_exl_report(self):
        filename = 'Inventory Coverage Report.xls'
        get_months = self.get_months()
        get_product_stock = self.get_product_stock()
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
        worksheet.write_merge(0, 1, 0, 17, "Inventory Coverage Report", style=style_title)
        worksheet.write(3, 1, 'Start Date:', style_table_header)
        worksheet.write(4, 1, current_date)
        worksheet.write(3, 3, 'End Date', style_table_header)
        worksheet.write(4, 3, self.report_date.strftime('%Y-%m-%d'))
        worksheet.write(6, 0, 'Id', style_table_header)
        worksheet.write(6, 1, 'Products', style_table_header)
        worksheet.write(6, 2, 'Opening Stock', style_table_header)
        col = 3
        for month in get_months:
            worksheet.write(5, col, month)
            for date in get_months[month]:
                worksheet.write(6, col, date )
                col+=1
        row = 7
        col = 0
        count = 1
        if get_product_stock:
            for product in get_product_stock:
                worksheet.write(row, col, count, style)
                worksheet.write(row, col+1, product.product_id.name, style)
                worksheet.write(row, col+2, product.quantity, style)
                row += 1
                count += 1
        fp = io.BytesIO()
        workbook.save(fp)

        export_id = self.env['cover.report.excel'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        res = {
                        'view_mode': 'form',
                        'res_id': export_id.id,
                        'name':'Invntory Coverage Report',
                        'res_model': 'cover.report.excel',
                        'view_type': 'form',
                        'type': 'ir.actions.act_window',
                        'target':'new'
                }
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: