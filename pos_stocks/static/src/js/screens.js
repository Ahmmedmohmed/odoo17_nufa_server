/** @odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { patch } from "@web/core/utils/patch";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";

patch(ProductScreen.prototype,{
  	onMounted() {
		var self = this;
		super.onMounted();
		setTimeout(() => {
			if(!self.pos.values_updated_on_load) self.pos.wk_change_qty_css();
		}, 500);
	}
});

patch(ProductsWidget.prototype,{
	get productsToDisplay() {
        var self = this;
      	var result = super.productsToDisplay;
		if (self.pos.config.wk_display_stock && self.pos.config.wk_hide_out_of_stock) {
			var available_product = [];
			result.forEach(product => {
				if ((product.wk_qty_available > 0) || product.type == "service") {   
					available_product.push(product);
				}
			});
			result = available_product;
		}
		return result;
	}
});

patch(ProductCard.prototype,{
	onMounted() {
		if (!this.props.product.image_128) {
			$(this.el).find('.product-content').css('justify-content', 'flex-end');
		}
	}
});