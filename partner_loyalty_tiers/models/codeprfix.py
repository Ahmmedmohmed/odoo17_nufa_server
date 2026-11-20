from odoo import models, fields, api
import random
import string

class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'

    # 1. إضافة الحقل الجديد اللي هيظهر في الشاشة
    coupon_prefix = fields.Char(string="Coupon Prefix", help="مثال: KSA-")

    def generate_coupons(self):
        # 2. نجيب الكوبونات اللي موجودة "قبل" ما ندوس على الزرار
        cards_before = self.env['loyalty.card'].search([('program_id', '=', self.program_id.id)])

        # 3. نشغل الكود الأصلي بتاع أودو عشان يكريت الكوبونات بطريقته
        res = super(LoyaltyGenerateWizard, self).generate_coupons()

        # 4. لو اليوزر كاتب Prefix، نعدل الكوبونات "الجديدة" بس
        if self.coupon_prefix:
            cards_after = self.env['loyalty.card'].search([('program_id', '=', self.program_id.id)])
            new_cards = cards_after - cards_before # كده مسكنا الكوبونات اللي لسه متولدة حالا

            for card in new_cards:
                # 5. توليد كود عشوائي غير متسلسل (مثلا 6 حروف وأرقام عشوائية)
                random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

                # 6. دمج الـ Prefix مع الكود العشوائي
                card.code = f"{self.coupon_prefix}{random_str}"

        return res