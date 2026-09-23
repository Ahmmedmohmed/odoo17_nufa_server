/** @odoo-module */

import * as PartnerEditorModule from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

// 1. استخراج الكلاس أياً كان اسمه في النسخة الخاصة بك
const PartnerEditorClass = PartnerEditorModule.PartnerEditor || PartnerEditorModule.PartnerDetailsEdit || Object.values(PartnerEditorModule)[0];

// 🚀 السر هنا: إضافة "nouf_beauty_custom.partner_editor_validation" كاسم للباتش (المتغير الثاني)
patch(PartnerEditorClass.prototype, "nouf_beauty_custom.partner_editor_validation", {

    async save() {
        // قراءة التعديلات سواء كانت في this.changes أو this.state.changes
        const changes = this.changes || (this.state && this.state.changes) || {};
        const partner = this.props.partner || {};

        let mobile = changes.mobile !== undefined ? changes.mobile : partner.mobile;
        let cleanMobile = mobile ? mobile.toString().replace(/\s+/g, '') : '';

        // 1. التحقق إن الموبايل مش فاضي
        if (!cleanMobile) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
            });
            return; // 🛑 إيقاف عملية الحفظ نهائياً
        }

        // 2. التحقق من 10 أرقام بالظبط
        if (!/^\d{10}$/.test(cleanMobile)) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
            });
            return; // 🛑 إيقاف عملية الحفظ نهائياً
        }

        // لو كله سليم، نكمل الحفظ الطبيعي
        return super.save(...arguments);
    },

    // دالة احتياطية لو النسخة بتنادي على saveChanges بدل save
    async saveChanges() {
        const changes = this.changes || (this.state && this.state.changes) || {};
        const partner = this.props.partner || {};

        let mobile = changes.mobile !== undefined ? changes.mobile : partner.mobile;
        let cleanMobile = mobile ? mobile.toString().replace(/\s+/g, '') : '';

        if (!cleanMobile) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
            });
            return;
        }

        if (!/^\d{10}$/.test(cleanMobile)) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
            });
            return;
        }

        return super.saveChanges(...arguments);
    }
});