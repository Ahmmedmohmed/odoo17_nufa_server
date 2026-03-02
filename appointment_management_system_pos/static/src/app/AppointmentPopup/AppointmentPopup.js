/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Input } from "@point_of_sale/app/generic_components/inputs/input/input";
import { unaccent } from "@web/core/utils/strings";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { AppointmentSeviceList } from "@appointment_management_system_pos/app/AppointmentSeviceList/AppointmentSeviceList";
import { AppointmentSeviceDetails } from "@appointment_management_system_pos/app/AppointmentSeviceDetails/AppointmentSeviceDetails";
import { AppointmentSevicePackSelection } from "@appointment_management_system_pos/app/AppointmentSevicePackSelection/AppointmentSevicePackSelection";
import { CategorySelector } from "@point_of_sale/app/generic_components/category_selector/category_selector";


export class AppointmentPopup extends AbstractAwaitablePopup {
    static template = "appointment_management_system_pos.AppointmentPopup";
    static components = {
        AppointmentSeviceList,
        AppointmentSeviceDetails,
        AppointmentSevicePackSelection,
        CategorySelector,
        Input
    };

    static defaultProps = {
        confirmText: _t("Confirm"),
        cancelText: _t("Cancel"),
        confirmKey: false,
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.ui = useState(useService("ui"));
        this.popup = useService("popup");

        this.appointment_categories = [];
        for (var i = 0; i < this.pos.appointment_categories.length; i++) {
          var cat = this.pos.db.category_by_id[this.pos.appointment_categories[i].id];
          if (cat) {
            this.appointment_categories.push(cat);
          }
        }
        this.appointment_categories = this.appointment_categories.map((category) => {
            const isRootCategory = category.id === this.pos.db.root_category_id;
            const showSeparator =
                !isRootCategory &&
                [
                    ...this.pos.db.get_category_ancestors_ids(this.pos.selectedCategoryId),
                    this.pos.selectedCategoryId,
                ].includes(category.id);
            return {
                id: category.id,
                name: !isRootCategory ? category.name : "",
                icon: isRootCategory ? "fa-home fa-2x" : "",
                separator: "fa-caret-right",
                showSeparator,
                imageUrl:
                    category?.has_image &&
                    `/web/image?model=pos.category&field=image_128&id=${category.id}&unique=${category.write_date}`,
            };
        })
        if (this.appointment_categories.length > 0 && !this.pos.SelectedCategoryId) {
            this.pos.SelectedCategoryId = this.appointment_categories[0].id;
        }
        this.appointment_services = this.pos.appointment_services;
        this.state = useState({ searchWord: ''});

    }
    get appointmentDetailsSelectedService() {
      if (this.pos.appointmentDetails) {
        return this.pos.appointmentDetails['selectedService'];

      }
        return false;
    }
    get SelectedCategoryId() {
        return this.pos.SelectedCategoryId;
    }
    get isSelectedServicePack() {
        return this.pos.isSelectedServicePack;
    }
    get searchWord() {
        return this.state.searchWord.trim();
    }
    get CategoryActive() {
        if(this.SelectedCategoryId == this.categ.id){
            return 'active';
        }
        return '';
    }
    switchCategory(categId) {
        this.pos.SelectedCategoryId = categId;
        this.pos.SelectedService = null;
        if (this.pos.appointmentDetails) {
          this.pos.appointmentDetails['selectedService'] = null;
          this.pos.appointmentDetails['services'] = null;
        }
        this.render();
    }

    search_product(product) {
        const { db } = this.pos;
        var query = this.searchWord;
        try {
            // eslint-disable-next-line no-useless-escape
            query = query.replace(/[\[\]\(\)\+\*\?\.\-\!\&\^\$\|\~\_\{\}\:\,\\\/]/g, ".");
            query = query.replace(/ /g, ".+");
            var re = RegExp("([0-9]+):.*?" + unaccent(query), "gi");
        } catch {
            return [];
        }
        var r = re.exec(db._product_search_string(product));
        if(r){
            return true;
        }
        return false;
    }

    getShowCategoryImages() {
        return (
            this.pos.show_category_images &&
            Object.values(this.pos.db.category_by_id).some((category) => category.has_image) &&
            !this.ui.isSmall
        );
    }

    get productsToDisplay() {
        const { db } = this.pos;
        let list = [];
        if (this.searchWord !== "") {
            list = db.search_product_in_category(this.SelectedCategoryId, this.searchWord);
            list = list.filter((product) => product.is_appointment_service);
        } else {
            var categId = this.SelectedCategoryId;
            list = Object.values(db.product_by_id).filter((product) => {
                if (!product.is_appointment_service || !product.active || !product.available_in_pos) {
                    return false;
                }
                if (categId && categId !== 0) {
                    return product.pos_categ_ids && product.pos_categ_ids.includes(categId);
                }
                return true;
            });
        }
        return list.sort(function (a, b) {
            return a.display_name.localeCompare(b.display_name);
        });
    }


    selectedServicePack(ev){
      this.pos.appointmentDetails['selectedService'] =ev.target.id;
      this.render();
    }


    async addProduct(product){
      this.pos.appointmentDetails = {};
      this.pos.SelectedService = product;
      this.pos.SelectedServices = [];
      this.pos.isSelectedServicePack = product && product.appointment_package_line_ids.length>0;
      this.pos.appointmentDetails['services'] = {}
      this.pos.appointmentDetails['service_id'] = product.id
      if (product ) {
        if (this.pos.isSelectedServicePack) {
          this.pos.appointmentDetails['isSelectedServicePack'] =true;
          this.pos.appointmentDetails['ServicePackFullName'] =product.display_name;
          for (var i = 0; i < product.appointment_package_line_ids.length; i++) {
            var product_id = this.pos.appointment_package_by_id[product.appointment_package_line_ids[i]]['product_id'][0];
            var prod = this.pos.db.get_product_by_id(product_id);
            this.pos.SelectedServices.push(prod);
            var obj = {
              'service_id':product_id,
              'branch_id': '',
              'employee_id': '',
              'date': '',
              'price': 0,
              'appointment_type': 'inside',
              'slot_ids': '',
              'appointment_id': false,
              'availableBranchs':[],
              'availableAppointments':[],
              'availableAppointmentsSorded':[],
              'availabledDates':[],
              'availableEmployees':[],
            }
            this.pos.appointmentDetails['services'][product_id] = obj
            await this.pos.getBranches(product_id);
          }
          this.pos.appointmentDetails['selectedService'] =this.pos.appointment_package_by_id[product.appointment_package_line_ids[0]]['product_id'][0];

        }else {
          this.pos.SelectedServices.push(product);
          var obj = {
            'service_id':product.id,
            'branch_id': '',
            'employee_id': '',
            'date': '',
            'price': 0,
            'appointment_type': 'inside',
            'slot_ids': '',
            'appointment_id': false,
            'availableBranchs':[],
            'availableAppointments':[],
            'availableAppointmentsSorded':[],
            'availabledDates':[],
            'availableEmployees':[],
          }
          this.pos.appointmentDetails['services'][product.id] = obj
          await this.pos.getBranches(product.id);
          this.pos.appointmentDetails['selectedService'] = product.id;
          this.pos.appointmentDetails['isSelectedServicePack'] =false;
        }


      }

      this.render();

    }

    removeProduct(product) {
      this.pos.SelectedService = null;
      this.pos.appointmentDetails['selectedService'] = null;
      this.pos.appointmentDetails['services'] = null;
      this.render();
    }

    async confirm() {
      var flag = true;
      if (this.pos.appointmentDetails['services']) {
        for (const [key, value] of Object.entries(this.pos.appointmentDetails['services'])) {
          console.log(key,value);
          if (
            value.service_id == ''||
            value.employee_id == ''||
            value.date == ''||
            value.slot_ids == ''
          ) {
            flag= false;
          }
        }
      }else {
        flag= false;
      }




      if (!flag) {
        this.popup.add(ErrorPopup, {
            title: _t("Missing Fields."),
            body: _t("Missing Data."),
        });
      }else {
        console.log('kljlkj');
        await this.createAppointments();
        super.confirm();
      }
    }

    async createAppointments(){
      var appointmentDetails = this.pos.appointmentDetails;
      var partner_id = false;
      if (this.pos.get_order().get_partner()) {
        partner_id = this.pos.get_order().get_partner().id;
      }
      const createAppointment = await this.orm.call("product.product", "action_create_appointments", [appointmentDetails['service_id'],partner_id,appointmentDetails]);
      this.pos.appointmentDetails = createAppointment;
      this.render();
    }

		/**
		 * @override
		 */
		async getPayload() {
      return this.pos.appointmentDetails;
		}
    cancel() {
        super.cancel();
        this.pos.SelectedService = null;
        if (this.pos.appointmentDetails) {
          this.pos.appointmentDetails['selectedService'] = null;
          this.pos.appointmentDetails['services'] = null;
        }

    }
}
