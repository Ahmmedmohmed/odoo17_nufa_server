from odoo import models, api

class UtmSource(models.Model):
    _inherit = 'utm.source'

    @api.model
    def _update_arabic_sources(self):
        translations = {
            'Search engine': 'محرك بحث',
            'Lead Recall': 'استدعاء عميل محتمل',
            'Newsletter': 'نشرة إخبارية',
            'Facebook': 'فيسبوك',
            'Twitter': 'تويتر',
            'LinkedIn': 'لينكد إن',
            'Monster': 'مونستر',
            'Glassdoor': 'جلاس دور',
            'Craigslist': 'كريجزليست',
        }

        for en_name, ar_name in translations.items():
            # إجبار البحث باللغة الإنجليزية لضمان العثور على السجل
            source = self.with_context(lang='en_US').search([('name', '=', en_name)], limit=1)
            if source:
                source.update_field_translations('name', {'ar_001': ar_name})


class UtmMedium(models.Model):
    _inherit = 'utm.medium'

    @api.model
    def _update_arabic_mediums(self):
        translations = {
            'Banner': 'بانر إعلاني',
            'Direct': 'مباشر',
            'Email': 'بريد إلكتروني',
            'Facebook': 'فيسبوك',
            'Google Adwords': 'إعلانات جوجل',
            'LinkedIn': 'لينكد إن',
            'Phone': 'هاتف',
            'Television': 'تلفزيون',
            'Twitter': 'تويتر',
            'Website': 'موقع إلكتروني',
        }

        for en_name, ar_name in translations.items():
            # إجبار البحث باللغة الإنجليزية لضمان العثور على السجل
            medium = self.with_context(lang='en_US').search([('name', '=', en_name)], limit=1)
            if medium:
                medium.update_field_translations('name', {'ar_001': ar_name})