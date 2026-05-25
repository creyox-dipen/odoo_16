odoo.define('cr_payment_nmi_integration.nmi_ach_form', function (require) {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const core = require('web.core');
    const _t = core._t;

    checkoutForm.include({

        /**
         * Determine and return the payment flow of the selected payment option.
         */
        _getPaymentFlowFromRadio: function (radio) {
            const providerCode = $(radio).data('provider');
            const paymentOptionType = $(radio).data('payment-option-type');
            if (providerCode === 'nmi' && paymentOptionType !== 'token') {
                return 'direct';
            }
            return this._super(...arguments);
        },

        /**
         * Override _prepareInlineForm to ensure flow is 'direct' for NMI ACH.
         */
        _prepareInlineForm: function (code, paymentOptionId, flow) {
            if (code === 'nmi' && flow !== 'token') {
                this._setPaymentFlow('direct');
            }
            return this._super(...arguments);
        },

        /**
         * Override _processDirectPayment to handle NMI ACH payment.
         */
        _processDirectPayment: function (code, providerId, processingValues) {
            if (code !== 'nmi') {
                return this._super(...arguments);
            }
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            if (!checkedRadio || $(checkedRadio).data('payment-option-type') === 'token') {
                return this._super(...arguments);
            }
            if (this.$('.o_payment_ach_form').length > 0) {
                return this._submitNmiAchForm(processingValues);
            }
            return this._super(...arguments);
        },

        /**
         * Override _processRedirectPayment to handle NMI ACH payment.
         */
        _processRedirectPayment: function (code, providerId, processingValues) {
            if (code !== 'nmi') {
                return this._super(...arguments);
            }
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            if (!checkedRadio || $(checkedRadio).data('payment-option-type') === 'token') {
                return this._super(...arguments);
            }
            if (this.$('.o_payment_ach_form').length > 0) {
                return this._submitNmiAchForm(processingValues);
            }
            return this._super(...arguments);
        },

        /**
         * Validates ACH fields and POSTs data to the NMI ACH controller.
         */
        _submitNmiAchForm: function (processingValues) {
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            const formType = $(checkedRadio).data('payment-option-type');
            const paymentOptionId = $(checkedRadio).data('payment-option-id');
            const inlineForm = this.$(`#o_payment_${formType}_inline_form_${paymentOptionId}`)[0] || this.el;

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
                this._displayError(_t("Validation Error"), _t("Please enter the Account Holder Name."));
                return;
            }
            if (!/^\d{9}$/.test(checkaba)) {
                this._enableButton();
                this._displayError(_t("Validation Error"), _t("Routing number must be exactly 9 digits."));
                return;
            }
            if (!checkaccount) {
                this._enableButton();
                this._displayError(_t("Validation Error"), _t("Please enter the Account Number."));
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
                tokenize: this.txContext.tokenizationRequested ? '1' : '0',
                csrf_token: core.csrf_token,
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

    return checkoutForm;
});
