/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { useAutofocus } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { parseFloat } from "@web/views/fields/parsers";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { Component, useState } from "@odoo/owl";
import { deserializeDateTime, formatDateTime, parseDateTime } from "@web/core/l10n/dates";
import { Order } from "@point_of_sale/app/store/models";
const { DateTime } = luxon;


patch(TicketScreen.prototype, {
  getNumpadButtons() {
    if (this._state.ui.filter == "APPOINTMENT") {
      return [
          { value: "1" },
          { value: "2" , disabled: true},
          { value: "3" , disabled: true},
          { value: "quantity", text: _t("Qty"), class: "active border-primary", disabled: true },
          { value: "4" , disabled: true},
          { value: "5" , disabled: true},
          { value: "6" , disabled: true},
          { value: "discount", text: _t("% Disc"), disabled: true },
          { value: "7" , disabled: true},
          { value: "8" , disabled: true},
          { value: "9" , disabled: true},
          { value: "price", text: _t("Price"), disabled: true },
          { value: "-", text: "+/-", disabled: true },
          { value: "0" , disabled: true},
          { value: this.env.services.localization.decimalPoint , disabled: true},
          { value: "Backspace", text: "⌫" },
      ];
    }
    return super.getNumpadButtons(...arguments);
  },

  _getFilterOptions() {
      const orderStates = super._getFilterOptions(...arguments);
      orderStates.set("APPOINTMENT", { text: _t("Appointment") });
      return orderStates;
  },

  async onFilterSelected(selectedFilter) {
      super.onFilterSelected(...arguments);

      if (this._state.ui.filter == "APPOINTMENT") {
          await this._fetchAppointmentOrders();
      }
  },

  async onSearch(search) {
    super.onSearch(...arguments);
      if (this._state.ui.filter == "APPOINTMENT") {
          this._state.syncedOrders.currentPage = 1;
          await this._fetchAppointmentOrders();
      }
  },
  getFilteredOrderList() {
      if (this._state.ui.filter == "APPOINTMENT") {
          return this._state.syncedOrders.toShow;
      }
      return super.getFilteredOrderList(...arguments)

  },

  async _fetchAppointmentOrders() {
      const domain = this._computeSyncedOrdersDomain();
      const limit = this._state.syncedOrders.nPerPage;
      const offset =
          (this._state.syncedOrders.currentPage - 1) * this._state.syncedOrders.nPerPage;
      const config_id = this.pos.config.id;
      const { ordersInfo, totalCount } = await this.orm.call(
          "pos.order",
          "search_appointment_order_ids",
          [],
          { config_id, domain, limit, offset }
      );
      const idsNotInCache = ordersInfo.filter(
          (orderInfo) => !(orderInfo[0] in this._state.syncedOrders.cache)
      );
      // If no cacheDate, then assume reasonable earlier date.
      const cacheDate = this._state.syncedOrders.cacheDate || DateTime.fromMillis(0);
      const idsNotUpToDate = ordersInfo.filter((orderInfo) => {
          return deserializeDateTime(orderInfo[1]) > cacheDate;
      });
      const idsToLoad = idsNotInCache.concat(idsNotUpToDate).map((info) => info[0]);
      if (idsToLoad.length > 0) {
          const fetchedOrders = await this.orm.call("pos.order", "export_appointment_for_ui", [idsToLoad]);
          // Check for missing products and partners and load them in the PoS
          await this.pos._loadMissingProducts(fetchedOrders);
          await this.pos._loadMissingPartners(fetchedOrders);
          // Cache these fetched orders so that next time, no need to fetch
          // them again, unless invalidated. See `_onInvoiceOrder`.
          fetchedOrders.forEach((order) => {
              this._state.syncedOrders.cache[order.id] = new Order(
                  { env: this.env },
                  { pos: this.pos, json: order }
              );
          });
          //Update the datetime indicator of the cache refresh
          this._state.syncedOrders.cacheDate = DateTime.local();
      }

      const ids = ordersInfo.map((info) => info[0]);
      this._state.syncedOrders.totalCount = totalCount;
      this._state.syncedOrders.toShow = ids.map((id) => this._state.syncedOrders.cache[id]);
  },
  async addAdditionalRefundInfo(order, destinationOrder) {
      const serviceLines = order.orderlines.filter(line => line.appointment_id);
      for (var i = 0; i < destinationOrder.orderlines.length; i++) {
        var line = destinationOrder.orderlines[i];
        var service = serviceLines.filter(l => l.id == line.refunded_orderline_id)
        if (service) {
          line.appointment_id = service[0].appointment_id;
          line.is_appointment_line = true;
          destinationOrder.set_screen_data({ name: "PaymentScreen" });
        }
      }
      return super.addAdditionalRefundInfo(...arguments);
  },
    async onDoRefund() {
      super.onDoRefund(...arguments);
    },

});

// patch(TicketScreen, {
//     components: { ...TicketScreen.components, AppointmentAddRefundButton,AppointmentRemoveRefundButton },
// });
