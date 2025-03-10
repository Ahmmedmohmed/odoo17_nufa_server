/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { WarningDialog } from "@web/core/errors/error_dialogs";

import { DateTimeInput } from '@web/core/datetime/datetime_input';
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

const { DateTime } = luxon;

// export class AccountReportFilters extends Component {
    // static template = "account_reports.AccountReportFilters";
    // static props = {};
    // static components = {
    //     DateTimeInput,
    //     Dropdown,
    //     DropdownItem,
    //     MultiRecordSelector,
    // };
patch(AccountReportFilters.prototype, {
    
    setup() {
        this.dialog = useService("dialog");
        this.companyService = useService("company");
        this.controller = useState(this.env.controller);
    },

    get hasAnalyticTagFilter() {
        return Boolean(this.controller.groups.analytic_accounting) && Boolean(this.controller.filters.display_analytic_tag_filter);
    }
})

