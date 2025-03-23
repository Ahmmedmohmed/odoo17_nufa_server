/** @odoo-module **/
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";

export class SetProductListButton extends Component {
    setup() {
    super.setup();
this.pos = usePos();
 const { popup } = this.env.services;
        this.popup = popup;
    }
    get productsList() {
        let list = [];
        list = this.pos.db.get_product_by_category(
            this.pos.selectedCategoryId
        );
        return list.sort(function(a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }
   async onClick() {
            let list = this.productsList;
            const cashierList = this.pos.hr_employee.map((cashier) => {
                    return {
                        id: cashier.id,
                        item: cashier,
                        label: cashier.name,
                        isSelected: false,
                    };
                });
              const { confirmed, payload: cashier } = await this.popup.add(SelectionPopup, {
                title: _t("Select The SalesPerson"),
                list: cashierList,
            });
              if (confirmed) {
             this.pos.selectedOrder.selected_orderline.cashier = cashier.name;
             this.pos.selectedOrder.selected_orderline.employee_id = cashier.id;
        }
    }
}
SetProductListButton.template = "CashierButton";
ProductScreen.addControlButton({
    component: SetProductListButton,
    condition: function() {
        return true;
    },
});


