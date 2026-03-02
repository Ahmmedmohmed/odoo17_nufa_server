/** @odoo-module **/

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { Component } from "@odoo/owl";

export class AppointmentSevicePackSelection extends Component {
    static template = "appointment_management_system_pos.AppointmentSevicePackSelection";
    static props = {
        class: { String, optional: true },
        name: String,
        productId: Number,
        // price: String,
        // imageUrl: [String, Boolean],
        // productInfo: { Boolean, optional: true },
        // onClick: { type: Function, optional: true },
        // onProductInfoClick: { type: Function, optional: true },
        // onRemoveClick: { type: Function, optional: true },
        // appointments: { type: Object, optional: true },
    }
    static defaultProps = {
        class: "",
    };

    setup() {
        super.setup();
        this.pos = usePos();
    }
    onSelect() {
      console.log('onClick',this);
      if (this.props.productId) {
        this.pos.appointmentDetails['selectedService'] = this.props.productId;
      }
    }

    highlight() {
        var highlightClass = '';
        var SelectedServiceId = this.pos.appointmentDetails['selectedService'];
        console.log(SelectedServiceId , this.props.productId);
        if (SelectedServiceId == this.props.productId) {
          highlightClass = 'green_border';
        }
        return highlightClass;
    }
}
