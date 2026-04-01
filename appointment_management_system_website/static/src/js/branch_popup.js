/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

let branchCache = null;

async function fetchBranches() {
    if (branchCache !== null) return branchCache;
    const result = await jsonrpc('/shop/branches', {});
    branchCache = result || [];
    return branchCache;
}

function showBranchPopup(branches) {
    return new Promise((resolve, reject) => {
        const overlay = document.createElement('div');
        overlay.className = 'branch-popup-overlay';
        overlay.innerHTML = `
            <div class="branch-popup-modal">
                <div class="branch-popup-header">
                    <h4>Select Branch</h4>
                    <button class="branch-popup-close">&times;</button>
                </div>
                <div class="branch-popup-body">
                    ${branches.map(b => `
                        <div class="branch-popup-item" data-branch-id="${b.id}">
                            <div class="branch-popup-logo">
                                ${b.logo ? `<img src="${b.logo}" alt="${b.name}"/>` : `<i class="fa fa-building"></i>`}
                            </div>
                            <div class="branch-popup-name">${b.name}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        setTimeout(() => overlay.classList.add('active'), 10);

        overlay.querySelector('.branch-popup-close').addEventListener('click', () => {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 300);
            reject('cancelled');
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('active');
                setTimeout(() => overlay.remove(), 300);
                reject('cancelled');
            }
        });

        overlay.querySelectorAll('.branch-popup-item').forEach(item => {
            item.addEventListener('click', () => {
                const branchId = item.dataset.branchId;
                overlay.classList.remove('active');
                setTimeout(() => overlay.remove(), 300);
                resolve(branchId);
            });
        });
    });
}

function addBranchInput(form, branchId) {
    let input = form.querySelector('input[name="branch_id"]');
    if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'branch_id';
        form.appendChild(input);
    }
    input.value = branchId;
}

publicWidget.registry.BranchPopupWidget = publicWidget.Widget.extend({
    selector: '#wrapwrap',

    start: function () {
        this._super.apply(this, arguments);
        this._interceptAddToCart();
        return Promise.resolve();
    },

    _interceptAddToCart: function () {
        const self = this;
        document.addEventListener('submit', function (ev) {
            const form = ev.target;
            if (!form.matches || !form.matches('form[action="/shop/cart/update"]')) return;
            if (form.dataset.branchSelected === 'true') return;

            ev.preventDefault();
            ev.stopImmediatePropagation();

            fetchBranches().then(branches => {
                if (!branches || branches.length === 0) {
                    form.dataset.branchSelected = 'true';
                    form.submit();
                    return;
                }
                if (branches.length === 1) {
                    addBranchInput(form, branches[0].id);
                    form.dataset.branchSelected = 'true';
                    form.submit();
                    return;
                }
                showBranchPopup(branches).then(branchId => {
                    addBranchInput(form, branchId);
                    form.dataset.branchSelected = 'true';
                    form.submit();
                }).catch(() => {});
            });
        }, true);

        document.addEventListener('click', function (ev) {
            const link = ev.target.closest('form[action="/shop/cart/update"] a.a-submit');
            if (!link) return;
            const form = link.closest('form[action="/shop/cart/update"]');
            if (!form) return;
            if (form.dataset.branchSelected === 'true') {
                form.dataset.branchSelected = '';
                return;
            }

            ev.preventDefault();
            ev.stopImmediatePropagation();

            fetchBranches().then(branches => {
                if (!branches || branches.length === 0) {
                    form.dataset.branchSelected = 'true';
                    form.submit();
                    return;
                }
                if (branches.length === 1) {
                    addBranchInput(form, branches[0].id);
                    form.dataset.branchSelected = 'true';
                    form.submit();
                    return;
                }
                showBranchPopup(branches).then(branchId => {
                    addBranchInput(form, branchId);
                    form.dataset.branchSelected = 'true';
                    form.submit();
                }).catch(() => {});
            });
        }, true);
    },
});
