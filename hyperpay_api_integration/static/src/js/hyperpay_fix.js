/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import PaymentForm from "@payment/js/payment_form";

patch(PaymentForm.prototype, {
    async _submitForm(ev) {
        // تحقق من اختيار HyperPay قبل أي شيء
        const checkedRadio = document.querySelector('input[name="o_payment_radio"]:checked');
        if (checkedRadio && checkedRadio.dataset.providerCode === 'hyperpay') {
            ev && ev.preventDefault();
            ev && ev.stopImmediatePropagation();

            const orderId = this._getHyperPayOrderId();
            if (orderId) {
                window.location.href = `/shop/payment/hyperpay/pay/${orderId}`;
            } else {
                console.error("HyperPay: order ID not found");
            }
            return; // لا تكمل منطق أودو
        }
        // غير HyperPay: اشتغل بشكل عادي
        return super._submitForm(...arguments);
    },

    _getHyperPayOrderId() {
        // أودو 17 يخزن الـ order في sale_order_id hidden input
        const sel = [
            'input[name="sale_order_id"]',
            'input[name="order_id"]',
            '[data-order-id]',
        ];
        for (const s of sel) {
            const el = document.querySelector(s);
            if (el) return el.value || el.dataset.orderId;
        }
        // من transaction_route: "/payment/transaction/42"
        const txRoute = document.querySelector('[name="transaction_route"]')
                     || document.querySelector('[data-transaction-route]');
        if (txRoute) {
            const val = txRoute.value || txRoute.dataset.transactionRoute || '';
            const m = val.match(/\/(\d+)/);
            if (m) return m[1];
        }
        return null;
    }
});