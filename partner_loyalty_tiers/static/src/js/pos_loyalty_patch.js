/** @odoo-module */

// ✅ المسار الأصلي صح — Order مش PosOrder
import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

// ✅ بديل ErrorPopup في Odoo 17
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

console.log("🚀 [Loyalty Tiers] تم تحميل ملف التحقق من الجوائز (Validation Mode) بنجاح!");

patch(Order.prototype, {
    _apply_reward(reward, coupon_id) {

        // 1. فحص هل الجائزة مقيدة بمستويات معينة؟
        if (reward && reward.allowed_tier_ids && reward.allowed_tier_ids.length > 0) {
            const partner = this.get_partner();

            // 2. التحقق من وجود عميل أصلاً
            if (!partner) {
                this.pos.env.services.dialog.add(AlertDialog, {
                    title: "تنبيه مستوى الولاء",
                    body: "يجب اختيار العميل أولاً للتحقق مما إذا كان يمتلك مستوى الولاء المطلوب لهذه الجائزة.",
                });
                return false;
            }

            // 3. تحديد مستوى العميل الحالي
            const partnerTierId = Array.isArray(partner.loyalty_tier_id)
                ? partner.loyalty_tier_id[0]
                : partner.loyalty_tier_id;

            // 4. التحقق مما إذا كان مستوى العميل ضمن المستويات المسموحة
            const isAllowed = reward.allowed_tier_ids.includes(partnerTierId);

            if (!isAllowed) {
                this.pos.env.services.dialog.add(AlertDialog, {
                    title: "مستوى العميل غير مطابق",
                    body: `عفواً، الجائزة (${reward.description || reward.name}) مخصصة لمستوى ولاء محدد، والعميل الحالي (${partner.name}) غير مشمول في هذا المستوى.`,
                });
                return false;
            }
        }

        // 5. لو كل حاجة تمام — نسمح لأودو يكمل شغله الطبيعي
        return super._apply_reward(...arguments);
    }
});