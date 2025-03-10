# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
import logging
_logger = logging.getLogger(__name__)

import io
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta 


try:
    import xlwt
except ImportError:
    _logger.debug('Cannot `import xlwt`.')

try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')

class stock_data(models.Model):
    _name = 'stock.rotation.data'
    _description = 'stock rotation data'

class StockRotationReport(models.TransientModel):
    _name = 'stock.rotation.report'
    _description = 'stock rotation report'

    date_from = fields.Datetime(string='From Date', required=True, default=datetime.now() - relativedelta(days=30))
    date_to = fields.Datetime(string='To Date', required=True, default=datetime.now() + relativedelta(days=1))
    is_all_warehouse = fields.Boolean(string='Include All Warehouse?')
    warehouse_ids = fields.Many2many('stock.warehouse',string='Warehouses')


    def generate_xls_report(self):
        sale = []
        purchase = []
        ware_list = []
        move_line = {}
        products = {}
        products_pur = {}
        if self.is_all_warehouse:
            for ware in self.env['stock.warehouse'].search([]):
                ware_list.append(ware.lot_stock_id.id)
                move_obj = self.env['stock.move'].search([])
            for move in move_obj:
                if self.date_from <= move.date and self.date_to >= move.date:
                    if move.picking_type_id.code == 'incoming':
                        purchase.append(move.id)
                        move_line.update({'incoming':purchase})
                        for move_l in move_line['incoming']:
                            if self.env['stock.move'].browse(move_l).product_id.id in products_pur:
                                temp =  products_pur[self.env['stock.move'].browse(move_l).product_id.id]
                                temp.append(move_l)
                                products_pur[self.env['stock.move'].browse(move_l).product_id.id] = temp
                            else:
                                products_pur.setdefault(self.env['stock.move'].browse(move_l).product_id.id, []).append(move_l)
                        for k,v in products_pur.items():
                            products_pur.update({k:list(set(v))})
                    if move.picking_type_id.code == 'outgoing':
                        sale.append(move.id)
                        move_line.update({'outgoing':sale})
                        for move_l in move_line['outgoing']:
                            if self.env['stock.move'].browse(move_l).product_id.id in products:
                                temp =  products[self.env['stock.move'].browse(move_l).product_id.id]
                                temp.append(move_l)
                                products[self.env['stock.move'].browse(move_l).product_id.id] = temp
                            else:
                                products.setdefault(self.env['stock.move'].browse(move_l).product_id.id, []).append(move_l)
                        for k,v in products.items():
                            products.update({k:list(set(v))})
        
        if self.warehouse_ids:
            for ware in self.warehouse_ids:
                ware_list.append(ware.lot_stock_id.id)
                move_obj = self.env['stock.move'].search(["|",('location_id','in',ware_list),('location_dest_id','in',ware_list)])
            for move in move_obj:
                if self.date_from <= move.date and self.date_to >= move.date:
                    if move.picking_type_id.code == 'outgoing':
                        sale.append(move.id)
                        move_line.update({'outgoing':sale})
                        for move_l in move_line['outgoing']:
                            if self.env['stock.move'].browse(move_l).product_id.id in products:
                                temp =  products[self.env['stock.move'].browse(move_l).product_id.id]
                                temp.append(move_l)
                                products[self.env['stock.move'].browse(move_l).product_id.id] = temp
                            else:
                                products.setdefault(self.env['stock.move'].browse(move_l).product_id.id, []).append(move_l)
                        for k,v in products.items():
                            products.update({k:list(set(v))})
                    if move.picking_type_id.code == 'incoming':
                        purchase.append(move.id)
                        move_line.update({'incoming':purchase})
                        for move_l in move_line['incoming']:
                            if self.env['stock.move'].browse(move_l).product_id.id in products_pur:
                                temp =  products_pur[self.env['stock.move'].browse(move_l).product_id.id]
                                temp.append(move_l)
                                products_pur[self.env['stock.move'].browse(move_l).product_id.id] = temp
                            else:
                                products_pur.setdefault(self.env['stock.move'].browse(move_l).product_id.id, []).append(move_l)
                        for k,v in products_pur.items():
                            products_pur.update({k:list(set(v))})
        
        filename = 'Stock Rotation Report.xls'
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
        worksheet.write_merge(0, 1, 0, 12, "Stock Rotation Report", style=style_title)
        worksheet.write_merge(2, 3, 0, 0, "From Date",style_table_header)
        worksheet.write_merge(2, 3, 2, 2, "To Date",style_table_header)
        worksheet.write(4, 0, self.date_from.strftime('%d-%m-%Y'))
        worksheet.write(4, 2, self.date_to.strftime('%d-%m-%Y'))
        worksheet.write_merge(2, 3, 1, 1,  style=style_table_header)
        worksheet.write(6, 0, 'Id', style_table_header)
        worksheet.write(6, 1, 'Reference', style_table_header)
        worksheet.write(6, 2, 'Products', style_table_header)
        worksheet.write(6, 3, 'Cost', style_table_header)
        worksheet.write(6, 4, 'Sales Price', style_table_header)
        worksheet.write(6, 5, 'Opening Stock', style_table_header)
        worksheet.write(6, 6, 'Sales in Period', style_table_header)
        worksheet.write(6, 7, 'Warehouse Transfer(OUT)', style_table_header)
        worksheet.write(6, 8, 'Last sale', style_table_header)
        worksheet.write(6, 9, 'Purchase in Period', style_table_header)
        worksheet.write(6, 10, 'Warehouse Transfer(IN)', style_table_header)
        worksheet.write(6, 11, 'Last purchase', style_table_header)
        worksheet.write(6, 12, 'Closing Stock', style_table_header)
        prod_row = 7
        prod_col = 0    
        count = 1
        if products:
            len_k = 0
            opening_stock = 0
            last_sale = ""

            for k in products:
                get_list = products[k]
                ware_tranf_out = len(get_list)

                for move_id in get_list:
                    ware_tranf_out = len(get_list)
                    browse_move_id = self.env['stock.move'].browse(move_id)
                    product_id=self.env['product.product'].search([('id','=',browse_move_id.product_id.id)])
                    opening_stock += product_id.qty_available
                    if browse_move_id.sale_line_id.order_id.date_order:
                        if self.date_to >= browse_move_id.sale_line_id.order_id.date_order:
                            last_sale = browse_move_id.sale_line_id.order_id.date_order.strftime('%d-%m-%Y')
                
                len_k+=1
                
                product_id=self.env['product.product'].browse(k)
                worksheet.write(prod_row, prod_col, count, style)
                worksheet.write(prod_row, prod_col+1, product_id.default_code, style)
                worksheet.write(prod_row, prod_col+2, product_id.name, style)
                worksheet.write(prod_row, prod_col+3, product_id.standard_price, style)
                worksheet.write(prod_row, prod_col+4, product_id.lst_price, style)
                worksheet.write(prod_row, prod_col+5, opening_stock, style)
                worksheet.write(prod_row, prod_col+6,product_id.sales_count, style)
                worksheet.write(prod_row, prod_col+7, ware_tranf_out, style)
                if last_sale:
                    worksheet.write(prod_row, prod_col+8, parser.parse(last_sale).strftime('%d-%m-%Y'), style)
                worksheet.write(prod_row, prod_col+9, 0, style)
                worksheet.write(prod_row, prod_col+10, 0, style)
                worksheet.write(prod_row, prod_col+12, 0, style)
                prod_row = prod_row + 1
                count = count+1
                opening_stock = 0

        if products_pur:
            len_k = 0
            last_sale = ""
            closing_stock = 0
            for k in products_pur:
                get_list = products_pur[k]
                ware_tranf_in = len(get_list)

                for move_id in get_list:
                    ware_tranf_in = len(get_list)
                    browse_move_id = self.env['stock.move'].browse(move_id)
                    product_id=self.env['product.product'].search([('id','=',browse_move_id.product_id.id)])
                    get_cl = ((product_id.qty_available + product_id.purchased_product_qty)-product_id.sales_count)
                    closing_stock += get_cl
                    if browse_move_id.purchase_line_id.order_id.date_order:
                        if self.date_to >= browse_move_id.purchase_line_id.order_id.date_order:
                            last_sale = browse_move_id.purchase_line_id.order_id.date_order.strftime('%d-%m-%Y')
                len_k+=1
                
                product_id=self.env['product.product'].browse(k)

                worksheet.write(prod_row, prod_col, count, style)
                worksheet.write(prod_row, prod_col+1, product_id.default_code, style)
                worksheet.write(prod_row, prod_col+2, product_id.name, style)
                worksheet.write(prod_row, prod_col+3, product_id.standard_price, style)
                worksheet.write(prod_row, prod_col+4, product_id.lst_price, style)
                worksheet.write(prod_row, prod_col+5, 0, style)
                worksheet.write(prod_row, prod_col+6, 0, style)
                worksheet.write(prod_row, prod_col+7, 0, style)
                worksheet.write(prod_row, prod_col+9,product_id.purchased_product_qty, style)
                worksheet.write(prod_row, prod_col+10, ware_tranf_in, style)
                if last_sale:
                    worksheet.write(prod_row, prod_col+11, parser.parse(last_sale).strftime('%d-%m-%Y'), style)
                worksheet.write(prod_row, prod_col+12, closing_stock, style)
                closing_stock = 0
                
                prod_row = prod_row + 1
                count = count+1
        fp = io.BytesIO()
        workbook.save(fp)
        export_id = self.env['stock.excel.report'].create({'excel_file': base64.b64encode(fp.getvalue()), 'file_name': filename})
        res = {'view_mode': 'form',
               'res_id': export_id.id,
               'name': 'Stock Rotation Report',
               'res_model': 'stock.excel.report',
               'view_type': 'form',
               'type': 'ir.actions.act_window',
               'target':'new'
                }
        return res

class stock_excel_report(models.TransientModel):
    _name = "stock.excel.report"
    _description= 'stock excel report'

    excel_file = fields.Binary('Download Excel Report', readonly =True)
    file_name = fields.Char('File', readonly=True)