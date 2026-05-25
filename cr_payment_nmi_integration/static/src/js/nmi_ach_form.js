/** @odoo-module **/
/* Part of Creyox Technologies */

import PaymentForm from '@payment/js/payment_form';
import { _t } from '@web/core/l10n/translation';

/**
 * NMI ACH Direct Debit — Odoo 17 CE frontend handler.
 */
PaymentForm.include({

    /**
     * Determine and return the payment flow of the selected payment option.
     *
     * We override this to force 'direct' flow for NMI ACH, preventing Odoo's
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
        if (providerCode === 'nmi' && paymentMethodCode === 'ach_direct_debit') {
            const paymentOptionType = this._getPaymentOptionType(radio);
            return paymentOptionType === 'token' ? 'token' : 'direct';
        }
        return this._super(...arguments);
    },

    /**
     * Override _prepareInlineForm to ensure flow is 'direct' for NMI ACH.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode === 'nmi' && paymentMethodCode === 'ach_direct_debit' && flow !== 'token') {
            this._setPaymentFlow('direct');
        }
        return this._super(...arguments);
    },

    /**
     * Override _processDirectFlow to handle NMI ACH payment.
     * Called when flow === 'direct'.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode !== 'ach_direct_debit') {
            return this._super(...arguments);
        }
        return this._submitNmiAchForm(processingValues);
    },

    /**
     * Override _processRedirectFlow — Safety net for NMI ACH.
     * Intercepts and redirects to our direct flow handler.
     *
     * @override method from @payment/js/payment_form
     * @private
     */
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode !== 'ach_direct_debit') {
            return this._super(...arguments);
        }
        return this._submitNmiAchForm(processingValues);
    },

    /**
     * Validates ACH fields and POSTs data to the NMI ACH controller.
     *
     * @private
     * @param {object} processingValues - Transaction processing values from server.
     */
    _submitNmiAchForm(processingValues) {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(checkedRadio) || this.el;

        const getValue = (name) =>
            (inlineForm.querySelector(`[name="${name}"]`) || this.el.querySelector(`[name="${name}"]`))
                ?.value?.trim() ?? '';

        const checkname           = getValue('checkname');
        const checkaba            = getValue('checkaba');
        const checkaccount        = getValue('checkaccount');
        const account_type        = getValue('account_type') || 'checking';
        const account_holder_type = getValue('account_holder_type') || 'personal';

        // --- Client-side validation ---
        if (!checkname) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Please enter the Account Holder Name."));
            return;
        }
        if (!/^\d{9}$/.test(checkaba)) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Routing number must be exactly 9 digits."));
            return;
        }
        if (!checkaccount) {
            this._enableButton();
            this._displayErrorDialog(_t("Validation Error"), _t("Please enter the Account Number."));
            return;
        }

        // --- Build and submit form to controller ---
        const achUrl = processingValues.ach_process_url || '/payment/nmi/ach/process';
        const form = document.createElement('form');
        form.method = 'post';
        form.action = achUrl;

        const formFields = {
            reference:            processingValues.reference || '',
            amount:               processingValues.amount    || '',
            checkname,
            checkaba,
            checkaccount,
            account_type,
            account_holder_type,
            tokenize: this.paymentContext['tokenizationRequested'] ? '1' : '0',
            csrf_token: odoo.csrf_token,
        };

        for (const [name, value] of Object.entries(formFields)) {
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
