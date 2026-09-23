import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ملاحظة: متعملش mobile = fields.Char(required=True) هنا.
    # required=True على مستوى الحقل بيأثر على res.partner كله (شركات، عناوين
    # توصيل/فواتير، موردين، بورتال يوزرز...) مش بس عميل الـ POS الجديد،
    # وأي partner قديم من غير mobile هيوقف الـ migration/upgrade.
    # عشان كده الإجبارية بتتطبق هنا في create() بس، وقت إنشاء عميل جديد.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            mobile = (vals.get('mobile') or '').strip()
            if not mobile:
                raise ValidationError(_("رقم الجوال مطلوب للعملاء الجدد، برجاء إدخاله."))
        return super().create(vals_list)

    @api.constrains('mobile')
    def _check_mobile_validation(self):
        for partner in self:
            if partner.mobile:
                # إزالة المسافات إن وجدت
                clean_mobile = partner.mobile.replace(' ', '')

                # التحقق: أرقام إنجليزية (0-9) فقط وطولها 10 بالظبط.
                # استخدمنا re.ASCII عشان \d متقبلش أرقام هندية/عربية
                # (٠١٢٣٤٥٦٧٨٩) اللي بترجع True مع str.isdigit() العادية.
                if not re.fullmatch(r'\d{10}', clean_mobile, re.ASCII):
                    # الدالة _() تقوم بجلب الترجمة العربية إذا كانت واجهة المستخدم بالعربية
                    # (بشرط وجود msgid/msgstr مطابقين في ملف i18n/ar.po الخاص بالموديول)
                    raise ValidationError(_("Sorry, the mobile number must consist of exactly 10 digits."))