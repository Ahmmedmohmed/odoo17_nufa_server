/** @odoo-module */

import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { localization } from "@web/core/l10n/localization";

// كل رسائل الخطأ متجمعة هنا (عربي / إنجليزي) - مفيش أي اعتماد على ملفات .po
const MESSAGES = {
    ar: {
        title: "خطأ في الإدخال",
        empty: "حقل رقم الجوال مطلوب للعملاء الجدد، برجاء إدخال الرقم.",
        invalid: "رقم الجوال غير صحيح، يجب أن يحتوي على أرقام فقط.",
        tooShort: "رقم الجوال غير مكتمل، يجب أن يتكون من 10 أرقام بالضبط.",
        tooLong: "رقم الجوال طويل أكثر من اللازم، يجب أن يتكون من 10 أرقام فقط.",
    },
    en: {
        title: "Input Error",
        empty: "Mobile number is required for new customers, please enter it.",
        invalid: "Mobile number is invalid, it must contain digits only.",
        tooShort: "Mobile number is incomplete, it must be exactly 10 digits.",
        tooLong: "Mobile number is too long, it must be exactly 10 digits.",
    },
};

if (PartnerDetailsEdit && PartnerDetailsEdit.prototype) {
    patch(PartnerDetailsEdit.prototype, {

        async save() {
            // القيود دي بتتفعّل بس مع "عميل جديد" - العميل القديم مش هيتأثر
            const isNewPartner = !this.props.partner || !this.props.partner.id;

            if (isNewPartner) {
                const dir = (document.documentElement.dir || document.body.dir || "").toLowerCase();
                const isArabic = dir === "rtl";
                const t = isArabic ? MESSAGES.ar : MESSAGES.en;

                const changes = this.state.changes;
                const partner = this.props.partner || {};

                let mobile = changes.mobile !== undefined ? changes.mobile
                           : changes.phone !== undefined ? changes.phone
                           : (partner.mobile || partner.phone || "");

                const cleanMobile = mobile ? mobile.toString().replace(/\s+/g, "") : "";

                if (!cleanMobile) {
                    this.env.services.popup.add(ErrorPopup, { title: t.title, body: t.empty });
                    return false;
                }
                if (!/^\d+$/.test(cleanMobile)) {
                    this.env.services.popup.add(ErrorPopup, { title: t.title, body: t.invalid });
                    return false;
                }
                if (cleanMobile.length < 10) {
                    this.env.services.popup.add(ErrorPopup, { title: t.title, body: t.tooShort });
                    return false;
                }
                if (cleanMobile.length > 10) {
                    this.env.services.popup.add(ErrorPopup, { title: t.title, body: t.tooLong });
                    return false;
                }
            }

            return super.save(...arguments);
        }
    });
} else {
    console.error("⚠️ nouf_beauty_custom: PartnerDetailsEdit undefined - راجع مسار الـ import");
}