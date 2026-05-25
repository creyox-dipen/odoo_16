odoo.define('cr_payment_nmi_integration.nmi_card_form', function (require) {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const publicWidget = require('web.public.widget');
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
         * Override _prepareInlineForm to ensure flow is 'direct' for NMI.
         */
        _prepareInlineForm: function (code, paymentOptionId, flow) {
            if (code === 'nmi' && flow !== 'token') {
                this._setPaymentFlow('direct');
            }
            return this._super(...arguments);
        },

        /**
         * Override _processDirectPayment to handle NMI card payment.
         */
        _processDirectPayment: function (code, providerId, processingValues) {
            if (code !== 'nmi') {
                return this._super(...arguments);
            }
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            if (!checkedRadio || $(checkedRadio).data('payment-option-type') === 'token') {
                return this._super(...arguments);
            }
            const paymentOptionId = $(checkedRadio).data('payment-option-id');
            const inlineForm = this.$(`#o_payment_provider_inline_form_${paymentOptionId}`);
            if (inlineForm.find('.o_payment_nmi_card_form').length > 0) {
                return this._submitNmiCardForm(processingValues);
            }
            return this._super(...arguments);
        },

        /**
         * Override _processRedirectPayment to handle NMI card payment.
         */
        _processRedirectPayment: function (code, providerId, processingValues) {
            if (code !== 'nmi') {
                return this._super(...arguments);
            }
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            if (!checkedRadio || $(checkedRadio).data('payment-option-type') === 'token') {
                return this._super(...arguments);
            }
            const paymentOptionId = $(checkedRadio).data('payment-option-id');
            const inlineForm = this.$(`#o_payment_provider_inline_form_${paymentOptionId}`);
            if (inlineForm.find('.o_payment_nmi_card_form').length > 0) {
                return this._submitNmiCardForm(processingValues);
            }
            return this._super(...arguments);
        },

        /**
         * Validates card fields and POSTs data to the NMI card controller.
         */
        _submitNmiCardForm: function (processingValues) {
            const getValue = (id) => this.$(`#${id}`).val()?.trim() ?? '';

            const ccnumber = getValue('nmi_ccnumber').replace(/\s+/g, '');
            const ccexp    = getValue('nmi_ccexp');
            const cvv      = getValue('nmi_cvv');

            // --- Client-side validation ---
            if (!ccnumber || ccnumber.length < 13) {
                this._enableButton();
                this._displayError(_t("Validation Error"), _t("Please enter a valid card number."));
                return;
            }
            if (!/^\d{2}\/\d{2}$/.test(ccexp)) {
                this._enableButton();
                this._displayError(_t("Validation Error"), _t("Please enter the expiry date in MM/YY format."));
                return;
            }
            if (!/^\d{3,4}$/.test(cvv)) {
                this._enableButton();
                this._displayError(_t("Validation Error"), _t("Please enter a valid CVV (3 or 4 digits)."));
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
                tokenize: this.txContext.tokenizationRequested ? '1' : '0',
                csrf_token: core.csrf_token,
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
        selector: 'form[name="o_payment_checkout"]',
        events: {
            'input #nmi_ccnumber': '_onCardInput',
            'change input[name="o_payment_radio"]': '_onRadioChange',
        },

        _onRadioChange: function () {
            this._updateFeeSummary(false);
            this.lastBin = null;
        },

        _onCardInput: async function (ev) {
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
                const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
                const providerId   = parseInt($(checkedRadio).data('payment-option-id'));
                const result = await this._rpc({
                    route: '/payment/nmi/bin_lookup',
                    params: {
                        bin_number:  bin,
                        provider_id: providerId,
                    }
                });
                this._updateFeeSummary(result.type);
            } catch (error) {
                console.error('[NMI BIN Lookup] Error:', error);
                this._updateFeeSummary(false);
            }
        },

        _updateFeeSummary: function (cardType) {
            const formContainer = this.$('.o_payment_nmi_card_form')[0];
            const summary = this.$('#nmi_fee_summary')[0];
            if (!summary || !formContainer) return;

            const ctx       = $(formContainer).data();
            const feeActive = ctx.feeActive === true || ctx.feeActive === 'True' || ctx.feeActive === 'true' || ctx.feeActive === '1';

            let feePercent = 0;
            if (cardType === 'credit' || cardType === 'charge') {
                feePercent = parseFloat(ctx.creditFeePercent) || 0;
            } else if (cardType === 'debit') {
                feePercent = parseFloat(ctx.debitFeePercent) || 0;
            }

            if (feeActive && feePercent > 0) {
                const baseAmount   = parseFloat(this.$el.data('amount')) || 0;
                const fee          = (baseAmount * feePercent) / 100;
                const total        = baseAmount + fee;
                const currencyName = this.$el.data('currency-name') || 'USD';
                const formatter    = new Intl.NumberFormat('en-US', { style: 'currency', currency: currencyName });

                this.$('#nmi_fee_amount').text(formatter.format(fee));
                this.$('#nmi_total_amount').text(formatter.format(total));
                $(summary).removeClass('d-none');
            } else {
                $(summary).addClass('d-none');
            }
        },
    });

    return checkoutForm;
});
