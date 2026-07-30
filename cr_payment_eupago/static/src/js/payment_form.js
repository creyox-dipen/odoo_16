odoo.define('cr_payment_eupago.payment_form', require => {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const manageForm = require('payment.manage_form');
    const core = require('web.core');
    const _t = core._t;

    const paymentMixin = {
        _prepareInlineForm: function (providerCode, paymentOptionId, flow) {
            console.log('[euPago] _prepareInlineForm called:', { providerCode, paymentOptionId, flow });
            if (providerCode !== 'eupago_mbway') {
                return this._super(...arguments);
            } else if (flow === 'token') {
                console.log('[euPago] Flow is token, skipping direct payment setup');
                return Promise.resolve();
            }
            console.log('[euPago] Setting payment flow to direct for MB WAY');
            this._setPaymentFlow('direct');
            return Promise.resolve();
        },

        _processDirectPayment: function (providerCode, paymentOptionId, processingValues) {
            console.log('[euPago] _processDirectPayment called:', { providerCode, paymentOptionId, processingValues });
            if (providerCode !== 'eupago_mbway') {
                return this._super(...arguments);
            }

            const phoneInput = document.getElementById('cr_eupago_phone');
            const phone = phoneInput ? phoneInput.value.trim().replace(/\s+/g, '') : '';
            console.log('[euPago] Extracted phone number:', phone);
            
            if (!phone || !/^[0-9]{9}$/.test(phone)) {
                console.warn('[euPago] Invalid phone number provided');
                this._displayErrorDialog(_t("Invalid Phone Number"), _t("Please enter a valid 9-digit phone number."));
                this._enableButton();
                return Promise.resolve();
            }

            console.log('[euPago] Making RPC call to process MB WAY payment...');
            // Call our custom controller to process the MB WAY payment
            return this._rpc({
                route: '/payment/cr_eupago/mbway/pay',
                params: {
                    'reference': processingValues.reference,
                    'phone': phone,
                }
            }).then(() => {
                console.log('[euPago] RPC call successful. Switching UI to pending state...');
                // Switch view to pending notification
                const container = document.querySelector('.o_cr_eupago_mbway_container');
                if (container) {
                    const phoneForm = container.querySelector('.o_cr_eupago_mbway_phone_form');
                    if (phoneForm) {
                        phoneForm.classList.add('d-none');
                    }
                    const pendingDiv = container.querySelector('.o_cr_eupago_mbway_pending');
                    if (pendingDiv) {
                        pendingDiv.classList.remove('d-none');
                        const phoneStrong = pendingDiv.querySelector('strong');
                        if (phoneStrong) {
                            phoneStrong.textContent = phone;
                        }
                    }
                }

                // Start polling for payment status
                console.log('[euPago] Starting to poll for payment status for reference:', processingValues.reference);
                this._eupagoPollMbwayStatus(processingValues.reference);
            }).catch(error => {
                console.error('[euPago] RPC call failed:', error);
                if (error && error.message) {
                    this._displayErrorDialog(_t("Payment processing failed"), error.message.data ? error.message.data.message : error.message);
                } else {
                    this._displayErrorDialog(_t("Payment processing failed"), _t("Unknown error"));
                }
                this._enableButton();
                return Promise.reject(error);
            });
        },

        _eupagoPollMbwayStatus: function (reference) {
            console.log('[euPago] Initializing polling mechanism for MB WAY...');
            const MAX_POLL_ATTEMPTS = 60;
            let attempts = 0;

            const pollInterval = setInterval(() => {
                attempts++;
                console.log(`[euPago] Polling attempt ${attempts}/${MAX_POLL_ATTEMPTS} for reference:`, reference);

                if (attempts >= MAX_POLL_ATTEMPTS) {
                    clearInterval(pollInterval);
                    console.warn('[euPago] Polling timeout reached. Redirecting to status page.');
                    window.location = '/payment/status';
                    return;
                }

                this._rpc({
                    route: '/payment/cr_eupago/mbway/status',
                    params: { 'ref': reference }
                }).then(response => {
                    console.log('[euPago] Polling response received:', response);
                    if (response.state === 'done') {
                        console.log('[euPago] Payment marked as done. Redirecting...');
                        clearInterval(pollInterval);
                        window.location = '/payment/status';
                    } else if (response.state && response.state !== 'pending' && response.state !== 'draft') {
                        console.log('[euPago] Payment reached a final state:', response.state, 'Redirecting...');
                        clearInterval(pollInterval);
                        window.location = '/payment/status';
                    }
                }).catch((error) => {
                    console.warn('[euPago] Transient error during polling:', error);
                    // Ignore transient RPC errors during polling
                });
            }, 5000);
        }
    };

    checkoutForm.include(paymentMixin);
    manageForm.include(paymentMixin);
});
