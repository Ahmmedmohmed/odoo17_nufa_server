from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # جعل الجوال إجباري من جهة قاعدة البيانات
    mobile = fields.Char(string='Mobile', required=True)

    # جعل الهاتف اختياري
    phone = fields.Char(string='Phone', required=False)

    @api.constrains('mobile')
    def _check_mobile_validation(self):
        for partner in self:
            if partner.mobile:
                # إزالة المسافات إن وجدت
                clean_mobile = partner.mobile.replace(' ', '')

                # التحقق: أرقام فقط وطولها 10
                if not clean_mobile.isdigit() or len(clean_mobile) != 10:
                    # الدالة _() تقوم بجلب الترجمة العربية إذا كانت واجهة المستخدم بالعربية
                    raise ValidationError(_("Sorry, the mobile number must consist of exactly 10 digits."))