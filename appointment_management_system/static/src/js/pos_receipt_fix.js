/** @odoo-module **/

// 1. المسار الصحيح لاستدعاء Orderline في أودو 17
import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

// 2. تحديث طريقة الباتش بدون اسم سترينج
patch(Orderline.prototype, {
    export_for_printing() {
        // 3. استخدام super القياسية بدلاً من this._super القديمة
        const line = super.export_for_printing(...arguments);

        // هنا بنبعت الحقول للفاتورة عشان الـ XML يقدر يقرأها
        // بافتراض إن الحقول دي موجودة جوا المنتج (Product)
        if (this.product) {
            line.service_slot_inside = this.product.service_slot_inside || 1;
            line.service_slot_outside = this.product.service_slot_outside || 1;
        }

        // ولو الحقول دي إنت ضايفها في الـ pos.order.line مباشرة، استخدم السطور دي بدل اللي فوق:
        // line.service_slot_inside = this.service_slot_inside || 1;
        // line.service_slot_outside = this.service_slot_outside || 1;

        line.appointment_type = this.appointment_type || 'inside';

        return line;
    }
});