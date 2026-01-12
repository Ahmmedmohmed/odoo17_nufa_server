/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";

patch(Order.prototype, {
    set_orderline_options(orderline, options) {
      var result = super.set_orderline_options(...arguments);
      if (options.appointment_id !== undefined) {
        orderline.is_appointment_line = true;
        orderline.appointment_id = options.appointment_id;
        orderline.appointment_name = options.appointment_name;
        orderline.employee_name = options.employee_name;
        orderline.branch_name = options.branch_name;
        orderline.appointment_type = options.appointment_type;
        orderline.date = options.date;
        orderline.slot_name = options.slot_name;
      }
    },
});
