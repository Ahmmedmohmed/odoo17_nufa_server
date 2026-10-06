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
import { localization } from "@web/core/l10n/localization";

// ─── Translation map ───────────────────────────────────────────────────────────
const TRANSLATIONS = {
    ar: {
        type:             'نوع الخدمة',
        branch:           'الفرع',
        employee:         'الموظف / الأخصائية',
        date:             'التاريخ',
        appointments:     'المواعيد المتاحة',
        none:             'لا يوجد',
        internalServices: 'خدمات داخلية',
        externalServices: 'خدمات خارجية',
    },
    en: {
        type:             'Type',
        branch:           'Branch',
        employee:         'Employee',
        date:             'Date',
        appointments:     'Appointments',
        none:             'None',
        internalServices: 'Internal Services',
        externalServices: 'External Services',
    },
};

function getLang() {
    if (localization.direction === 'rtl') {
        return 'ar';
    }
    const lang = (localization.lang || 'en').split(/[-_]/)[0].toLowerCase();
    return TRANSLATIONS[lang] ? lang : 'en';
}

function t(key) {
    return TRANSLATIONS[getLang()][key] || TRANSLATIONS['en'][key] || key;
}

// تاريخ اليوم بصيغة YYYY-MM-DD
function todayString() {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
}

// هل التاريخ المطلوب موجود جوه نتيجة السيرفر (list / object / string)؟
function datesInclude(dates, dateStr) {
    if (Array.isArray(dates)) {
        return dates.includes(dateStr);
    } else if (dates && typeof dates === 'object') {
        return Object.keys(dates).includes(dateStr) || Object.values(dates).includes(dateStr);
    } else if (typeof dates === 'string') {
        return dates === dateStr;
    }
    return false;
}

// أول تاريخ متاح من نتيجة السيرفر
function firstDateOf(dates) {
    if (Array.isArray(dates) && dates.length > 0) {
        return dates[0];
    } else if (dates && typeof dates === 'object' && Object.keys(dates).length > 0) {
        return Object.values(dates)[0];
    }
    return null;
}
// ──────────────────────────────────────────────────────────────────────────────

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

    // ─── Translation getters ───────────────────────────────────────────────────
    get labelType()             { return t('type'); }
    get labelBranch()           { return t('branch'); }
    get labelEmployee()         { return t('employee'); }
    get labelDate()             { return t('date'); }
    get labelAppointments()     { return t('appointments'); }
    get labelNone()             { return t('none'); }
    get labelInternalServices() { return t('internalServices'); }
    get labelExternalServices() { return t('externalServices'); }
    // ──────────────────────────────────────────────────────────────────────────

    setup() {
        super.setup();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.pos = usePos();
        this._id = 0;
        this.availableBranchs = []
        this.availableEmployees = []
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
        this.t = t;
        this.popup = useService("popup");
    }

    // ─── الخدمة المختارة حالياً (آمنة: ترجع null لو مش موجودة) ──────────────────
    get currentService() {
        const d = this.pos.appointmentDetails;
        if (!d || !d.services) {
            return null;
        }
        const id = d['selectedService'];
        if (id === null || id === undefined || id === '') {
            return null;
        }
        return d.services[id] || null;
    }

    // الشرط اللي بيظهر بيانات الخدمة: لازم الخدمة تكون موجودة فعلاً جوه services
    get appointmentDetailsSelectedService() {
        if (this.currentService) {
            return this.pos.appointmentDetails['selectedService'];
        }
        return false;
    }

    get appointmentDetailsSelectedServicePack() {
      const d = this.pos.appointmentDetails;
      if (d && d.services) {
        return d['selectedService'] && d['isSelectedServicePack'];
      }
        return false;
    }

    onClick(ev) {
      const d = this.pos.appointmentDetails;
      const id = parseInt(ev.target.id);
      if (d && d.services && d.services[id]) {
        d['selectedService'] = id;
        const svc = d.services[id];
        this.availableBranchs = svc.availableBranchs;
        this.changes.branch_id = String(svc.branch_id ?? '');
        this.changes.employee_id = String(svc.employee_id ?? '');
      }
      this.render();
    }

    highlight(id) {
        var highlightClass = '';
        var SelectedServiceId = this.pos.appointmentDetails?.['selectedService'];
        if (SelectedServiceId == id) {
          highlightClass = 'green_border';
        }
        return highlightClass;
    }

    _disabledBranch() {
      const s = this.currentService;
      return !!s && s.syncBranchs === true;
    }

    _disabledEmployee() {
      const s = this.currentService;
      return !!s && s.syncEmployees === true;
    }

    _disabledDate() {
      const s = this.currentService;
      return !!s && s.syncDates === true;
    }

    _disabledAvailableAppointments() {
      const s = this.currentService;
      return !!s && s.syncAppointments === true;
    }

    onTypeChange(ev) {
        const s = this.currentService;
        if (!s) { return; }
        s.appointment_type = ev.target.value;
        s.branch_id = '';
        s.employee_id = '';
        s.date = '';
        s.slot_ids = '';
        s.syncBranchs = false;
        s.syncEmployees = false;
        s.syncDates = false;
        s.syncAppointments = false;
        this.getBranches();
        this.render();
    }

    onBranchChange(ev) {
        const s = this.currentService;
        if (!s) { return; }
        const branch_id = ev.target.value;
        s.branch_id = branch_id;
        this.changes.branch_id = branch_id;
        s.employee_id = '';
        s.date = '';
        s.slot_ids = '';
        s.syncPrices = false;
        s.syncEmployees = false;
        s.syncDates = false;
        s.syncAppointments = false;
        if (branch_id != '') {
          s.branch_name = s['availableBranchs'][parseInt(branch_id)];
          this.getAvailableEmployees(s);
        }
        this.render();
    }

    onEmployeeChange(ev) {
        const s = this.currentService;
        if (!s) { return; }
        const employee_id = ev.target.value;
        s.employee_id = employee_id;
        this.changes.employee_id = employee_id;
        s.date = '';
        s.slot_ids = '';
        s.syncDates = false;
        s.syncAppointments = false;
        if(employee_id != ''){
          s.employee_name = s['availableEmployees'][parseInt(employee_id)];
          // لو الموظف اتغير يدوياً، نستدعي التواريخ الخاصة بيه
          this.getAvailableDates(s);
        }
        this.render();
    }

    onDateChange(ev) {
        const s = this.currentService;
        if (!s) { return; }
        s.date = ev.target.value;
        s.slot_ids = '';
        s.syncAppointments = false;
        if(s.date != ''){
          this.getAvailableAppointments(s);
        }
        this.render();
    }

    onAppointmentChange(ev) {
        const s = this.currentService;
        if (!s) { return; }
        s.slot_ids = ev.target.value;
        if(ev.target.value != ''){
          s.slot_ids = s['availableAppointments'][ev.target.value].ids;
          s.slot_name = s['availableAppointments'][ev.target.value].name;
        }
        this.render();
    }

    _packServiceId() {
        const d = this.pos.appointmentDetails;
        return d && d['isSelectedServicePack'] ? d['service_id'] : false;
    }

    // 1️⃣ فلترة وقفل الفروع على فرع نقطة البيع (pos.config) الحالية فقط
    async getBranches(service = this.currentService){
      const s = service;
      if (!s) { return; }
      s.syncBranchs = false;

      const availableBranchs = await this.orm.call(
          "product.product",
          "action_get_appointment_branch",
          [s.service_id, this._packServiceId()]
      );
      s.syncBranchs = true;

      // فرع نقطة البيع الحالية (اللي شغال عليها الكاشير)
      const currentConfigId = this.pos.config ? String(this.pos.config.id) : null;

      let filteredBranches = {};
      if (currentConfigId && availableBranchs[currentConfigId] !== undefined) {
          filteredBranches[currentConfigId] = availableBranchs[currentConfigId];
      } else {
          filteredBranches = availableBranchs; // fallback احتياطي فقط لو مفيش تطابق
      }

      this.availableBranchs = filteredBranches;
      s.availableBranchs = filteredBranches;

      if (Object.keys(filteredBranches).length > 0) {
          const onlyBranchId = Object.keys(filteredBranches)[0];
          s.branch_id = onlyBranchId;
          this.changes.branch_id = onlyBranchId;
          await this.getAvailableEmployees(s);
      }

      this.render();
    }

    // 2️⃣ البحث الذكي عن الموظف اللي عنده حجوزات "اليوم"
    async getAvailableEmployees(service = this.currentService){
      const s = service;
      if (!s) { return; }
      s.syncEmployees = false;
      const availableEmployees = await this.orm.call(
          "product.product",
          "action_get_appointment_employee",
          [s.service_id, s.branch_id, this._packServiceId()]
      );
      s.syncEmployees = true;
      s.availableEmployees = availableEmployees;

      // -- بدء عملية البحث الذكي --
      if (availableEmployees && Object.keys(availableEmployees).length > 0) {
          const empIds = Object.keys(availableEmployees);
          const todayStr = todayString();

          let targetEmpId = null;
          let targetDate = null;
          let targetEmpDates = null;

          let firstEmpId = empIds[0];
          let firstEmpDates = null;

          // البحث في كل الموظفين عن من لديه موعد اليوم
          for (let empId of empIds) {
              const dates = await this.orm.call(
                  "product.product",
                  "action_get_appointment_date",
                  [s.service_id, empId, this._packServiceId()]
              );

              if (empId === firstEmpId) {
                  firstEmpDates = dates; // نحتفظ ببيانات أول موظف احتياطياً
              }

              if (datesInclude(dates, todayStr)) {
                  targetEmpId = empId;
                  targetDate = todayStr;
                  targetEmpDates = dates;
                  break; // وجدنا الموظف المناسب! نوقف حلقة البحث
              }
          }

          // لو لم نجد أحداً متاحاً اليوم، نختار أول موظف وأول تاريخ له
          if (!targetEmpId) {
              targetEmpId = firstEmpId;
              targetEmpDates = firstEmpDates;
              targetDate = firstDateOf(firstEmpDates);
          }

          // -- تعبئة البيانات وتفعيل الاختيارات في الشاشة --
          s.employee_id = targetEmpId;
          this.changes.employee_id = targetEmpId;

          s.syncDates = true;
          s.availabledDates = targetEmpDates;

          if (targetDate) {
              s.date = targetDate;
              await this.getAvailableAppointments(s);
          }
      }

      this.render();
    }

    // 3️⃣ تعمل كبديل احتياطي لو قام الكاشير بتغيير الموظف يدوياً من القائمة
    async getAvailableDates(service = this.currentService){
      const s = service;
      if (!s) { return; }
      s.syncDates = false;

      const availabledDates = await this.orm.call(
          "product.product",
          "action_get_appointment_date",
          [s.service_id, s.employee_id, this._packServiceId()]
      );

      s.syncDates = true;
      s.availabledDates = availabledDates;

      const todayStr = todayString();

      if (datesInclude(availabledDates, todayStr)) {
          s.date = todayStr;
          await this.getAvailableAppointments(s);
      } else if (availabledDates) {
          const firstDate = firstDateOf(availabledDates);
          if (firstDate) {
              s.date = firstDate;
              await this.getAvailableAppointments(s);
          }
      }

      this.render();
    }

    async getAvailableAppointments(service = this.currentService){
      const s = service;
      if (!s) { return; }
      s.syncAppointments = false;
      const availableAppointments = await this.orm.call(
          "product.product",
          "action_get_appointment_employee_slot",
          [s.service_id, s.employee_id, s.date, s.appointment_type, s.branch_id, this._packServiceId()]
      );
      s.syncAppointments = true;
      s.availableAppointments = availableAppointments;
      this.render();
    }
}