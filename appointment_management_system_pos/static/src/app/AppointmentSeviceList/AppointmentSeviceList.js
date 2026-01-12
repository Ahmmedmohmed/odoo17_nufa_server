/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { AppointmentSeviceItem } from "@appointment_management_system_pos/app/AppointmentSeviceItem/AppointmentSeviceItem";
import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";

export class AppointmentSeviceList extends Component {
    static template = "appointment_management_system_pos.AppointmentSeviceList";
    static components = {
        AppointmentSeviceItem,
    };
    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
    }
    async onProductInfoClick(product) {
        const info = await this.pos.getProductInfo(product, 1);
        this.popup.add(ProductInfoPopup, { info: info, product: product });
    }
}
