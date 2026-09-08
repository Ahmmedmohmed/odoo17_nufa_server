/** @odoo-module **/
import { Orderline } from 'point_of_sale.models';
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, "appointment_management_system.receipt_fix", {
    export_for_printing() {
        const line = this._super(...arguments);

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