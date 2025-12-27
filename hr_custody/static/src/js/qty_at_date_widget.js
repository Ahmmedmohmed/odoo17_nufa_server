odoo.define("hr_custody.QtyAtDateWidget", function (require) {
    "use strict";

    const core = require("web.core");
    const QWeb = core.qweb;

    const Context = require("web.Context");
    const data_manager = require("web.data_manager");
    const time = require("web.time");

    const QtyAtDateWidget = require("sale_stock.QtyAtDateWidget");

    QtyAtDateWidget.include({
        async _openForecastCustody(ev) {
            ev.stopPropagation();

            var action = await this._rpc({
                model: 'product.product',
                method: 'action_product_forecast_report',
                args: [[this.data.product_id.data.id]]
            });
            action.context = {
                active_model: 'product.product',
                active_id: this.data.product_id.data.id,
                warehouse: this.data.warehouse_id && this.data.warehouse_id.res_id
            };
            return this.do_action(action);
        },
        _getContent() {
            if (!this.data.custody_qty_widget) {
                return this._super();
            }

            const $content = $(QWeb.render('hr_custody.QtyDetailPopOver', { data: this.data }));
            $content.on('click', '.action_open_forecast', this._openForecastCustody.bind(this));
            return $content
        },

    });
});