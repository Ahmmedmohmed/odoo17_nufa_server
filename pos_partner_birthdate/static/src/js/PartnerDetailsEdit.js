/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        this.popup = useService("popup");
        this.pos = usePos();
        this.intFields = ["country_id", "state_id", "property_product_pricelist"];
        const partner = this.props.partner;
        this.changes = useState({
            first_name: partner.first_name || false,
            last_name: partner.last_name || false,
            birth_date: partner.birth_date || false,
            married_date: partner.married_date || false,
            street: partner.street || false,
            city: partner.city || false,
            zip: partner.zip || false,
            state_id: partner.state_id && partner.state_id[0],
            country_id: partner.country_id && partner.country_id[0],
            lang: partner.lang || false,
            email: partner.email || false,
            phone: partner.phone || false,
            mobile: partner.mobile || false,
            barcode: partner.barcode || false,
            vat: partner.vat || false,
            property_product_pricelist: this.setDefaultPricelist(partner),
        });
        // Provides translated terms used in the view
        this.partnerDetailsFields = {
            'Street': _t('Street'),
            'City': _t('City'),
            'Zip': _t('Zip'),
            'Email': _t('Email'),
            'Phone': _t('Phone'),
            'Mobile': _t('Mobile'),
            'Barcode': _t('Barcode'),
            'First Name': _t('First Name'),
            'Last Name': _t('Last Name'),
            'Birth Date': _t('Birth Date'),
            'Married Date': _t('Married Date'),
        };
        Object.assign(this.props.imperativeHandle, {
            save: () => this.saveChanges(),
        });
    },

    saveChanges() {
        const processedChanges = {};
        for (const [key, value] of Object.entries(this.changes)) {
            if (this.intFields.includes(key)) {
                processedChanges[key] = parseInt(value) || false;
            } else {
                processedChanges[key] = value;
            }
        }
        if (
            processedChanges.state_id &&
            this.pos.states.find((state) => state.id === processedChanges.state_id)
                .country_id[0] !== processedChanges.country_id
        ) {
            processedChanges.state_id = false;
        }

        if ((!this.props.partner.first_name && !processedChanges.first_name) || processedChanges.first_name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer First Name Is Required"),
            });
        }

        if ((!this.props.partner.last_name && !processedChanges.last_name) || processedChanges.last_name === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Last Name Is Required"),
            });
        }

        if ((!this.props.partner.phone && !processedChanges.phone) || processedChanges.phone === "") {
            return this.popup.add(ErrorPopup, {
                title: _t("A Customer Phone Is Required"),
            });
        }
        processedChanges.id = this.props.partner.id || false;
        this.props.saveChanges(processedChanges);
    }
});