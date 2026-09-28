from odoo import models, api


class ResCountry(models.Model):
    _inherit = 'res.country'

    @api.model
    def _update_arabic_names(self):
        # قاموس يربط كود الدولة بالترجمة العربية
        translations = {
            'BQ': 'بونير وسينت أوستاتيوس وسابا',
            'SZ': 'إسواتيني',
            'MK': 'مقدونيا الشمالية',
            'SH': 'سانت هيلينا وأسينشين وتريستان دا كونا',
            'VC': 'سانت فنسنت والجرينادينز',
            'SX': 'سينت مارتن (الجزء الهولندي)',
            'SJ': 'سفالبارد ويان ماين',
            'ST': 'ساو تومي وبرينسيبي',
            'TL': 'تيمور الشرقية',
            'TR': 'تركيا',
            'UM': 'جزر الولايات المتحدة الصغيرة النائية',
            'VU': 'فانواتو',
            'WF': 'والس وفوتونا',
        }

        for code, ar_name in translations.items():
            # البحث عن الدولة باستخدام الكود الخاص بها
            country = self.search([('code', '=', code)], limit=1)
            if country:
                # تحديث الاسم باللغة العربية فقط دون المساس بالاسم الإنجليزي
                country.with_context(lang='ar_001').name = ar_name