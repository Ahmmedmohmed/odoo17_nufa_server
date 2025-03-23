/** @odoo-module */
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

export class OutOfStockMessagePopup extends AbstractAwaitablePopup {
    static template = "pos_stocks.OutOfStockMessagePopup";
    static defaultProps = {
        title: "Confirm ?",
        body: ""
    };

    setup() {
        super.setup();
        this.pos = usePos();
        onMounted(this.onMounted);
        Object.assign(this, this.props.info);
    }
    onMounted(){
        var self = this;
        $('.search-box input').on('keyup', function(ev) {
            var data = self.pos.data_to_search[ev.currentTarget.name];
            var count = data.length;
            var val = $(ev.currentTarget).val();
            var search_section = $(ev.currentTarget).parents('.search-section').children('.search-options');
            
            if(ev.key === 'Backspace' && count && !val){
                data.pop();
                search_section.css({'display' : 'none'});
            }
            search_section.css({'display' : 'block'});
        });
        $('.advance_med_body').on('click', function(ev) {
            $('.search-options').css({'display' : 'none'});
        });
        $('.search-section').on('click', function(ev) {
            ev.stopPropagation();
            ev.preventDefault();
        });
    }
}