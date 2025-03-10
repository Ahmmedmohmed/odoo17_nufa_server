# -*- coding: utf-8 -*-
{
    'name': "Warehouse Stock Rotation Report Odoo",
    'version' : "17.0.0.0",
    'summary': 'product stock Rotation report Opening stock report closing stock report inventory movement report inventory stock transfer reports overstock report stock coverage report inventory Coverage report stock report periodically stock report stock expiry report',
    'description': """
        Generate Excel Report for All Warehouses Stock and Particular Warehouses Stock Between Specific Dates.
    odoo warehouse stock transfer report warehouse transfer stock report Odoo stock transfer report
    odoo stock transfer inventory reports stock inventory transfer reports Odoo inventory transfer reports
    odoo inventory stock transfer reports warehouse stock rotation reports
    odoo warehouse stock transfer reports warehouse inventory stock rotation reports
    Odoo inventory stock input reports inventory stock outpur reports
    Odoo stock opening reports closing stock reports
    Odoo opening stock reports stock details reports stock movement reports
       Odoo Inventory Turnover report Stock turnover reports Stock inventory turnover reports
       Odoo Stock Rotation Analysis Stock Analysis report Inventory Stock Rotation stock Inventory Turnover
       odoo stock reports inventory reports Odoo real time stock reports 
       
        Odoo inventory movement report moveble stock reports
        Odoo Report for stock rotation report for stock transfer report for stock movement stock in/out reports stock in-out reports
        odoo stock last price report stock pricing reports stock price movement reports price change stock report
        Odoo stock price change reports stock period reports Odoo periodically stock reports print inventory reports
    download inventory reports print stock reports download stock reports

    odoo Out of stock product report Overstock product report stock forecast report odoo
    odoo out of stock report stock Coverage report Coverage stock report odoo
    odoo overstock report stock coverage report odoo inventory Coverage report
    odoo current inventory report current stock report inventory forcaste report forecast inventory report print
    odoo Product Out Of Stock Report Report Inventory Coverage Report app advance purchasing management
    Odoo report forecasted sales or past sale report periodical product stock report odoo
    Odoo Warehouse stock Coverage report print inventory reports download inventory reports odoo
    odoo print stock reports download stock reports Odoo Stock Inventory Report odoo
    Odoo stock transfer report transfer stock report odoo
    odoo stock transfer inventory reports stock inventory transfer reports odoo
    Odoo inventory stock transfer reports warehouse stock rotation reports odoo
    Odoo warehouse stock transfer reports warehouse inventory stock rotation reports odoo
    Odoo inventory stock input reports inventory stock output reports odoo
    Odoo stock opening reports closing stock reports odoo
    Odoo opening stock reports stock details reports odoo
    Odoo warehouse stock movement reports inventory movement reports
    odoo warehouse moveble stock reports Report for stock rotation report for stock transfer report for stock movement
    odoo stock in/out reports stock in-out reports
    Odoo stock last price report stock pricing reports
    odoo stock price movement reports price change stock report
    odoo stock price change reports stock period reports
    Odoo periodically stock reports Expiry stock report Expiry product report
    Odoo Expiry product stock report product stock Expiry report
    odoo stock product report stock product report expiry
    odoo stock product report expired for product report expired for stock
    odoo stock product report expiry for product report expiry for stock
    odoo stock Expiry Report for product Expiry Report for stock product Expiry Report for warehouse Expiry Report for location
    odoo stock expired Report for product expired Report for stock product expired Report for warehouse expired Report for location

    odoo stock expired report product expired report product stock expired report


    odoo print Out of stock product report print Overstock product report print stock forecast report print
    odoo print out of stock report print stock Coverage report Coverage stock report print
    odoo print overstock report print stock coverage report odoo print inventory Coverage report
    odoo print current inventory report print current stock report inventory print forecast report print forecast inventory report print
    odoo print Product Out Of Stock Report print Report Inventory Coverage Report app print advance purchasing management
    Odoo print report forecasted sales or print past sale report periodical product stock report print
    Odoo print Warehouse stock Coverage report print inventory reports print inventory reports print
    odoo print stock reports print stock reports Odoo Stock Inventory Report print
    Odoo print stock transfer report print transfer stock report print
    odoo print stock transfer inventory reports print stock inventory transfer reports print
    Odoo print inventory stock transfer reports print warehouse stock rotation reports print
    Odoo print warehouse stock transfer reports print warehouse inventory stock rotation reports print
    Odoo print inventory stock input reports print inventory stock output reports print
    Odoo print stock opening reports print closing stock reports print
    Odoo print opening stock reports print stock details reports print
    Odoo print warehouse stock movement reports print inventory movement reports print
    odoo print warehouse moveble stock reports Report for print stock rotation report print stock transfer report for stock movement
    odoo print stock in/out reports stock in-out reports print
    Odoo print stock last price report stock pricing reports print
    odoo print stock price movement reports price change stock report print
    odoo print stock price change reports stock period reports print
    Odoo print periodically stock reports print Expiry stock report Expiry product report print
    Odoo print Expiry product stock report product stock Expiry report print
    odoo printstock product report stock product report expiry print
    odoo print stock product report expired print product report expired print stock print
    odoo print stock product report expiry print product report expiry print stock print
    odoo print stock Expiry Report print product Expiry Report print stock product Expiry Report print warehouse Expiry Report for location
    odoo print stock expired Report for print product expired Report print stock product expired Report print warehouse expired Report for location

    odoo print stock expired report print product expired report product stock expired report print
    """,
    'author': "BrowseInfo",
    'website': "https://www.browseinfo.com",
    'category': 'Warehouse',
    'depends': ['base','stock', 'purchase', 'sale_stock','sale_management'],
    'price': 49,
    'currency': "EUR",
    'data': [
		'security/ir.model.access.csv',
        'views/stock_rotation_wizard_view.xml',
    ],
    'qweb':[
    ],
    "auto_install": False,
    "installable": True,
    'live_test_url':'https://youtu.be/VhE6Yg2Qq9o',
	"images":['static/description/Banner.gif'],
    'license': 'OPL-1' ,
}
