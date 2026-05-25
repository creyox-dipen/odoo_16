/** @odoo-module **/
/* Part of Creyox Technologies */

import PaymentForm from '@payment/js/payment_form';
import publicWidget from '@web/legacy/js/public/public_widget';
import { _t } from '@web/core/l10n/translation';

/**
 * NMI Card Payment — Odoo 17 CE frontend handler.
 */
PaymentForm.include({

    /**
     * Determine and return the payment flow of the selected payment option.
     *
     * We override this to force 'direct' flow for NMI Card, preventing Odoo's
     * base JS from attempting a redirect flow and crashing when no redirect
     * form element is found.
     *
     * @override method from @payment/js/payment_form
     * @private
     * @param {HTMLInputElement} radio - The radio button linked to the payment option.
     * @return {string} The flow of the selected payment option.
     */
    _getPaymentFlow(radio) {
        const providerCode = this._getProviderCode(radio);
        const paymentMethodCode = this._getPaymentMethodCode(radio);
        if (providerCode === 'nmi' && paymentMethodCode !== 'ach_direct_debit') {
            const paymentOptionType = this._getPaymentOptionType(radio);
            return paymentOptionType === 'token' ? 'token' : 'direct';
        }
        return this._super(...arguments);
    },

    /**
     * Override _prepareInlineForm to ensure flow is 'direct' for NMI.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode === 'nmi' && paymentMethodCode !== 'ach_direct_debit' && flow !== 'token') {
            this._setPaymentFlow('direct');
        }
        return this._super(...arguments);
    },

    /**
     * Override _processDirectFlow to handle NMI card payment.
     * Called when flow === 'direct'.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode === 'ach_direct_debit') {
            return this._super(...arguments);
        }
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio || this._getPaymentOptionType(checkedRadio) === 'token') {
            return this._super(...arguments);
        }
        return this._submitNmiCardForm(processingValues);
    },

    /**
     * Override _processRedirectFlow — Safety net for NMI.
     * Intercepts and redirects to our direct flow handler.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode === 'ach_direct_debit') {
            return this._super(...arguments);
        }
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio || this._getPaymentOptionType(checkedRadio) === 'token') {
             return this._super(...arguments);
        }
        return this._submitNmiCardForm(processingValues);
    },

    /**
     * Validates card fields and POSTs data to the NMI card controller.
     *
     * @private
     * @param {object} processingValues - Transaction processing values from server.
     */
    _submitNmiCardForm(processingValues) {
        const getValue = (id) => this.el.querySelector(`#${id}`)?.value?.trim() ?? '';

        const ccnumber = getValue('nmi_ccnumber').replace(/\s+/g, '');
        const ccexp    = getValue('nmi_ccexp');
        const cvv      = getValue('nmi_cvv');

        // --- Client-side validation ---
        if (!ccnumber || ccnumber.length < 13) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Please enter a valid card number."));
            return;
        }
        if (!/^\d{2}\/\d{2}$/.test(ccexp)) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Please enter the expiry date in MM/YY format."));
            return;
        }
        if (!/^\d{3,4}$/.test(cvv)) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Please enter a valid CVV (3 or 4 digits)."));
            return;
        }

        // --- Build and submit form to controller ---
        const form = document.createElement('form');
        form.method = 'post';
        form.action = '/payment/nmi/card/process';

        const fields = {
            reference: processingValues.reference,
            ccnumber,
            ccexp,
            cvv,
            tokenize: this.paymentContext['tokenizationRequested'] ? '1' : '0',
            csrf_token: odoo.csrf_token,
        };

        for (const [name, value] of Object.entries(fields)) {
            const input = document.createElement('input');
            input.type  = 'hidden';
            input.name  = name;
            input.value = value;
            form.appendChild(input);
        }

        document.body.appendChild(form);
        form.submit();
    },
});

/**
 * publicWidget to handle real-time fee summary updates based on BIN lookup.
 */
publicWidget.registry.NmiCardFeeDisplay = publicWidget.Widget.extend({
    selector: '#o_payment_form',
    events: {
        'input #nmi_ccnumber': '_onCardInput',
        'change input[name="o_payment_radio"]': '_onRadioChange',
    },

    /**
     * @override
     */
    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
    },

    _onRadioChange() {
        this._updateFeeSummary(false);
        this.lastBin = null;
    },

    async _onCardInput(ev) {
        const cardNumber = ev.target.value.replace(/\s+/g, '');
        if (cardNumber.length < 6) {
            this.lastBin = null;
            this._updateFeeSummary(false);
            return;
        }

        const bin = cardNumber.substring(0, 6);
        if (this.lastBin === bin) return;
        this.lastBin = bin;

        try {
            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
            const providerId   = parseInt(checkedRadio?.dataset.providerId);
            const result = await this.rpc('/payment/nmi/bin_lookup', {
                bin_number:  bin,
                provider_id: providerId,
            });
            this._updateFeeSummary(result.type);
        } catch (error) {
            console.error('[NMI BIN Lookup] Error:', error);
            this._updateFeeSummary(false);
        }
    },

    _updateFeeSummary(cardType) {
        const formContainer = this.el.classList.contains('o_payment_nmi_card_form')
            ? this.el
            : this.el.querySelector('.o_payment_nmi_card_form');
        const summary = this.el.querySelector('#nmi_fee_summary');
        if (!summary || !formContainer) return;

        const ctx       = formContainer.dataset;
        const feeActive = ctx.feeActive === 'True' || ctx.feeActive === 'true' || ctx.feeActive === '1';

        let feePercent = 0;
        if (cardType === 'credit' || cardType === 'charge') {
            feePercent = parseFloat(ctx.creditFeePercent) || 0;
        } else if (cardType === 'debit') {
            feePercent = parseFloat(ctx.debitFeePercent) || 0;
        }

        if (feeActive && feePercent > 0) {
            const baseAmount   = parseFloat(this.el.dataset.amount) || 0;
            const fee          = (baseAmount * feePercent) / 100;
            const total        = baseAmount + fee;
            const currencyName = this.el.dataset.currencyName || 'USD';
            const formatter    = new Intl.NumberFormat('en-US', { style: 'currency', currency: currencyName });

            const feeEl   = this.el.querySelector('#nmi_fee_amount');
            const totalEl = this.el.querySelector('#nmi_total_amount');
            if (feeEl)   feeEl.textContent  = formatter.format(fee);
            if (totalEl) totalEl.textContent = formatter.format(total);
            summary.classList.remove('d-none');
        } else {
            summary.classList.add('d-none');
        }
    },
});
