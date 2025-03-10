# -*- coding: utf-8 -*-

import time
from odoo import api, models

class ReportHrLoan(models.AbstractModel):
    _name = 'report.hr_loan.report_loanprint'

    @api.model
    def render_html(self, docids, data=None):
        self.model = self.env.context.get('active_model')
        docs = self.env[self.model].browse(self.env.context.get('active_id'))
        # print(docs)
        installmet_records = []
        # if docs.date_from and docs.date_to:
        #     for order in orders:
        #         if parse(docs.date_from) <= parse(order.date_order) and parse(docs.date_to) >= parse(order.date_order):
        #             installmet_records.append(order);
        # else:
        #     raise UserError("Please enter duration")

        docargs = {
            'doc_ids': self.ids,
            'doc_model': self.model,
            'docs': docs,
            'time': time,
        }
        return self.env['report'].render('hr_loan.report_hrloan', docargs)