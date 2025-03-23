/** @odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { Order, Orderline } from "@point_of_sale/app/store/models";
import { OutOfStockMessagePopup } from "@pos_stocks/js/popups";

patch(PosStore.prototype, {
    wk_change_qty_css() {
        var self = this;
        var products_qty = {};

        this.get_order_list().forEach(order => {
            order.get_orderlines().forEach(line => {
                if (line.product){
                    if(products_qty[line.product.id] == undefined){
                        products_qty[line.product.id] = line.quantity
                    } else {
                        products_qty[line.product.id]+= line.quantity
                    }
                }
            });
        });

        if(Object.keys(products_qty).length){
            Object.keys(products_qty).forEach(product_id => {
                if((self.db.product_by_id[product_id].wk_qty_available != undefined)){
                    var final_qty = self.db.product_by_id[product_id].original_qty_available - products_qty[product_id];
                    if (!(final_qty < self.config.wk_deny_val)) {
                        self.db.product_by_id[product_id].wk_qty_available = final_qty;
                    }
                }
            });
        }
        self.values_updated_on_load = true
    },
    async _loadProductProduct(products) {
        var self = this;
        super._loadProductProduct(...arguments);
        products.forEach(wkproduct => {
            self.db.product_by_id[wkproduct.id].wk_qty_available = wkproduct.wk_qty_available;
            self.db.product_by_id[wkproduct.id].original_qty_available = wkproduct.original_qty_available;
        });
    },
    push_single_order(order) {
        var self = this;
        if (order) {
            if (!order.is_return_order) {
                var wk_order_line = order.get_orderlines();

                for (var j = 0; j < wk_order_line.length; j++) {
                    if (!wk_order_line[j].stock_location_id){
                        if(self.db.product_by_id[wk_order_line[j].product.id]){
                            self.db.product_by_id[wk_order_line[j].product.id].original_qty_available = self.db.product_by_id[wk_order_line[j].product.id].original_qty_available - wk_order_line[j].quantity;
                        }
                    }
                }
            } else {
                var wk_order_line = order.get_orderlines();
                for (var j = 0; j < wk_order_line.length; j++) {
                    if(self.db.product_by_id[wk_order_line[j].product.id]){
                        self.db.product_by_id[wk_order_line[j].product.id].original_qty_available = self.db.product_by_id[wk_order_line[j].product.id].original_qty_available + wk_order_line[j].quantity;
                    }
                }
            }
        }
        return super.push_single_order(...arguments);
    },
    push_orders(opts = {}) {
        var self = this;
        let order = this.get_order();
        if (order) {
            if (!order.is_return_order) {
                var wk_order_line = order.get_orderlines();
                for (var j = 0; j < wk_order_line.length; j++) {
                    if (!wk_order_line[j].stock_location_id){
                        if(self.db.product_by_id[wk_order_line[j].product.id]){
                            self.db.product_by_id[wk_order_line[j].product.id].original_qty_available = self.db.product_by_id[wk_order_line[j].product.id].original_qty_available - wk_order_line[j].quantity;
                        }
                    }
                }
            } else {
                var wk_order_line = order.get_orderlines();
                for (var j = 0; j < wk_order_line.length; j++) {
                    if(self.db.product_by_id[wk_order_line[j].product.id]){
                        self.db.product_by_id[wk_order_line[j].product.id].original_qty_available = self.db.product_by_id[wk_order_line[j].product.id].original_qty_available + wk_order_line[j].quantity;
                    }
                }
            }
        }
        return super.push_orders(...arguments);
    },
});

patch(Order.prototype, {
    add_product(product, options) {
        var self = this;
        options = options || {};
        // warehouse management compatiblity code start---------------
        for (var i = 0; i < this.orderlines; i++) {
          if ((self.orderlines[i].product.id == product.id) && self.orderlines[i].stock_location_id) {
            options.merge = false;
          }
        }
        // warehouse management compatiblity code end---------------
        if (!self.pos.config.wk_continous_sale && self.pos.config.wk_display_stock && !self.pos.get_order().is_return_order) {
            if(self.pos && self.pos.get_order_list() && self.pos.get_order_list().length){
                var total_qty = 1;

                self.pos.get_order_list().forEach(order => {
                    order.get_orderlines().forEach(line => {
                        if(line.product.id == product.id) total_qty+=line.quantity;
                    });
                });
    
                if((self.pos.db.product_by_id[product.id].wk_qty_available != undefined)){
                    var final_qty = self.pos.db.product_by_id[product.id].original_qty_available - total_qty;

                    if (self.pos.db.product_by_id[product.id].type ==='service'){
                        return super.add_product(...arguments)
                    }else if (!(options && options.quantity < 0 && options.refunded_orderline_id) && final_qty < self.pos.config.wk_deny_val) {
                        this.env.services.popup.add(OutOfStockMessagePopup, {
                            title: _t("Warning !!!!"),
                            body: _t("(" + product.display_name + ")" + self.pos.config.wk_error_msg + "."),
                            product_id: product.id,
                        });
                        $(".numpad-backspace").trigger("update_buffer");
                        return false
                    }else {
                        self.pos.db.product_by_id[product.id].wk_qty_available = final_qty
                        return super.add_product(...arguments)
                    }
                }
            }
        } else super.add_product(...arguments)
    },
    init_from_JSON(json) {
        this.order_id = json.order_id
        return super.init_from_JSON(...arguments)
    }
});

patch(Orderline.prototype, {
    set_quantity(quantity, keep_price) {
        var self = this;

        if (self.stock_location_id && quantity && quantity != "remove") {
            var order = self.pos.get_order();
            if (order && order.selected_orderline && order.selected_orderline.cid == self.cid) {
                this.env.services.popup.add(OutOfStockMessagePopup, {
                    title: _t("Warning !!!!"),
                    body: _t("Selected orderline product have different stock location, you can't update the qty of this orderline"),
                    product_id: self.product.id,
                });
                $(".numpad-backspace").trigger("update_buffer");
                return;
            } else return super.set_quantity(...arguments);
        }
  
        if(self.pos && self.pos.get_order_list() && self.pos.get_order_list().length){
            var total_qty = 0;

            if(quantity == 'remove') total_qty+= 0;
            else {
                if(!quantity)total_qty = 0;
                else total_qty = quantity;
            }
          
            self.pos.get_order_list().forEach(order => {
                if(!(order.cid == self.order.cid)){
                    order.get_orderlines().forEach(line => {
                        if(line.product.id == self.product.id){
                          total_qty+=line.quantity
                        }
                    });
                }
            });
  
            if(self.pos.config.wk_display_stock && (self.pos.db.product_by_id[self.product.id].wk_qty_available != undefined)){
                var final_qty = self.pos.db.product_by_id[self.product.id].original_qty_available - total_qty;

                if (self.pos.db.product_by_id[self.product.id].type ==='service'){
                    return super.set_quantity(...arguments);
                }
                if (self.pos.config.wk_continous_sale){
                    self.pos.db.product_by_id[self.product.id].wk_qty_available = final_qty
                } else if (keep_price && quantity && quantity > 0 && final_qty < self.pos.config.wk_deny_val) {
                    if (!self.order.order_id) {
                        this.env.services.popup.add(OutOfStockMessagePopup, {
                            title: _t("Warning !!!!"),
                            body: _t("(" + self.product.display_name + ")" + self.pos.config.wk_error_msg + "."),
                            product_id: self.product.id,
                        });
                        $(".numpad-backspace").trigger("update_buffer");
                        return false
                    } else return super.set_quantity(...arguments);
                } else self.pos.db.product_by_id[self.product.id].wk_qty_available = final_qty
            }
        } 
        return super.set_quantity(...arguments);
    }
});