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
      this.appointmentDetails['services'][selectedService].syncBranchs = false;
      const availableBranchs = await this.orm.call(
          "product.product",
          "action_get_appointment_branch",
          [selectedService,this.appointmentDetails['isSelectedServicePack']? this.appointmentDetails['service_id']:false]
      );
      this.appointmentDetails['services'][selectedService].syncBranchs = true;

      // -- فلترة على فرع نقطة البيع (pos.config) الحالية فقط --
      const currentConfigId = this.config ? String(this.config.id) : null;

      let filteredBranches = {};
      if (currentConfigId && availableBranchs[currentConfigId] !== undefined) {
          filteredBranches[currentConfigId] = availableBranchs[currentConfigId];
      } else {
          filteredBranches = availableBranchs; // fallback احتياطي فقط لو مفيش تطابق
      }

      this.appointmentDetails['services'][selectedService].availableBranchs = filteredBranches;

      if (Object.keys(filteredBranches).length > 0) {
          const onlyBranchId = Object.keys(filteredBranches)[0];
          this.appointmentDetails['services'][selectedService].branch_id = onlyBranchId;

          // 🚀 نكمل أوتوماتيك: الموظف + التاريخ + المواعيد من غير أي تفاعل من الكاشير
          await this.autoSelectEmployeeAndDate(selectedService);
      }
    },

    // البحث الذكي عن الموظف اللي عنده حجوزات "اليوم" - بيشتغل من ساعة إضافة الخدمة مباشرة
    async autoSelectEmployeeAndDate(selectedService) {
      const changes = this.appointmentDetails['services'][selectedService];
      changes.syncEmployees = false;

      const availableEmployees = await this.orm.call(
          "product.product",
          "action_get_appointment_employee",
          [changes.service_id, changes.branch_id, this.appointmentDetails['isSelectedServicePack']? this.appointmentDetails['service_id']:false]
      );
      changes.syncEmployees = true;
      changes.availableEmployees = availableEmployees;

      if (!availableEmployees || Object.keys(availableEmployees).length === 0) {
          return;
      }

      const empIds = Object.keys(availableEmployees);

      const today = new Date();
      const yyyy = today.getFullYear();
      const mm = String(today.getMonth() + 1).padStart(2, '0');
      const dd = String(today.getDate()).padStart(2, '0');
      const todayStr = `${yyyy}-${mm}-${dd}`;

      let targetEmpId = null;
      let targetDate = null;
      let targetEmpDates = null;

      let firstEmpId = empIds[0];
      let firstEmpDates = null;

      for (let empId of empIds) {
          const dates = await this.orm.call(
              "product.product",
              "action_get_appointment_date",
              [changes.service_id, empId, this.appointmentDetails['isSelectedServicePack']? this.appointmentDetails['service_id']:false]
          );

          if (empId === firstEmpId) {
              firstEmpDates = dates;
          }

          let isTodayAvail = false;
          if (Array.isArray(dates)) {
              isTodayAvail = dates.includes(todayStr);
          } else if (dates && typeof dates === 'object') {
              isTodayAvail = Object.keys(dates).includes(todayStr) || Object.values(dates).includes(todayStr);
          } else if (typeof dates === 'string') {
              isTodayAvail = dates === todayStr;
          }

          if (isTodayAvail) {
              targetEmpId = empId;
              targetDate = todayStr;
              targetEmpDates = dates;
              break;
          }
      }

      if (!targetEmpId) {
          targetEmpId = firstEmpId;
          targetEmpDates = firstEmpDates;

          if (Array.isArray(firstEmpDates) && firstEmpDates.length > 0) {
              targetDate = firstEmpDates[0];
          } else if (firstEmpDates && typeof firstEmpDates === 'object' && Object.keys(firstEmpDates).length > 0) {
              targetDate = Object.values(firstEmpDates)[0];
          }
      }

      changes.employee_id = targetEmpId;
      changes.syncDates = true;
      changes.availabledDates = targetEmpDates;

      if (targetDate) {
          changes.date = targetDate;
          await this.autoSelectAppointmentSlot(selectedService);
      }
    },

    async autoSelectAppointmentSlot(selectedService) {
      const changes = this.appointmentDetails['services'][selectedService];
      changes.syncAppointments = false;
      const availableAppointments = await this.orm.call(
          "product.product",
          "action_get_appointment_employee_slot",
          [changes.service_id, changes.employee_id, changes.date, changes.appointment_type, changes.branch_id, this.appointmentDetails['isSelectedServicePack']? this.appointmentDetails['service_id']:false]
      );
      changes.syncAppointments = true;
      changes.availableAppointments = availableAppointments;
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