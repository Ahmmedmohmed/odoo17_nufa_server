from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # res.users بيعمل _inherits على res.partner - يعني create/write هنا
    # بيولّد create/write تلقائي على الـ partner المرتبط بالمستخدم.
    # بنبعت context flag يوقف شرط الجوال في res.partner وقت ما ده بيحصل،
    # لأن مستخدم النظام (موظف/أدمن) مش عميل، ومش المفروض نطلب منه جوال.

    @api.model_create_multi
    def create(self, vals_list):
        return super(ResUsers, self.with_context(skip_mobile_validation=True)).create(vals_list)

    def write(self, vals):
        return super(ResUsers, self.with_context(skip_mobile_validation=True)).write(vals)