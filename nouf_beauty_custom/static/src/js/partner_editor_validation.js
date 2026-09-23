/** @odoo-module */

import { PartnerListScreen } from "@point_of_sale/app/screens/partner_list/partner_list";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerListScreen.prototype, {

    // إحنا هنا بنستهدف دالة "إنشاء العميل الجديد" فقط! (العميل القديم مش هيتأثر أبداً)
    createPartner() {
        // بنخلي أودو يجهز شاشة العميل الجديد زي ما هو متعود
        super.createPartner(...arguments);

        // هنا بنمسك دالة الحفظ اللي أودو مجهزها، ونغلفها بالقيود بتاعتنا
        const originalSave = this.state.editModeProps.save;

        this.state.editModeProps.save = async (changes) => {
            let mobile = changes.mobile || changes.phone || '';
            let cleanMobile = mobile.toString().replace(/\s+/g, '');

            // 1. لو الكاشير ساب الموبايل فاضي
            if (!cleanMobile) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('حقل رقم الجوال مطلوب للعملاء الجدد، يرجى إدخال الرقم.'),
                });
                return; // 🛑 نوقف الحفظ، والشاشة هتفضل مفتوحة قدامه عشان يصلح الرقم
            }

            // 2. لو الرقم مش 10 أرقام
            if (!/^\d{10}$/.test(cleanMobile)) {
                this.env.services.popup.add(ErrorPopup, {
                    title: _t('خطأ في الإدخال'),
                    body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
                });
                return; // 🛑 نوقف الحفظ
            }

            // 3. لو الرقم سليم 100%، هنشغل دالة الحفظ الأصلية بتاعت أودو
            return originalSave(changes);
        };
    }
});