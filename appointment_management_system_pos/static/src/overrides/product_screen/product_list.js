/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        let list = [];
        const { db } = this.pos;
        if (this.searchWord !== "") {
            list = db.search_product_in_category(this.selectedCategoryId, this.searchWord);
        } else if (this.selectedCategoryId === 0 || this.selectedCategoryId === db.root_category_id) {
            const validCatIds = Object.keys(db.category_by_id)
                .map(Number)
                .filter((id) => {
                    if (id === 0 || id === db.root_category_id) return true;
                    const cat = db.category_by_id[id];
                    return !cat || !cat.is_appointment_category;
                });
            const seen = new Set();
            for (const catId of validCatIds) {
                const productIds = db.product_by_category_id[catId] || [];
                for (const pid of productIds) {
                    if (!seen.has(pid)) {
                        seen.add(pid);
                        const product = db.product_by_id[pid];
                        if (product) list.push(product);
                    }
                }
            }
        } else {
            list = db.get_product_by_category(this.selectedCategoryId);
        }
        list = list.filter(
            (product) =>
                product.is_appointment_service !== true &&
                product.is_appointment_package !== true &&
                !this.getProductListToNotDisplay().includes(product.id)
        );
        return list.sort((a, b) => a.display_name.localeCompare(b.display_name));
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
