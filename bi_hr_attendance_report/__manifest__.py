# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name":"Hr Employee Attendance Report",
    "version":"17.0.0.1",
    "category":"Employee",
    "summary":"print hr employee attendance xls report employee attendance excel report print attendance xls report employee attendance pdf report download employee department wise attendance report hr employee report hr attendance report print attendance report ",
    "description":"""The Employee Attendance Report Odoo app allows businesses to streamline attendance tracking, generate detailed reports, and ensure effective workforce management. Human resource manager can easily generate detailed attendance report based on employee or department and also can select specific employee or department reports in XLS or PDF format.""",
    "license": "OPL-1",
    "author" : "BrowseInfo",
    "website": "https://www.browseinfo.com",
    "depends":["base",
               "hr_attendance",
               "hr",
	          ],
    "data":[
            "security/ir.model.access.csv",
            "report/employee_attendence_report_wizard_form.xml",
            "report/employee_attendence_report_wizard_view.xml",
            "wizard/employee_attendence_report_wizard_view.xml",
            "wizard/excel_report.xml",
            "views/hr_employee_view.xml",
	       ],
    "auto_install": False,
    "application": True,      
    "installable": True,
    "images":['static/description/Employee-Attendance-Report.gif'],
    'live_test_url':'https://youtu.be/f401klMIp-U',
    'external_dependencies': {'python': ['xlwt',]},
}
