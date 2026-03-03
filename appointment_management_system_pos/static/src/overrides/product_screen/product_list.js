/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        let list = super.productsToDisplay;
        list = list.filter(
            (product) => !product.is_appointment_service && !product.is_appointment_package
        );
        return list;
    },
    getCategories() {
        let categories = super.getCategories();
        const db = this.pos.db;
        categories = categories.filter((cat) => {
            const catData = db.category_by_id[cat.id];
            return !catData || !catData.is_appointment_category;
        });
        return categories;
    },
});
