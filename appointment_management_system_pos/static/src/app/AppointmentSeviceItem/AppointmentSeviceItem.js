/** @odoo-module **/

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";

export class AppointmentSeviceItem extends ProductCard {
    static template = "appointment_management_system_pos.AppointmentSeviceItem";
    static props = {
        ...ProductCard.props,
        onRemoveClick: { type: Function, optional: true },
        orderMenu: { type: Object, optional: true },
    }

    setup() {
        super.setup();
        this.pos = usePos();
    }

    highlight() {
        var highlightClass = '';
        if (this.pos.appointmentDetails) {
          var SelectedServiceId = this.pos.SelectedService?this.pos.SelectedService.id:false;
          console.log(SelectedServiceId , this.props.productId);
          if (SelectedServiceId == this.props.productId) {
            highlightClass = 'green_border';
          }
        }

        return highlightClass;
    }
}
