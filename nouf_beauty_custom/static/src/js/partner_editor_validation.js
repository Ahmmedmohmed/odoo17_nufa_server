/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerListScreen.prototype, {
    async savePartner(partnerDetails) {
        // في أودو 17، الدالة دي بتستلم بيانات العميل عشان تحفظها
        // العميل الجديد بيكون لسه ملوش id
        const isNewPartner = !partnerDetails.id;

        // 🚀 هنطبق الإجبار فقط وحصرياً لو الكاشير بيكريت عميل جديد!
        if (isNewPartner) {
            let mobile = partnerDetails.mobile || '';
            let cleanMobile = mobile.toString().replace(/\s+/g, '');

            // 1. لو ساب الموبايل فاضي
            if (!cleanMobile) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('حقل رقم الجوال مطلوب للعملاء الجدد، يرجى إدخال الرقم.'),
                });
                return; // 🛑 إيقاف إنشاء العميل فوراً
            }

            // 2. لو كتب رقم مش 10 أرقام
            if (!/^\d{10}$/.test(cleanMobile)) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
                });
                return; // 🛑 إيقاف إنشاء العميل فوراً
            }
        }

        // لو العميل قديم، أو لو العميل جديد ورقمه سليم 100%، هنكمل الحفظ في الداتا بيز
        return super.savePartner(...arguments);
    }
});