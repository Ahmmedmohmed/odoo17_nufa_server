/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Orderline, Order } from "@point_of_sale/app/store/models";

patch(Orderline.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        this.appointment_id = null || options.json?.appointment_id;
        this.appointment_name = null || options.json?.appointment_name;
        this.employee_name = null || options.json?.employee_name;
        this.branch_name = null || options.json?.branch_name;
        this.appointment_type = null || options.json?.appointment_type;
        this.date = null || options.json?.date;
        this.slot_name = null || options.json?.slot_name;
        this.is_appointment_line =options.json&& options.json.appointment_id? true:false ;
    },
    export_as_JSON(){
        var json = super.export_as_JSON.call(this);
        json.appointment_id = this.appointment_id;
        json.employee_name = this.employee_name;
        json.branch_name = this.branch_name;
        json.appointment_type = this.appointment_type;
        json.date = this.date;
        json.slot_name = this.slot_name;
        json.is_appointment_line = this.is_appointment_line;
        return json;
    },
    init_from_JSON(json){
        super.init_from_JSON(...arguments);
        if (json.appointment_id) {
          this.appointment_id = json.appointment_id;
          this.appointment_name = json.appointment_name;
          this.is_appointment_line = json.is_appointment_line;
          this.employee_name = json.employee_name;
          this.branch_name = json.branch_name;
          this.appointment_type = json.appointment_type;
          this.date = json.date;
          this.slot_name = json.slot_name;
        }
    },

    getDisplayData() {

        return {
            ...super.getDisplayData(),
            is_appointment_line: this.is_appointment_line,
            appointment_id: this.appointment_id,
            appointment_name: this.appointment_name,
            employee_name: this.employee_name,
            branch_name: this.branch_name,
            appointment_type: this.appointment_type,
            date: this.date,
            slot_name: this.slot_name,
        };
    },

});
