/** @odoo-module */

import * as PartnerEditorModule from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

const PartnerEditorClass = PartnerEditorModule.PartnerEditor || PartnerEditorModule.PartnerDetailsEdit || Object.values(PartnerEditorModule)[0];

// دالة التحقق المنفصلة عشان نستخدمها في أي مكان
function validateMobile(instance) {
    // نجلب التعديلات سواء من state أو مباشرة
    const changes = instance.state ? instance.state.changes : (instance.changes || {});
    const partner = instance.props.partner || {};

    let mobile = changes.mobile !== undefined ? changes.mobile : partner.mobile;
    let cleanMobile = mobile ? mobile.toString().replace(/\s+/g, '') : '';

    // 1. التحقق إن الموبايل مش فاضي
    if (!cleanMobile) {
        instance.env.services.popup.add(ErrorPopup, {
            title: _t('خطأ في الإدخال'),
            body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
        });
        return false;
    }

    // 2. التحقق من 10 أرقام بالظبط
    if (!/^\d{10}$/.test(cleanMobile)) {
        instance.env.services.popup.add(ErrorPopup, {
            title: _t('خطأ في الإدخال'),
            body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
        });
        return false;
    }

    return true;
}

// عمل باتش لكل دوال الحفظ المحتملة في أودو 17
patch(PartnerEditorClass.prototype, {
    async saveChanges() {
        // لو التحقق فشل، وقف الحفظ
        if (!validateMobile(this)) return;
        return super.saveChanges(...arguments);
    },
    async save() {
        // كود احتياطي لو النسخة بتستخدم save
        if (!validateMobile(this)) return;
        return super.save(...arguments);
    }
});