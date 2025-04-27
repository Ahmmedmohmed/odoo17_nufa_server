/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Orderline, Order } from "@point_of_sale/app/store/models";

patch(Orderline.prototype, {
    export_as_JSON(){
        var json = super.export_as_JSON.call(this);
        json.appointment_id = this.appointment_id;
        return json;
    },
    init_from_JSON(json){
        super.init_from_JSON(...arguments);
        if (json.appointment_id) {
          this.appointment_id = json.appointment_id;
        }
    },
    set_uom(uom_id){
        this.product_uom_id = uom_id;
    },
});
