odoo.define('cr_payment_eupago.payment_fees_badge', require => {
    'use strict';

    const checkoutForm = require('payment.checkout_form');
    const manageForm = require('payment.manage_form');

    const feesMixin = {
        _prepareInlineForm: function (providerCode, paymentOptionId, flow) {
            console.log('[euPago Badge] _prepareInlineForm triggered for provider:', providerCode);
            const def = this._super(...arguments);
            
            // Only process euPago providers
            if (!['eupago_cc', 'eupago_mbway', 'eupago_mbref'].includes(providerCode)) {
                return def;
            }

            const radio = document.querySelector('input[name="o_payment_radio"]:checked');
            if (!radio) {
                console.log('[euPago Badge] No active radio button found, aborting badge setup.');
                return def;
            }

            // Using this._rpc instead of this.rpc for Odoo 16
            const self = this;
            return def.then(() => {
                return self._fetchEupagoProviderConfig(providerCode).then(providerData => {
                    if (!providerData) return;
                    return self._fetchEupagoCountryData(providerData).then(countryData => {
                        console.log('[euPago Badge] Provider and country data fetched successfully:', { providerData, countryData });
                        const companyCountryId = countryData.companyCountryId;
                        const deliveryCountryId = countryData.deliveryCountryId;

                        if (providerData.cr_eupago_is_extra_fees) {
                            console.log('[euPago Badge] Provider HAS extra fees enabled. Calculating base amount...');
                            let amountStr = null;
                            const totalSummaryEl = document.getElementById('amount_total_summary');
                            if (totalSummaryEl) {
                                const oeSpan = totalSummaryEl.querySelector('.oe_currency_value');
                                amountStr = oeSpan ? oeSpan.textContent : totalSummaryEl.textContent;
                            } else {
                                amountStr = self.txContext ? self.txContext.amount : "0";
                                amountStr = amountStr.toString();
                            }
                            
                            console.log('[euPago Badge] Raw amount string before parsing:', amountStr);

                            if (typeof amountStr === 'string') {
                                amountStr = amountStr.replace(/\s+/g, '').replace(/&nbsp;/g, '').replace(/[^\d.,]/g, '');
                                if (amountStr.includes(',') && !amountStr.includes('.')) {
                                    amountStr = amountStr.replace(',', '.');
                                } else if (amountStr.includes(',') && amountStr.includes('.')) {
                                    if (amountStr.lastIndexOf(',') > amountStr.lastIndexOf('.')) {
                                        amountStr = amountStr.replace(/\./g, '').replace(',', '.');
                                    } else {
                                        amountStr = amountStr.replace(/,/g, '');
                                    }
                                }
                            }

                            let baseAmount = parseFloat(amountStr);
                            if (isNaN(baseAmount)) {
                                console.warn('[euPago Badge] Failed to parse amount, defaulting to 0');
                                baseAmount = 0;
                            }
                            console.log('[euPago Badge] Parsed base amount for fee calculation:', baseAmount);

                            const calculatedFees = self._calculateEupagoFees(
                                baseAmount, providerData, companyCountryId, deliveryCountryId
                            );

                            console.log('[euPago Badge] Calculated final fees:', calculatedFees);

                            if (calculatedFees > 0) {
                                self._displayEupagoFeeBadge(radio, calculatedFees, providerData);
                            } else {
                                console.log('[euPago Badge] Fees are 0, not displaying badge.');
                            }
                        }
                    });
                });
            });
        },

        _fetchEupagoProviderConfig: function (providerCode) {
            return this._rpc({
                route: '/custom/eupago/provider_config',
                params: { provider_code: providerCode }
            }).then(provider => {
                if (!provider || !provider.company_id) {
                    return null;
                }
                return provider;
            }).catch(e => {
                return null;
            });
        },

        _fetchEupagoCountryData: function (provider) {
            let companyCountryId = null;
            let deliveryCountryId = null;
            const self = this;

            const companyDef = this._rpc({
                route: '/custom/eupago/company_country/' + (provider.company_id[0] || provider.company_id),
                params: {}
            }).then(data => {
                companyCountryId = data ? data.country_id : null;
            }).catch(e => {});

            const docInfo = this._extractEupagoDocumentInfo();
            const endpoint = docInfo.docId 
                ? '/custom/eupago/document_shipping_country/' + docInfo.docId 
                : '/custom/eupago/document_shipping_country';

            const deliveryDef = this._rpc({
                route: endpoint,
                params: { is_invoice: docInfo.isInvoice }
            }).then(data => {
                deliveryCountryId = data ? data.country_id : null;
            }).catch(e => {});

            return Promise.all([companyDef, deliveryDef]).then(() => {
                return { companyCountryId: companyCountryId, deliveryCountryId: deliveryCountryId };
            });
        },

        _extractEupagoDocumentInfo: function () {
            if (this.txContext && this.txContext.transactionRoute) {
                const isInvoice = this.txContext.transactionRoute.includes('/invoice/');
                const matches = this.txContext.transactionRoute.match(/\/transaction\/(\d+)/);
                const docId = matches && matches[1] ? parseInt(matches[1]) : null;
                return { docId: docId, isInvoice: isInvoice };
            }
            return { docId: null, isInvoice: false };
        },

        _calculateEupagoFees: function (baseAmount, provider, companyCountryId, deliveryCountryId) {
            const isInternational = deliveryCountryId && companyCountryId && deliveryCountryId !== companyCountryId;
            console.log('[euPago Badge] isInternational logic:', { deliveryCountryId, companyCountryId, isInternational });
            
            let totalFixedFees = 0;
            let totalPercentFees = 0;
            
            if (isInternational) {
                console.log('[euPago Badge] Applying INTERNATIONAL fee logic');
                if (!provider.cr_eupago_is_free_international) {
                    totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                    totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
                } else if (baseAmount < (provider.cr_eupago_free_international_amount || 0)) {
                    totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                    totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
                } else {
                    console.log('[euPago Badge] International amount is above free threshold. No fees applied.');
                }
            } else {
                console.log('[euPago Badge] Applying DOMESTIC fee logic');
                if (!provider.cr_eupago_is_free_domestic) {
                    totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                    totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
                } else if (baseAmount < (provider.cr_eupago_free_domestic_amount || 0)) {
                    totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                    totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
                } else {
                    console.log('[euPago Badge] Domestic amount is above free threshold. No fees applied.');
                }
            }
            console.log(`[euPago Badge] Fees computed -> Fixed: ${totalFixedFees}, Percentage computed: ${totalPercentFees}`);
            return Math.round((totalFixedFees + totalPercentFees) * 100) / 100;
        },

        _displayEupagoFeeBadge: function (radio, calculatedFees, providerData) {
            if (!radio) return;
            const container = radio.parentElement;
            if (!container) return;

            const existingBadge = container.querySelector('.eupago-fees-badge');
            if (existingBadge) {
                existingBadge.remove();
            }

            const currencyId = this.txContext ? parseInt(this.txContext.currencyId) : null;
            if (currencyId) {
                this._rpc({
                    model: 'res.currency',
                    method: 'read',
                    args: [[currencyId], ['symbol']]
                }).then(result => {
                    const currencySymbol = (result && result.length > 0) ? result[0].symbol : '€';
                    this._appendBadge(container, currencySymbol, calculatedFees);
                }).catch(() => {
                    this._appendBadge(container, '€', calculatedFees);
                });
            } else {
                this._appendBadge(container, '€', calculatedFees);
            }
        },

        _appendBadge: function (container, currencySymbol, calculatedFees) {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary ms-2 eupago-fees-badge';
            badge.style.fontSize = '12px';
            badge.style.padding = '3px 8px';
            badge.textContent = `+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees`;

            const label = container.querySelector('.o_payment_option_label') || container.querySelector('label');
            if (label) {
                label.appendChild(badge);
            } else {
                container.appendChild(badge);
            }
        }
    };

    checkoutForm.include(feesMixin);
    manageForm.include(feesMixin);
});
