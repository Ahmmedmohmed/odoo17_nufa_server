/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useAutoFocusToLast } from "@point_of_sale/app/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
// import { EditListInput } from "@point_of_sale/app/store/select_lot_popup/edit_list_input/edit_list_input";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class AppointmentPopup extends AbstractAwaitablePopup {
    static components = {};
    static template = "appointment_management_system_pos.AppointmentPopup";
    static defaultProps = {
        confirmText: _t("Add"),
        cancelText: _t("Discard"),
        array: [],
        isSingleItem: false,
    };

    /**
     * @param {String} title required title of popup
     * @param {Array} [props.array=[]] the array of { id, text } to be edited or an array of strings
     * @param {Boolean} [props.isSingleItem=false] true if only allowed to edit single item (the first item)
     */
    setup() {
        super.setup();
				this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this._id = 0;
        this.employee_appointment = [];

        this.appointment_services = this.pos.appointment_services;
        this.appointment_service_price_plans_by_product_id = this.pos.appointment_service_price_plans_by_product_id;
        this.availableBranchs=[];
        this.availableEmployees=[];
        this.availabledDates=[];
        this.availableAppointments=[];
        this.changes = useState({
            branch_id: '',
            employee_id: '',
            service_id: '',
            date: '',
            price: 0,
            appointment_type: 'inside',
            appointment: '',
            appointment_id: false,
            syncBranchs: false,
            syncEmployees: false,
            syncPrices: false,
            syncDates: false,
            syncAppointments: false,
        });
    }
    _disabledBranch() {
      if (this.changes.syncBranchs === false ) {
        return true;
      }
        return false;
    }
    _disabledEmployee() {
      if (this.changes.syncEmployees === false ) {
        return true;
      }
        return false;
    }
    _disabledDate() {
      if (this.changes.syncDates === false ) {
        return true;
      }
        return false;
    }
    // _disabledType() {
    //   if (this.changes.syncPrices === false ) {
    //     return true;
    //   }
    //     return false;
    // }
    _disabledAvailableAppointments() {
      if (this.changes.syncAppointments === false ) {
        return true;
      }
        return false;
    }
    onServiceChange(ev) {
      console.log('onServiceChange');
        const service_id = ev.target.value;
        this.changes.service_id = service_id;
        this.changes.branch_id = '';
        this.changes.employee_id = '';
        this.changes.date = '';
        this.changes.appointment = '';
        this.changes.syncBranchs = false;
        this.changes.syncPrices = false;
        this.changes.syncEmployees = false;
        this.changes.syncDates = false;
        this.changes.syncAppointments = false;
        if (service_id != '') {
          // this.employee_appointment = this.appointment_service_price_plans_by_product_id[service_id];
          this.getBranches();
        }else {
          this.changes.branch_id= '';
          this.changes.appointment_type= 'inside';
          this.changes.employee_id= '';
          this.changes.date= '';
          this.changes.appointment= '';
        }
        this.render();
    }
    onBranchChange(ev) {
      console.log('onBranchChange');
        const branch_id = ev.target.value;
        this.changes.branch_id = branch_id;
        this.changes.employee_id = '';
        this.changes.date = '';
        this.changes.appointment = '';
        this.changes.syncPrices = false;
        this.changes.syncEmployees = false;
        this.changes.syncDates = false;
        this.changes.syncAppointments = false;
        if (branch_id != '') {
          // this.employee_appointment = this.appointment_service_price_plans_by_product_id[service_id];
          this.getAvailableEmployees();
        }else {
          this.changes.employee_id= '';
          this.changes.date= '';
          this.changes.appointment_type= 'inside';
          this.changes.appointment= '';
        }
        this.render();
    }
    onEmployeeChange(ev) {
      console.log('onEmployeeChange');
        const employee_id = ev.target.value;
        this.changes.employee_id = employee_id;
        this.changes.date = '';
        this.changes.appointment = '';
        this.changes.syncDates = false;
        this.changes.syncAppointments = false;
        if(this.changes.employee_id != ''){
          this.getAvailableDates();
        }else {
          this.changes.date= '';
          this.changes.appointment= '';
        }

        this.render();
    }
    onTypeChange(ev) {
      console.log('onTypeChange');
        this.changes.appointment_type= ev.target.value;
        this.render();
    }
    onDateChange(ev) {
      console.log('onDateChange');
        this.changes.date= ev.target.value;
        this.changes.appointment = '';
        this.changes.syncAppointments = false;
        if(this.changes.date != ''){
          this.getAvailableAppointments();
        }else {
          this.changes.appointment= '';
        }
        this.render();
    }
    onAppointmentChange(ev) {
        console.log('onAppointmentChange');
        this.changes.appointment= ev.target.value;

        this.render();
    }
    async getBranches(){
      this.changes.syncBranchs = false;
      const availableBranchs = await this.orm.call(
          "product.product",
          "action_get_appointment_branch",
          [parseInt(this.changes.service_id)]
      );
      this.changes.syncBranchs = true;
      this.availableBranchs = availableBranchs;
      console.log(availableBranchs);
      this.render();
    }
    async getAvailableEmployees(){
      this.changes.syncEmployees = false;
      const availableEmployees = await this.orm.call(
          "product.product",
          "action_get_appointment_employee",
          [parseInt(this.changes.service_id),parseInt(this.changes.branch_id)]
      );
      this.changes.syncEmployees = true;
      this.availableEmployees = availableEmployees;
      console.log(availableEmployees);
      this.render();
    }
    async getAvailableDates(){
      this.changes.syncDates = false;
      const availabledDates = await this.orm.call(
          "product.product",
          "action_get_appointment_date",
          [parseInt(this.changes.service_id),parseInt(this.changes.employee_id)]
      );
      this.changes.syncDates = true;
      this.availabledDates = availabledDates;
      console.log(availabledDates);
      this.render();
    }
    async getPrice(){
      this.changes.syncPrices = false;
      const prices = await this.orm.call(
          "product.product",
          "action_get_appointment_service_price",
          [parseInt(this.changes.service_id),this.changes.branch_id,this.changes.employee_id,this.changes.appointment_type]
      );
      this.changes.syncPrices = true;
      this.prcie = prices;
      console.log(prices);
      this.render();
    }
    async getAvailableAppointments(){
      this.changes.syncAppointments = false;
      const availableAppointments = await this.orm.call(
          "product.product",
          "action_get_appointment_employee_slot",
          [parseInt(this.changes.service_id),parseInt(this.changes.employee_id),this.changes.date]
      );
      this.changes.syncAppointments = true;
      this.availableAppointments = availableAppointments;
      console.log(availableAppointments);
      this.render();
    }
    async createAppointment(){
      var partner_id = false;
      if (this.pos.get_order().get_partner()) {
        partner_id = this.pos.get_order().get_partner().id;
      }
      const createAppointment = await this.orm.call(
          "product.product",
          "action_create_appointment",
          [parseInt(this.changes.service_id),partner_id,parseInt(this.changes.branch_id),parseInt(this.changes.employee_id),this.changes.date,this.changes.appointment_type,parseInt(this.changes.appointment)]
      );
      this.changes.appointment_id = createAppointment.id;
      this.changes.price = createAppointment.price;
      console.log(createAppointment);
      this.render();
    }


    async confirm() {
      if (
        this.changes.service_id == ''||
        this.changes.employee_id == ''||
        this.changes.date == ''||
        this.changes.appointment == ''
      ) {
        this.popup.add(ErrorPopup, {
            title: _t("Missing Fields."),
            body: _t("Missing Data."),
        });
      }else {
        await this.createAppointment();
        super.confirm();
      }
    }

		/**
		 * @override
		 */
		async getPayload() {
      return this.changes;
		}


}
