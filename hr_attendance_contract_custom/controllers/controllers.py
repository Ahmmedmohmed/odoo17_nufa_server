# -*- coding: utf-8 -*-
# from odoo import http


# class BsHrAttendance(http.Controller):
#     @http.route('/bs_hr_attendance/bs_hr_attendance', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/bs_hr_attendance/bs_hr_attendance/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('bs_hr_attendance.listing', {
#             'root': '/bs_hr_attendance/bs_hr_attendance',
#             'objects': http.request.env['bs_hr_attendance.bs_hr_attendance'].search([]),
#         })

#     @http.route('/bs_hr_attendance/bs_hr_attendance/objects/<model("bs_hr_attendance.bs_hr_attendance"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('bs_hr_attendance.object', {
#             'object': obj
#         })

