/** @odoo-module */

// 1. نستدعي الموديول بالكامل بدل استدعاء اسم كلاس بعينه
import * as PartnerEditorModule from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

// 2. نستخرج الكلاس أوتوماتيك أياً كان اسمه في نسختك (PartnerEditor أو PartnerDetailsEdit)
const PartnerEditorClass = PartnerEditorModule.PartnerEditor || PartnerEditorModule.PartnerDetailsEdit || Object.values(PartnerEditorModule)[0];

// 3. نعمل الباتش على الكلاس المستخرج
patch(PartnerEditorClass.prototype, {
    async save() {
        const changes = this.state.changes;
        const partner = this.props.partner || {};

        // نجيب القيمة الحالية في الـ field
        let mobile = changes.mobile !== undefined
            ? changes.mobile
            : partner.mobile;

        // نحول لـ string ونشيل المسافات
        let cleanMobile = mobile ? mobile.toString().replace(/\s+/g, '') : '';

        // 1. التحقق إن الموبايل مش فاضي
        if (!cleanMobile) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
            });
            return false;
        }

        // 2. التحقق من 10 أرقام بالظبط
        if (!/^\d{10}$/.test(cleanMobile)) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
            });
            return false;
        }

        return super.save(...arguments);
    }
});