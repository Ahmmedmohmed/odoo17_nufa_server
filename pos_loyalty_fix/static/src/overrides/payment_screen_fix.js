/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

// Override the entire ORM service for PaymentScreen to handle destruction
patch(PaymentScreen.prototype, {
    
    setup() {
        super.setup();
        
        // Create a safe ORM wrapper
        const originalOrm = this.orm;
        this.orm = {
            ...originalOrm,
            call: async (model, method, args, kwargs) => {
                try {
                    // Check component state before making call
                    if (!this.__owl__ || this.__owl__.status === "destroyed") {
                        console.warn("Skipping ORM call - component destroyed");
                        return { successful: true, payload: {} };
                    }
                    
                    const result = await originalOrm.call(model, method, args, kwargs);
                    
                    // Check component state after async operation
                    if (!this.__owl__ || this.__owl__.status === "destroyed") {
                        console.warn("Component destroyed during ORM call");
                        return { successful: true, payload: {} };
                    }
                    
                    return result;
                } catch (error) {
                    if (error.message && error.message.includes("Component is destroyed")) {
                        console.warn("Caught component destruction error in ORM call");
                        return { successful: true, payload: {} };
                    }
                    throw error;
                }
            }
        };
    }
});