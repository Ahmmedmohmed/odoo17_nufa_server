/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerListScreen.prototype, {
    async savePartner(partner, changes) {
        // التحقق: هل العميل جديد؟ (العميل الجديد ملوش ID لسه)
        const isNewPartner = !partner || !partner.id;

        // هنطبق الإجبار في حالتين بس:
        // 1. العميل جديد.
        // 2. العميل قديم بس الكاشير بيعدل رقم موبايله تحديداً دلوقتي.
        if (isNewPartner || changes.mobile !== undefined) {
            let mobile = changes.mobile !== undefined ? changes.mobile : (partner ? partner.mobile : '');
            let cleanMobile = mobile ? mobile.toString().replace(/\s+/g, '') : '';

            if (!cleanMobile) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
                });
                return; // 🛑 نمنع الإنشاء
            }

            if (!/^\d{10}$/.test(cleanMobile)) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
                });
                return; // 🛑 نمنع الإنشاء
            }
        }

        // لو العميل قديم ومعدلش الموبايل، أو لو الموبايل الجديد سليم، نحفظ طبيعي
        return super.savePartner(partner, changes);
    }
});