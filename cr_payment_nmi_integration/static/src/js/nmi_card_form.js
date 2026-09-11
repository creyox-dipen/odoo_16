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
     * publicWidget to handle real-time fee summary updates based on BIN lookup and Token surcharge.
     */
    publicWidget.registry.NmiCardFeeDisplay = publicWidget.Widget.extend({
        selector: 'form[name="o_payment_checkout"]',
        events: {
            'input #nmi_ccnumber': '_onCardInput',
            'change input[name="o_payment_radio"]': '_onRadioChange',
            'click div[name="o_payment_option_card"]': '_onCardClick',
            'click input[name="o_payment_radio"]': '_onCardClick',
        },

        start: function () {
            this.lastBin = null;
            this._initTokenBadges();
            this._onRadioChange();
            return this._super.apply(this, arguments);
        },

        _initTokenBadges: function () {
            const $paymentForm = this.$el;
            const badges = this.$('.nmi-token-fee-badge');
            if (!badges.length) return;

            const baseAmount = parseFloat($paymentForm.data('amount')) || 0;
            const currencyName = $paymentForm.data('currency-name') || 'USD';

            badges.each(function () {
                const badge = this;
                const cardType = $(badge).data('card-type');
                const creditFee = parseFloat($(badge).data('credit-fee')) || 0;
                const debitFee = parseFloat($(badge).data('debit-fee')) || 0;

                let feePercent = 0;
                if (cardType === 'credit' || cardType === 'charge') {
                    feePercent = creditFee;
                } else if (cardType === 'debit') {
                    feePercent = debitFee;
                }

                if (feePercent > 0 && baseAmount > 0) {
                    const feeAmount = (baseAmount * feePercent) / 100;
                    const formatter = new Intl.NumberFormat('en-US', {
                        style: 'currency',
                        currency: currencyName,
                    });
                    $(badge).text(`+ ${formatter.format(feeAmount)} Fees`).removeClass('d-none');
                } else {
                    $(badge).addClass('d-none');
                }
            });
        },

        _onCardClick: function (ev) {
            setTimeout(() => {
                this._onRadioChange();
            }, 50);
        },

        _onRadioChange: async function () {
            const checkedRadio = this.$('input[name="o_payment_radio"]:checked')[0];
            if (!checkedRadio) return;

            const providerCode = $(checkedRadio).data('provider');
            const paymentOptionType = $(checkedRadio).data('payment-option-type');
            const paymentOptionId = $(checkedRadio).data('payment-option-id');

            if (providerCode === 'nmi' && paymentOptionType === 'token') {
                this.lastBin = null;
                this._updateFeeSummary(false);
                try {
                    const result = await this._rpc({
                        route: '/payment/nmi/token_surcharge',
                        params: { token_id: parseInt(paymentOptionId) }
                    });
                    this._updateOrderSummaryDOM(result);
                } catch (err) {
                    console.error('[NMI Token Surcharge] Error:', err);
                }
            } else if (providerCode === 'nmi' && paymentOptionType === 'provider') {
                const inlineForm = this.$(`#o_payment_provider_inline_form_${paymentOptionId}`);
                const isCardForm = inlineForm.find('.o_payment_nmi_card_form').length > 0;
                const ccNumberInput = inlineForm.find('#nmi_ccnumber')[0] || this.$('#nmi_ccnumber')[0];
                const cardNumber = ccNumberInput ? ccNumberInput.value.replace(/\s+/g, '') : '';

                if (isCardForm && cardNumber.length >= 6) {
                    const bin = cardNumber.substring(0, 6);
                    this.lastBin = bin;
                    try {
                        const result = await this._rpc({
                            route: '/payment/nmi/bin_lookup',
                            params: {
                                bin_number: bin,
                                provider_id: parseInt(paymentOptionId),
                            }
                        });
                        this._updateFeeSummary(result.type);
                        this._updateOrderSummaryDOM(result);
                    } catch (err) {
                        console.error('[NMI BIN Lookup] Error:', err);
                    }
                } else {
                    this.lastBin = null;
                    this._updateFeeSummary(false);
                    try {
                        const result = await this._rpc({
                            route: '/payment/nmi/clear_surcharge',
                            params: {}
                        });
                        this._updateOrderSummaryDOM(result);
                    } catch (err) {
                        console.error('[NMI Clear Surcharge] Error:', err);
                    }
                }
            } else {
                this.lastBin = null;
                this._updateFeeSummary(false);
                try {
                    const result = await this._rpc({
                        route: '/payment/nmi/clear_surcharge',
                        params: {}
                    });
                    this._updateOrderSummaryDOM(result);
                } catch (err) {
                    console.error('[NMI Clear Surcharge] Error:', err);
                }
            }
        },

        _onCardInput: async function (ev) {
            const cardNumber = ev.target.value.replace(/\s+/g, '');
            if (cardNumber.length < 6) {
                if (this.lastBin !== null) {
                    this.lastBin = null;
                    this._updateFeeSummary(false);
                    try {
                        const result = await this._rpc({
                            route: '/payment/nmi/clear_surcharge',
                            params: {}
                        });
                        this._updateOrderSummaryDOM(result);
                    } catch (err) {
                        console.error('[NMI Clear Surcharge] Error:', err);
                    }
                }
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
                this._updateOrderSummaryDOM(result);
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

        _updateOrderSummaryDOM: function (data) {
            if (!data) return;
            _logger_info('[NMI] Updating Order Summary DOM:', data);

            // 1. Cart total section (contains Subtotal, Surcharge, Tax, Total)
            const summaryHtml = data.summary_html || data.total_html;
            if (summaryHtml) {
                const $cartTotal = $('#cart_total');
                if ($cartTotal.length) {
                    $cartTotal.replaceWith(summaryHtml);
                }
            }

            // 2. Cart lines section (products list)
            if (data.cart_lines_html) {
                const $cartProducts = $('#cart_products');
                if ($cartProducts.length) {
                    $cartProducts.replaceWith(data.cart_lines_html);
                }
            }

            // 3. Simple total summary badge/text if present
            if (data.amount_total_html) {
                const $amountTotalSummary = $('#amount_total_summary');
                if ($amountTotalSummary.length) {
                    $amountTotalSummary.replaceWith(data.amount_total_html);
                }
            }
        },
    });

    function _logger_info(...args) {
        console.log(...args);
    }

    return checkoutForm;
});

