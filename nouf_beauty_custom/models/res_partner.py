import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # رسايل الخطأ عربي/إنجليزي مكتوبة هنا مباشرة، وبيتم اختيار المناسب حسب
    # لغة جلسة اليوزر - مش معتمدين على ترجمة ملف .po عشان تشتغل فورًا من
    # غير أي إعداد إضافي (Load a Translation / -u للموديول).
    _MOBILE_MESSAGES = {
        'ar': {
            'required': "رقم الجوال مطلوب للعملاء الجدد، برجاء إدخاله.",
            'format': "عفواً، يجب أن يتكون رقم الجوال من 10 أرقام بالضبط.",
        },
        'en': {
            'required': "Mobile number is required for new customers, please enter it.",
            'format': "Sorry, the mobile number must consist of exactly 10 digits.",
        },
    }

    def _get_mobile_messages(self):
        # لغات العربي في أودو مش دايمًا "ar" بالظبط - ممكن تكون ar_001،
        # ar_EG، ar_SA، ar_AE، ar_MA... إلخ حسب الـ Language Pack المتثبت.
        # عشان كده بنتأكد إن الكود "بيبدأ بـ" ar مش بيساويها تمامًا.
        lang = (self.env.lang or self.env.context.get('lang') or '').lower()
        return self._MOBILE_MESSAGES['ar'] if lang.startswith('ar') else self._MOBILE_MESSAGES['en']

    # ملاحظة: متعملش mobile = fields.Char(required=True) هنا.
    # required=True على مستوى الحقل بيأثر على res.partner كله (شركات، عناوين
    # توصيل/فواتير، موردين، بورتال يوزرز...) مش بس عميل الـ POS الجديد،
    # وأي partner قديم من غير mobile هيوقف الـ migration/upgrade.
    # عشان كده الإجبارية بتتطبق هنا في create() بس، وقت إنشاء عميل جديد.

    @api.model_create_multi
    def create(self, vals_list):
        # لو الطلب جاي من res.users (create/write مستخدم) بنتجاهل الشرط بالكامل -
        # راجع res_users.py لمعرفة إمتى بيتبعت الكونتكست ده.
        if not self.env.context.get('skip_mobile_validation'):
            msgs = self._get_mobile_messages()
            for vals in vals_list:
                # بنطبق الشرط بس على "جهات الاتصال الرئيسية الأفراد"
                # (مش الشركات، ومش العناوين الفرعية زي التوصيل/الفاتورة)
                is_main_contact = (vals.get('type') or 'contact') == 'contact'
                is_company = vals.get('is_company', False)
                is_sub_contact = vals.get('parent_id', False)

                if is_main_contact and not is_company and not is_sub_contact:
                    mobile = (vals.get('mobile') or '').strip()
                    if not mobile:
                        raise ValidationError(msgs['required'])

        return super().create(vals_list)

    @api.constrains('mobile')
    def _check_mobile_validation(self):
        # نفس الاستثناء هنا كمان عشان تنسيق الرقم مايتفحصش لو الطلب جاي
        # من مسار res.users (مش عميل حقيقي بيتعامل بالجوال أصلاً).
        if self.env.context.get('skip_mobile_validation'):
            return

        msgs = self._get_mobile_messages()
        for partner in self:
            if partner.mobile:
                # إزالة المسافات إن وجدت
                clean_mobile = partner.mobile.replace(' ', '')

                # التحقق: أرقام إنجليزية (0-9) فقط وطولها 10 بالظبط.
                # استخدمنا re.ASCII عشان \d متقبلش أرقام هندية/عربية
                # (٠١٢٣٤٥٦٧٨٩) اللي بترجع True مع str.isdigit() العادية.
                if not re.fullmatch(r'\d{10}', clean_mobile, re.ASCII):
                    raise ValidationError(msgs['format'])