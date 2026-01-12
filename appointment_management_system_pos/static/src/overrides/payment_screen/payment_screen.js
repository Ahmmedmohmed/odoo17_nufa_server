/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    // async _finalizeValidation() {
    async afterOrderValidation(suggestToSync = true) {
        await this.updateAppointment();
        await super.afterOrderValidation(...arguments);
    },
    async updateAppointment(){
      this.currentOrder.cashier = this.pos.get_cashier();
      const serviceLines = this.currentOrder.orderlines.filter(line => line.appointment_id);
      if (serviceLines) {
        for (var i = 0; i < serviceLines.length; i++) {
          var status = '2';
          if (serviceLines[i].refunded_orderline_id) {
            status = '4';
          }
          const updateAppointment = await this.orm.call(
              "product.product",
              "action_update_appointment",
              [false,serviceLines[i].appointment_id,status]
          );
        }

      }

    }
});
