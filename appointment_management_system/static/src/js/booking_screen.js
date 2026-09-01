/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class AppointmentBookingScreen extends Component {
    static template = "appointment_management_system.BookingScreenTemplate";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            step: 1,
            categories: [],
            services: [],
            partners: [],
            payment_methods: [],

            isPackageMode: false,
            selectedPackage: null,
            packageServices: [],
            packageSelections: [],
            currentPackageIndex: 0,

            availableBranches: [],
            availableEmployees: [],
            availableDates: [],
            availableSlots: [],

            appointment_type: 'inside',
            selectedCategory: null,
            selectedService: null,
            selectedBranch: null,
            selectedEmployee: null,
            selectedDate: '',
            selectedSlot: null,
            selectedPartner: null,
            selectedPaymentMethod: null,

            calculatedPrice: 0,
            notes: "",
            isSubmitting: false,
            confirmedRef: "",
            confirmedInvoiceId: null,
        });

        onWillStart(async () => {
            const data = await this.orm.call("appointment.management", "get_booking_initial_data", []);
            this.state.categories = data.categories || [];
            this.state.partners = data.partners || [];
            this.state.payment_methods = data.payment_methods || [];
        });
    }

    // ─── النصوص المترجمة (بالـ If الجذري) ────────────────────────────────────────────────────
    get t() {
        // فحص لغة المستخدم الحالية
        const currentLang = this.env?.services?.user?.lang || "en_US";
        const isAr = currentLang.startsWith("ar");

        if (isAr) {
            return {
                // Header
                newBookingAndPayment:       "حجز موعد جديد والدفع",
                chooseDetails:              "اختر التفاصيل لإتمام حجزك بنجاح",
                step1Label:                 "1. التصنيف",
                step2Label:                 "2. الخدمة/الباقة",
                step3Label:                 "3. التفاصيل",
                step4Label:                 "4. الدفع",

                // Step 1
                selectCategory:             "اختر التصنيف",
                showAllServicesAndPackages: "عرض كل الخدمات والباقات",

                // Step 2
                selectServiceOrPackage:     "اختر الخدمة أو الباقة",
                backToCategories:           "الرجوع للتصنيفات",
                package:                    "باقة",
                packageContents:            "محتويات الباقة",
                cancelPackageAndReturn:     "إلغاء الباقة والرجوع",
                youArePurchasingPackage:    "أنت تقوم الآن بشراء باقة:",
                packagePaymentNote:         "سيدفع العميل ثمن الباقة كاملاً الآن. يرجى اختيار الخدمة الأولى التي سيتم تنفيذها اليوم.",
                selectForTodaySession:      "اختر لجلسة اليوم",

                // Step 3
                bookingService:             "حجز خدمة",
                of:                         "من",
                serviceBookingSettings:     "إعدادات حجز الخدمة",
                back:                       "رجوع",
                bookingType:                "نوع الحجز",
                insideBranch:               "داخلي (بالفرع)",
                outsideHome:                "خارجي (منزلي)",
                availableBranch:            "الفرع المتاح",
                selectBranch:               "-- اختر الفرع --",
                availableSpecialist:        "الأخصائية المتاحة",
                selectSpecialist:           "-- اختر الأخصائية --",
                availableDatesForSpecialist:"الأيام المتاحة للأخصائية",
                selectBookingDate:          "-- اختر يوم الحجز --",
                sorryNoDates:               "عفواً، لا توجد أيام متاحة لهذه الأخصائية.",
                availableTimesSlots:        "الأوقات المتاحة",
                selectSuitableTime:         "-- اختر الوقت المناسب --",
                noAppointmentsAvailable:    "لا توجد مواعيد متاحة في هذا اليوم.",
                nextBookNextPackageService: "التالي: حجز الخدمة القادمة بالباقة",
                nextCustomerDetailsPayment: "التالي: بيانات العميل والدفع",

                // Step 4
                customerDetailsAndPayment:  "بيانات العميل والدفع",
                selectCustomer:             "اختر العميل",
                selectCustomerFromList:     "-- اختر عميلاً من القائمة --",
                noNumber:                   "بدون رقم",
                paymentMethodPOS:           "طريقة الدفع (نقاط البيع)",
                selectPaymentMethod:        "-- اختر طريقة الدفع للسداد الفوري --",
                additionalNotes:            "ملاحظات إضافية",
                confirmBookingAndInvoice:   "تأكيد الحجز وإصدار الفاتورة",

                // Step 5
                bookingConfirmedSuccess:    "تم تأكيد الحجز والدفع بنجاح!",
                bookingNumber:              "رقم الحجز: ",
                newBooking:                 "حجز جديد",
                printInvoice:               "طباعة الفاتورة",

                // Sidebar summary
                bookingSummary:             "ملخص الحجز",
                category:                   "التصنيف",
                service:                    "الخدمة",
                branch:                     "الفرع",
                specialist:                 "الأخصائية",
                dateAndTime:                "التاريخ والوقت",
                packageLabel:               "باقة: ",
                bookingNow:                 "جاري حجز: ",
                customer:                   "العميل",
                totalAmount:                "المبلغ الإجمالي",
                sar:                        "ر.س",

                // Validation messages
                pleaseSelectBranch:         "يرجى اختيار الفرع أولاً",
                pleaseSelectSpecialist:     "يرجى اختيار الأخصائية",
                pleaseSelectDate:           "يرجى تحديد التاريخ",
                pleaseSelectSlot:           "يرجى اختيار وقت الحجز المتاح",
                pleaseSelectCustomer:       "يرجى اختيار العميل",
                pleaseSelectPayment:        "يرجى اختيار طريقة الدفع",
                bookingSuccess:             "تم تأكيد الحجز بنجاح",
                bookingError:               "حدث خطأ أثناء حفظ الحجز",
            };
        } else {
            return {
                // Header
                newBookingAndPayment:       "New Booking and Payment",
                chooseDetails:              "Choose details to complete your booking successfully",
                step1Label:                 "1. Category",
                step2Label:                 "2. Service/Package",
                step3Label:                 "3. Details",
                step4Label:                 "4. Payment",

                // Step 1
                selectCategory:             "Select Category",
                showAllServicesAndPackages: "Show All Services and Packages",

                // Step 2
                selectServiceOrPackage:     "Select Service or Package",
                backToCategories:           "Back to Categories",
                package:                    "Package",
                packageContents:            "Package Contents",
                cancelPackageAndReturn:     "Cancel Package and Return",
                youArePurchasingPackage:    "You are now purchasing a package:",
                packagePaymentNote:         "The customer will pay the full package price now. Please select the first service to be executed today.",
                selectForTodaySession:      "Select for today's session",

                // Step 3
                bookingService:             "Booking Service",
                of:                         "of",
                serviceBookingSettings:     "Service Booking Settings",
                back:                       "Back",
                bookingType:                "Booking Type",
                insideBranch:               "Inside (Branch)",
                outsideHome:                "Outside (Home)",
                availableBranch:            "Available Branch",
                selectBranch:               "-- Select Branch --",
                availableSpecialist:        "Available Specialist",
                selectSpecialist:           "-- Select Specialist --",
                availableDatesForSpecialist:"Available Dates for Specialist",
                selectBookingDate:          "-- Select Booking Date --",
                sorryNoDates:               "Sorry, no available dates for this specialist.",
                availableTimesSlots:        "Available Times (Slots)",
                selectSuitableTime:         "-- Select Suitable Time --",
                noAppointmentsAvailable:    "No appointments available on this day.",
                nextBookNextPackageService: "Next: Book Next Package Service",
                nextCustomerDetailsPayment: "Next: Customer Details and Payment",

                // Step 4
                customerDetailsAndPayment:  "Customer Details and Payment",
                selectCustomer:             "Select Customer",
                selectCustomerFromList:     "-- Select a customer from the list --",
                noNumber:                   "No number",
                paymentMethodPOS:           "Payment Method (POS)",
                selectPaymentMethod:        "-- Select payment method for immediate payment --",
                additionalNotes:            "Additional Notes",
                confirmBookingAndInvoice:   "Confirm Booking and Issue Invoice",

                // Step 5
                bookingConfirmedSuccess:    "Booking and Payment Confirmed Successfully!",
                bookingNumber:              "Booking Number: ",
                newBooking:                 "New Booking",
                printInvoice:               "Print Invoice",

                // Sidebar summary
                bookingSummary:             "Booking Summary",
                category:                   "Category",
                service:                    "Service",
                branch:                     "Branch",
                specialist:                 "Specialist",
                dateAndTime:                "Date & Time",
                packageLabel:               "Package: ",
                bookingNow:                 "Booking now: ",
                customer:                   "Customer",
                totalAmount:                "Total Amount",
                sar:                        "SAR",

                // Validation messages
                pleaseSelectBranch:         "Please select a branch first",
                pleaseSelectSpecialist:     "Please select a specialist",
                pleaseSelectDate:           "Please select a date",
                pleaseSelectSlot:           "Please select an available time slot",
                pleaseSelectCustomer:       "Please select a customer",
                pleaseSelectPayment:        "Please select a payment method",
                bookingSuccess:             "Booking confirmed successfully",
                bookingError:               "An error occurred while saving the booking",
            };
        }
    }

    // ─── Logic Methods (unchanged) ───────────────────────────────────────────

    async selectCategory(categ) {
        this.state.selectedCategory = categ;
        const services = await this.orm.call("appointment.management", "get_category_services", [categ ? categ.id : false]);
        this.state.services = services || [];
        this.state.step = 2;
        this.state.isPackageMode = false;
        this.state.selectedPackage = null;
    }

    async selectService(item) {
        if (item.is_package) {
            this.state.isPackageMode = true;
            this.state.selectedPackage = item;
            this.state.calculatedPrice = item.price;
            const packServices = await this.orm.call("appointment.management", "get_package_services", [item.id]);
            this.state.packageServices = packServices || [];
            this.state.currentPackageIndex = 0;
            this.state.packageSelections = [];
            await this.setupStep3ForPackage();
        } else {
            this.state.isPackageMode = false;
            this.state.selectedService = item;
            this.state.calculatedPrice = item.price;
            await this.loadStep3Data();
        }
    }

    async setupStep3ForPackage() {
        this.state.selectedService = this.state.packageServices[this.state.currentPackageIndex];
        await this.loadStep3Data();
    }

    async loadStep3Data() {
        this.state.step = 3;
        const branches = await this.orm.call("product.product", "action_get_appointment_branch", [
            this.state.selectedService.id,
            this.state.selectedPackage ? this.state.selectedPackage.id : false
        ]);
        this.state.availableBranches = Object.entries(branches).map(([id, name]) => ({ id: parseInt(id), name }));
        this.state.selectedBranch = null;
        this.state.selectedEmployee = null;
        this.state.selectedDate = '';
        this.state.selectedSlot = null;
        this.state.availableDates = [];
        this.state.availableSlots = [];
    }

    onTypeChange(ev) {
        this.state.appointment_type = ev.target.value;
        this.updatePrice();
    }

    async onBranchChange(ev) {
        const branchId = parseInt(ev.target.value);
        this.state.selectedBranch = this.state.availableBranches.find(b => b.id === branchId);
        this.state.selectedEmployee = null;
        this.state.selectedDate = '';
        this.state.selectedSlot = null;
        this.state.availableSlots = [];
        this.state.availableDates = [];

        if (branchId) {
            const employees = await this.orm.call("product.product", "action_get_appointment_employee", [
                this.state.selectedService.id,
                branchId,
                this.state.selectedPackage ? this.state.selectedPackage.id : false
            ]);
            this.state.availableEmployees = Object.entries(employees).map(([id, name]) => ({ id: parseInt(id), name }));
        } else {
            this.state.availableEmployees = [];
        }
        this.updatePrice();
    }

    async onEmployeeChange(ev) {
        const empId = parseInt(ev.target.value);
        this.state.selectedEmployee = this.state.availableEmployees.find(e => e.id === empId);
        this.state.selectedDate = '';
        this.state.selectedSlot = null;
        this.state.availableSlots = [];
        this.state.availableDates = [];

        if (this.state.selectedEmployee) {
            this.state.availableDates = await this.orm.call("appointment.management", "get_employee_available_dates", [this.state.selectedEmployee.id]);
        }
        this.updatePrice();
    }

    async onDateChange(ev) {
        this.state.selectedDate = ev.target.value;
        this.state.selectedSlot = null;
        this.state.availableSlots = [];

        if (this.state.selectedDate && this.state.selectedEmployee) {
            const slots = await this.orm.call("product.product", "action_get_appointment_employee_slot", [
                this.state.selectedService.id,
                this.state.selectedEmployee.id,
                this.state.selectedDate,
                this.state.appointment_type,
                this.state.selectedBranch.id,
                this.state.selectedPackage ? this.state.selectedPackage.id : false
            ]);
            this.state.availableSlots = Object.values(slots);
        }
    }

    onSlotChange(ev) {
        const slotName = ev.target.value;
        this.state.selectedSlot = this.state.availableSlots.find(s => s.name === slotName);
    }

    onPartnerChange(ev) {
        const partnerId = parseInt(ev.target.value);
        this.state.selectedPartner = this.state.partners.find(p => p.id === partnerId);
    }

    onPaymentMethodChange(ev) {
        const pmId = parseInt(ev.target.value);
        this.state.selectedPaymentMethod = this.state.payment_methods.find(p => p.id === pmId);
    }

    async updatePrice() {
        if (!this.state.isPackageMode && this.state.selectedBranch && this.state.selectedEmployee) {
            const price = await this.orm.call("product.product", "action_get_appointment_service_price", [
                this.state.selectedService.id,
                this.state.selectedBranch.id,
                this.state.selectedEmployee.id,
                this.state.appointment_type,
                false
            ]);
            this.state.calculatedPrice = price;
        }
    }

    nextStep3() {
        const t = this.t;
        if (!this.state.selectedBranch)   return this.notification.add(t.pleaseSelectBranch,     { type: "warning" });
        if (!this.state.selectedEmployee) return this.notification.add(t.pleaseSelectSpecialist,  { type: "warning" });
        if (!this.state.selectedDate)     return this.notification.add(t.pleaseSelectDate,        { type: "warning" });
        if (!this.state.selectedSlot)     return this.notification.add(t.pleaseSelectSlot,        { type: "warning" });

        const currentSelection = {
            product_id:       this.state.selectedService.id,
            branch_id:        this.state.selectedBranch.id,
            employee_id:      this.state.selectedEmployee.id,
            date:             this.state.selectedDate,
            slot_ids:         this.state.selectedSlot.ids,
            appointment_type: this.state.appointment_type,
            service_name:     this.state.selectedService.name,
            branch_name:      this.state.selectedBranch.name,
            employee_name:    this.state.selectedEmployee.name,
            slot_name:        this.state.selectedSlot.name,
        };

        if (this.state.isPackageMode) {
            this.state.packageSelections[this.state.currentPackageIndex] = currentSelection;
            if (this.state.currentPackageIndex < this.state.packageServices.length - 1) {
                this.state.currentPackageIndex++;
                this.setupStep3ForPackage();
            } else {
                this.state.step = 4;
            }
        } else {
            this.state.packageSelections = [currentSelection];
            this.state.step = 4;
        }
    }

    step3Back() {
        if (this.state.isPackageMode && this.state.currentPackageIndex > 0) {
            this.state.currentPackageIndex--;
            this.setupStep3ForPackage();
        } else {
            this.state.step = 2;
            this.state.isPackageMode = false;
            this.state.selectedPackage = null;
        }
    }

    async confirmBooking() {
        const t = this.t;
        if (!this.state.selectedPartner)       return this.notification.add(t.pleaseSelectCustomer, { type: "warning" });
        if (!this.state.selectedPaymentMethod) return this.notification.add(t.pleaseSelectPayment,  { type: "warning" });

        this.state.isSubmitting = true;
        try {
            const res = await this.orm.call("appointment.management", "create_direct_appointment", [{
                partner_id:        this.state.selectedPartner.id,
                package_id:        this.state.isPackageMode ? this.state.selectedPackage.id : false,
                price:             this.state.calculatedPrice,
                payment_method_id: this.state.selectedPaymentMethod.id,
                notes:             this.state.notes,
                appointments:      this.state.packageSelections,
            }]);

            if (res.status === "success") {
                this.notification.add(t.bookingSuccess, { type: "success" });
                this.state.confirmedRef       = res.ref;
                this.state.confirmedInvoiceId = res.invoice_id;
                this.state.step = 5;
            }
        } catch (error) {
            this.notification.add(t.bookingError, { type: "danger" });
        } finally {
            this.state.isSubmitting = false;
        }
    }

    printInvoice() {
        if (this.state.confirmedInvoiceId) {
            this.action.doAction({
                type:        'ir.actions.report',
                report_type: 'qweb-pdf',
                report_name: 'account.report_invoice_with_payments',
                report_file: 'account.report_invoice_with_payments',
                context:     { active_ids: [this.state.confirmedInvoiceId] },
            });
        }
    }

    resetWizard() {
        this.state.step                 = 1;
        this.state.isPackageMode        = false;
        this.state.selectedPackage      = null;
        this.state.packageServices      = [];
        this.state.packageSelections    = [];
        this.state.selectedCategory     = null;
        this.state.selectedService      = null;
        this.state.selectedBranch       = null;
        this.state.selectedEmployee     = null;
        this.state.selectedDate         = '';
        this.state.selectedSlot         = null;
        this.state.selectedPartner      = null;
        this.state.selectedPaymentMethod = null;
    }
}

registry.category("actions").add("appointment_booking_screen_tag", AppointmentBookingScreen);