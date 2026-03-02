/** @odoo-module **/

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductCard } from "@point_of_sale/app/generic_components/product_card/product_card";
import { Component, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useAutoFocusToLast } from "@point_of_sale/app/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

export class AppointmentSeviceDetails extends Component {
    static template = "appointment_management_system_pos.AppointmentSeviceDetails";
    static props = {
        class: { String, optional: true },
        onClick: { type: Function, optional: true },
        SelectedServices: { type: Object, optional: true },
        appointmentDetails: { type: Object, optional: true },
    }
    static defaultProps = {
        onClick: () => {},
        class: "",
    };


    setup() {
        super.setup();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this._id = 0;
        this.availableBranchs = []
        this.availableEmployees = []
        // this.branch_id = ''
        // this.employee_id = ''
        this.changes = useState({
            categ_id: '',
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

        this.selectedService=this.pos.appointmentDetails?this.pos.appointmentDetails['selectedService']:[];

    }
    get appointmentDetailsSelectedService() {
      if (this.pos.appointmentDetails) {
        return this.pos.appointmentDetails['selectedService'];
      }
        return false;
    }
    get appointmentDetailsSelectedServicePack() {
      if (this.pos.appointmentDetails) {
        return this.pos.appointmentDetails['selectedService'] && this.pos.appointmentDetails['isSelectedServicePack'];
      }
        return false;
    }

    onClick(ev) {
      console.log('onClick',this);
      if (ev.target.id != '') {
        this.pos.appointmentDetails['selectedService'] = parseInt(ev.target.id);
        this.availableBranchs = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableBranchs
        this.changes.branch_id = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].branch_id.toString()
        // this.availableEmployees = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableEmployees
        this.changes.employee_id = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_id.toString()

      }
      this.render();
    }

    highlight(id) {
        var highlightClass = '';
        var SelectedServiceId = this.pos.appointmentDetails['selectedService'];
        if (SelectedServiceId == id) {
          highlightClass = 'green_border';
        }
        return highlightClass;
    }

    _disabledBranch() {
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
      console.log('sdzfsdafsdfsdf',changes.syncBranchs != true);
      if (changes.syncBranchs != true ) {
        return false;
      }
      return true;
    }

    _disabledEmployee() {
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];

      if (changes.syncEmployees != true ) {
        return false;
      }
      return true;
    }

    _disabledDate() {
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];

      if (changes.syncDates != true ) {
        return false;
      }
      return true;
    }

    _disabledAvailableAppointments() {
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];

      if (changes.syncAppointments != true ) {
        return false;
      }
      return true;
    }

    onTypeChange(ev) {
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].appointment_type= ev.target.value;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].branch_id = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_id = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].date = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncBranchs = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
        this.getBranches();
        this.render();
    }
    onBranchChange(ev) {
        const branch_id = ev.target.value;
        var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];

        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].branch_id = branch_id;
        this.changes.branch_id = branch_id;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_id = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].date = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncPrices = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
        if (branch_id != '') {
          // this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].branch_id = parseInt(branch_id);
          this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].branch_name = changes['availableBranchs'][parseInt(branch_id)];
          this.getAvailableEmployees();

        }
        this.render();
    }
    onEmployeeChange(ev) {
        const employee_id = ev.target.value;
        var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_id = employee_id;
        this.changes.employee_id = employee_id;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].date = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = false;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
        if(employee_id != ''){
          // this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_id = parseInt(employee_id);
          this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].employee_name = changes['availableEmployees'][parseInt(employee_id)];
          this.getAvailableDates();

        }

        this.render();
    }

    onDateChange(ev) {
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].date= ev.target.value;
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids = '';
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
        if(this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].date != ''){
          this.getAvailableAppointments();
        }
        this.render();
    }

    onAppointmentChange(ev) {
        var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
        this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids= ev.target.value;
        if(ev.target.value != ''){
          this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_ids= changes['availableAppointments'][ev.target.value].ids;
          this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].slot_name= changes['availableAppointments'][ev.target.value].name;
        }

        this.render();
    }

    async getBranches(){
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncBranchs = false;

      const availableBranchs = await this.orm.call(
          "product.product",
          "action_get_appointment_branch",
          [changes.service_id,this.pos.appointmentDetails['isSelectedServicePack']? this.pos.appointmentDetails['service_id']:false]
      );
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncBranchs = true;
      this.availableBranchs = availableBranchs;
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableBranchs = availableBranchs;
      console.log(availableBranchs);
      this.render();
    }
    async getAvailableEmployees(){
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = false;
      const availableEmployees = await this.orm.call(
          "product.product",
          "action_get_appointment_employee",
          [changes.service_id,changes.branch_id,this.pos.appointmentDetails['isSelectedServicePack']? this.pos.appointmentDetails['service_id']:false]
      );
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncEmployees = true;
      // this.availableEmployees = availableEmployees;
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableEmployees = availableEmployees;
      console.log(availableEmployees);
      this.render();
    }
    async getAvailableDates(){
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = false;
      const availabledDates = await this.orm.call(
          "product.product",
          "action_get_appointment_date",
          [changes.service_id,changes.employee_id,this.pos.appointmentDetails['isSelectedServicePack']? this.pos.appointmentDetails['service_id']:false]
      );
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncDates = true;
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availabledDates = availabledDates;
      console.log(availabledDates);
      this.render();
    }
    async getAvailableAppointments(){
      var changes = this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']];
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = false;
      const availableAppointments = await this.orm.call(
          "product.product",
          "action_get_appointment_employee_slot",
          [changes.service_id,changes.employee_id,changes.date,changes.appointment_type,changes.branch_id,this.pos.appointmentDetails['isSelectedServicePack']? this.pos.appointmentDetails['service_id']:false]
      );
      // 1. Convert to array of [key, value] pairs
      // const entries = Object.entries(availableAppointments);
      //
      // // 2. Sort by the 'name' field in each value object
      // entries.sort((a, b) => a[1].name.localeCompare(b[1].name));

      // this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableAppointmentsSorded = entries;
      //
      // // 3. Convert back to object (optional)
      // const sortedObj = Object.fromEntries(entries);

      console.log(availableAppointments);
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].syncAppointments = true;
      this.pos.appointmentDetails['services'][this.pos.appointmentDetails['selectedService']].availableAppointments = availableAppointments;
      console.log(availableAppointments);
      this.render();
    }

}
