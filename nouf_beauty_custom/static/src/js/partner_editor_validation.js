/** @odoo-module */

import { PartnerEditor } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerEditor.prototype, {
    async save() {
        // نجلب التعديلات الجديدة أو القيمة القديمة لو العميل موجود مسبقاً
        let mobile = this.changes.mobile !== undefined ? this.changes.mobile : this.props.partner.mobile;

        // 1. التحقق من وجود رقم الجوال
        if (!mobile) {
            this.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
            });
            return false; // نمنع عملية الحفظ
        }

        // 2. إزالة المسافات والتحقق من أنه 10 أرقام فقط
        let cleanMobile = mobile.replace(/\s+/g, '');
        if (!/^\d{10}$/.test(cleanMobile)) {
            this.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
            });
            return false; // نمنع عملية الحفظ
        }

        // لو كل الشروط اتحققت، نكمل عملية الحفظ الطبيعية
        return super.save(...arguments);
    }
});