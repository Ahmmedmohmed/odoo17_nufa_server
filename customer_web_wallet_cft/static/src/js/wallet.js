odoo.define('account.AccountPortalSidebar.instance', function (require) {
"use strict";

    require('web.dom_ready');

    $('#add_money_button').on('click', function () {
        $('#add_money').toggleClass('d-none');
    })

    $('#transaction_history').click('/website/wallet/transaction')
});