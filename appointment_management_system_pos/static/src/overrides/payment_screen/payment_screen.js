/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    // async _finalizeValidation() {
    async afterOrderValidation(suggestToSync = true) {
        try {
            await this.updateAppointment();
        } catch (error) {
            console.error('Error updating appointments after order validation:', error);
            // Continue with the normal flow even if appointment update fails
        }
        
        // Check if component is still valid before calling super
        if (this.__owl__ && this.__owl__.status !== 'destroyed') {
            await super.afterOrderValidation(...arguments);
        }
    },
    async updateAppointment(){
      try {
        // Check if component is still mounted before making ORM calls
        if (this.__owl__ && this.__owl__.status === 'destroyed') {
          console.warn('PaymentScreen component is destroyed, skipping appointment update');
          return;
        }

        this.currentOrder.cashier = this.pos.get_cashier();
        const serviceLines = this.currentOrder.orderlines.filter(line => line.appointment_id);
        
        if (serviceLines && serviceLines.length > 0) {
          for (var i = 0; i < serviceLines.length; i++) {
            // Check component status again before each call
            if (this.__owl__ && this.__owl__.status === 'destroyed') {
              console.warn('PaymentScreen component destroyed during appointment update');
              break;
            }

            var status = '2';
            if (serviceLines[i].refunded_orderline_id) {
              status = '4';
            }
            
            try {
              const updateAppointment = await this.orm.call(
                  "product.product",
                  "action_update_appointment",
                  [false, serviceLines[i].appointment_id, status]
              );
            } catch (error) {
              console.error('Failed to update appointment:', serviceLines[i].appointment_id, error);
              // Continue with other appointments even if one fails
            }
          }
        }
      } catch (error) {
        console.error('Error in updateAppointment:', error);
        // Don't throw the error to prevent breaking the payment flow
      }
    }
});
