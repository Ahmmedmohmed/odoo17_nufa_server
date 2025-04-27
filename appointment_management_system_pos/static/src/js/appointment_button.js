/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { AppointmentPopup } from "@appointment_management_system_pos/js/appointment_popup";

export class AppointmentButton extends Component {
    static template = "appointment_management_system_pos.AppointmentButton";

    setup() {
        this.popup = useService("popup");
        this.pos = usePos();
    }
    async click() {

      const { confirmed, payload } = await this.popup.add(AppointmentPopup, {
          title: _t("Add Appointment"),
      });
      console.log(confirmed);
      console.log(payload);
      if (confirmed) {
        debugger
        const service = await this.pos.db.get_product_by_id(parseInt(payload.service_id));
        var line = await this.pos.get_order().add_product(service,{
            quantity: 1,
            price: parseFloat(payload.price),
            extras: { price_type: "manual" },
        });
        line.appointment_id = payload.appointment_id
      }
      return;
    }
    // _shouldBeHighlighted(orderTotal, eWalletPrograms, eWalletRewards) {
    //     return (orderTotal < 0 && eWalletPrograms.length >= 1) || eWalletRewards.length >= 1;
    // }
    // _getText(orderTotal, eWalletPrograms, eWalletRewards) {
    //     if (orderTotal < 0 && eWalletPrograms.length >= 1) {
    //         return _t("eWallet Refund");
    //     } else if (eWalletRewards.length >= 1) {
    //         return _t("eWallet Pay");
    //     } else {
    //         return _t("eWallet");
    //     }
    // }
}

ProductScreen.addControlButton({
    component: AppointmentButton,
    condition: function () {
        return this.pos.config.allow_appointment;
    },
});
