/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

// 1. اعتراض في شاشة List
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        this.wizardAction = useService("action");
    },
    onClickCreate() {
        if (this.props.resModel === "appointment.management") {
            this.wizardAction.doAction("appointment_management_system.action_appointment_booking_wizard");
        } else {
            super.onClickCreate(...arguments);
        }
    }
});

// 2. اعتراض في شاشة Kanban
patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        this.wizardAction = useService("action");
    },
    createRecord() {
        if (this.props.resModel === "appointment.management") {
            this.wizardAction.doAction("appointment_management_system.action_appointment_booking_wizard");
        } else {
            super.createRecord(...arguments);
        }
    }
});

// 3. 🚀 اعتراض في شاشة Form (الزرار الجديد اللي إنت طلبته)
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.wizardAction = useService("action");
    },
    async create() {
        if (this.props.resModel === "appointment.management") {
            this.wizardAction.doAction("appointment_management_system.action_appointment_booking_wizard");
        } else {
            return super.create(...arguments);
        }
    }
});