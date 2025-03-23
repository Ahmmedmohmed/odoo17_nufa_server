/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/store/models";

//Patching Orderline to change the uom by adding a function.
patch(Orderline.prototype, {
        setup(_defaultObj, options) {
        super.setup(...arguments);
        if(options.json){
        this.cashier = this.cashier;
        this.employee_id = this.employee_id;
        }
    },
    export_as_JSON(){
        var json = super.export_as_JSON.call(this);
        json.cashier = this.cashier || false
        json.employee_id = this.employee_id || false
            return json
    },
            // Set the unit from the JSON data
    init_from_JSON(json){
        super.init_from_JSON(...arguments);
         this.cashier = json.cashier;
         this.employee_id = json.employee_id;
    },
    get_cashier(){
    return this.cashier , this.employee_id },
     getDisplayData() {
        return {
            ...super.getDisplayData(),
            cashier: this.cashier,
            employee_id: this.employee_id,
        };
    },
});







