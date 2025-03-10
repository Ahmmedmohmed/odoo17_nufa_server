# -*- coding: utf-8 -*-
# from odoo import http


# class AnalyticAccountFilter(http.Controller):
#     @http.route('/analytic_account_filter/analytic_account_filter', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/analytic_account_filter/analytic_account_filter/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('analytic_account_filter.listing', {
#             'root': '/analytic_account_filter/analytic_account_filter',
#             'objects': http.request.env['analytic_account_filter.analytic_account_filter'].search([]),
#         })

#     @http.route('/analytic_account_filter/analytic_account_filter/objects/<model("analytic_account_filter.analytic_account_filter"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('analytic_account_filter.object', {
#             'object': obj
#         })

