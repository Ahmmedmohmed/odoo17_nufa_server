/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        if (this.config.allow_appointment) {
          this.appointment_categories = loadedData["appointment.product.category"];
          this.appointment_services = loadedData["appointment.product.service"]['appointment_services'];
          this.appointment_services_by_categ_id = loadedData["appointment.product.service"]['appointment_services_by_categ_id'];
          this.appointment_package_by_id = loadedData["appointment.package.line"]['appointment_package_by_id'];
        }
    },

    async getBranches(selectedService){
      var changes = this.appointmentDetails['services'][selectedService];
      this.appointmentDetails['services'][selectedService].syncBranchs = false;
      const availableBranchs = await this.orm.call(
          "product.product",
          "action_get_appointment_branch",
          [selectedService,this.appointmentDetails['isSelectedServicePack']? this.appointmentDetails['service_id']:false]
      );
      this.appointmentDetails['services'][selectedService].syncBranchs = true;
      this.appointmentDetails['services'][selectedService].availableBranchs = availableBranchs;
    },
});