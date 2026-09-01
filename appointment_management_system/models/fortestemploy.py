from odoo import models, fields


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # مفيش داعي للـ related، أودو هيقرأهم من الداتابيز مباشرة
    is_appointment_employee = fields.Boolean(readonly=True)
    location_id = fields.Many2one('stock.location', readonly=True)
    credit_limit_loan = fields.Float(readonly=True)
    credit_limit_advance = fields.Float(readonly=True)

    # ⚠️ ركز هنا: أنا غيرته لـ Many2one عشان يتطابق مع الاسم، لو هو نوع تاني في الأصل غيره للنوع الصح
    loan_and_advance_user = fields.Many2one('res.users', readonly=True)

    limited_discount = fields.Float(readonly=True)