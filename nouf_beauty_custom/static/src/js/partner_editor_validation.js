/** @odoo-module */

import * as PartnerEditorModule from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

// استخراج الكلاس أياً كان اسمه في النسخة الخاصة بك
const PartnerEditorClass = PartnerEditorModule.PartnerEditor || PartnerEditorModule.PartnerDetailsEdit || Object.values(PartnerEditorModule)[0];

// تم إزالة الاسم النصي للباتش بناءً على تحديث أودو 17 الأخير
patch(PartnerEditorClass.prototype, {

    async save() {
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

        return super.save(...arguments);
    },

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