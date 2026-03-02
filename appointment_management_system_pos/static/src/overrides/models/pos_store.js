/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    // async setup() {
    //     await super.setup(...arguments);
    //     if (this.config.module_pos_hr) {
    //         if (!this.hasLoggedIn) {
    //             this.showTempScreen("LoginScreen");
    //         }
    //     }
    // },
    async _processData(loadedData) {
        await super._processData(...arguments);
        if (this.config.allow_appointment) {
          this.appointment_categories = loadedData["appointment.product.category"];
          this.appointment_services = loadedData["appointment.product.service"]['appointment_services'];
          this.appointment_services_by_categ_id = loadedData["appointment.product.service"]['appointment_services_by_categ_id'];
          this.appointment_package_by_id = loadedData["appointment.package.line"]['appointment_package_by_id'];
          // this.appointment_services = loadedData["appointment.service.price.plan"]['appointment_services'];
          // this.appointment_service_price_plans = loadedData["appointment.service.price.plan"]['appointment_service_price_plans'];
          // this.appointment_service_price_plans_by_product_id = loadedData["appointment.service.price.plan"]['appointment_service_price_plans_by_product_id'];
          //
          // this.employee_appointment = loadedData["hr.employee.appointment"]['employee_appointment'];
          // this.employee_appointment_by_id = loadedData["hr.employee.appointment"]['employee_appointment_by_id'];
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
      console.log(availableBranchs);
      // this.render();
    },
    // async getAvailableEmployees(selectedService){
    //   var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = false;
    //   const availableEmployees = await this.orm.call(
    //       "product.product",
    //       "action_get_appointment_employee",
    //       [changes.service_id,changes.branch_id]
    //   );
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = true;
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableEmployees = availableEmployees;
    //   console.log(availableEmployees);
    //   this.render();
    // },
    // async getAvailableDates(selectedService){
    //   var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = false;
    //   const availabledDates = await this.orm.call(
    //       "product.product",
    //       "action_get_appointment_date",
    //       [changes.service_id,changes.employee_id]
    //   );
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = true;
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availabledDates = availabledDates;
    //   console.log(availabledDates);
    //   this.render();
    // },
    // async getAvailableAppointments(selectedService){
    //   var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
    //   const availableAppointments = await this.orm.call(
    //       "product.product",
    //       "action_get_appointment_employee_slot",
    //       [changes.service_id,changes.employee_id,changes.date,changes.appointment_type,changes.branch_id]
    //   );
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = true;
    //   this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableAppointments = availableAppointments;
    //   console.log(availableAppointments);
    //   this.render();
    // }

});
