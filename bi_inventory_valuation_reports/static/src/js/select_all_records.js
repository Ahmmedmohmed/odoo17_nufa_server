/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { patch } from "@web/core/utils/patch";
import { jsonrpc } from "@web/core/network/rpc_service";

patch(ListController.prototype, {
    _onSelectDomain: function (ev) {	
			this._super.apply(this, arguments);
			const state = this.model.get(this.handle, {raw: true});
			var flag = state.context.tree_view_ref
			var id = state.id.split("_")[1]
			if (flag == "bi_inventory_valuation_reports.custom_tree_view"){
				jsonrpc("/web/dataset/call_kw/product.product", {
	                model: 'product.product',
	                method: 'set_flag_to_get_all_records',
	                args: [parseInt(id)],
	                kwargs: {},
	            })
			}
			
	    },
});