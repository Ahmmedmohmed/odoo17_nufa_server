/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async _finalizeValidation() {
        await this.updateAppointment();
        await super._finalizeValidation(...arguments);
    },
    async updateAppointment(){
      this.currentOrder.cashier = this.pos.get_cashier();
      const serviceLines = this.currentOrder.orderlines.filter(line => line.appointment_id);
      if (serviceLines) {
        for (var i = 0; i < serviceLines.length; i++) {
          const updateAppointment = await this.orm.call(
              "product.product",
              "action_update_appointment",
              [false,serviceLines[i].appointment_id]
          );
        }

      }

    }
});
