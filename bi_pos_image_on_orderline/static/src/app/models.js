/** @odoo-module */

import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {      
    setup() {
        super.setup(...arguments);
    },
    
    getDisplayData() {
        return {
        	...super.getDisplayData(),
            image_id: this.get_product().id,
            
        };
    }
});
