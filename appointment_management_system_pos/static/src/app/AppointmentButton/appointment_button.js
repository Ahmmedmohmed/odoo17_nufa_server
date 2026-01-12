/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { AppointmentPopup } from "@appointment_management_system_pos/app/AppointmentPopup/AppointmentPopup";

export class AppointmentButton extends Component {
    static template = "appointment_management_system_pos.AppointmentButton";

    setup() {
        this.popup = useService("popup");
        this.pos = usePos();
    }
    _isDisabled() {
        const partner = this.pos.get_order()?.get_partner();
        return !partner;
    }
    async click() {


      const { confirmed, payload } = await this.popup.add(AppointmentPopup, {
          title: _t("Add Appointment"),
      });

      if (confirmed) {
        debugger
        for (const [key, value] of Object.entries(this.pos.appointmentDetails['services'])) {
          const service = await this.pos.db.get_product_by_id(key);
          var line = await this.pos.get_order().add_product(service,{
              quantity: 1,
              price: value.price,
              extras: { price_type: "manual" },
              appointment_id:value.appointment_id,
              appointment_name:value.appointment_name,
              employee_name:value.employee_name,
              branch_name:value.branch_name,
              appointment_type:value.appointment_type,
              slot_name:value.slot_name,
              date:value.date
          });
          line.appointmentDetail = value
          line.full_product_name =
            this.pos.appointmentDetails['isSelectedServicePack'] ?
              line.full_product_name+'('+this.pos.appointmentDetails['ServicePackFullName']+')':line.full_product_name;
        }


      }
      return;
    }
}

ProductScreen.addControlButton({
    component: AppointmentButton,
    condition: function () {
        return this.pos.config.allow_appointment;
    },
});