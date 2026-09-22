/** @odoo-module */

import { PartnerEditor } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(PartnerEditor.prototype, {
    async save() {
        // الصح: التغييرات في state.changes
        const changes = this.state.changes;
        const partner = this.props.partner || {};

        let mobile = changes.mobile !== undefined
            ? changes.mobile
            : partner.mobile;

        // 1. التحقق من وجود رقم الجوال
        if (!mobile) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('حقل رقم الجوال مطلوب، يرجى إدخال الرقم.'),
            });
            return false;
        }

        // 2. إزالة المسافات والتحقق من 10 أرقام
        let cleanMobile = mobile.toString().replace(/\s+/g, '');
        if (!/^\d{10}$/.test(cleanMobile)) {
            this.env.services.popup.add(ErrorPopup, {
                title: _t('خطأ في الإدخال'),
                body: _t('عفواً، يجب أن يتكون رقم الجوال من 10 أرقام صحيحة.'),
            });
            return false;
        }

        // كل الشروط اتحققت، نكمل الحفظ
        return super.save(...arguments);
    }
});