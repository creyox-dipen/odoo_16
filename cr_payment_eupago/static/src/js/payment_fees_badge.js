/** @odoo-module **/

import paymentForm from '@payment/js/payment_form';

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        await this._super(...arguments);
        // Only process euPago providers
        if (!['eupago_cc', 'eupago_mbway', 'eupago_mbref'].includes(providerCode)) {
            return;
        }

        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        if (!radio) return;

        // Fetch provider configuration
        const providerData = await this._fetchEupagoProviderConfig(providerCode);
        if (!providerData) return;

        // Fetch country data
        const { companyCountryId, deliveryCountryId } = await this._fetchEupagoCountryData(providerData);

        // Calculate fees
        if (providerData.cr_eupago_is_extra_fees) {
            let amountStr = null;
            
            // On eCommerce checkout, the real total is in #amount_total_summary
            // this.paymentContext.amount sometimes incorrectly contains 0.00 in Odoo 17
            const totalSummaryEl = document.getElementById('amount_total_summary');
            if (totalSummaryEl) {
                const oeSpan = totalSummaryEl.querySelector('.oe_currency_value');
                amountStr = oeSpan ? oeSpan.textContent : totalSummaryEl.textContent;
            } else {
                amountStr = this.paymentContext.amount || "0";
                
                if (typeof amountStr === 'string' && amountStr.includes('<')) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = amountStr;
                    const oeSpan = tempDiv.querySelector('.oe_currency_value');
                    amountStr = oeSpan ? oeSpan.textContent : tempDiv.textContent;
                }
            }
            
            // Clean up the string to ensure it parses correctly across different locales (1,234.56 vs 1.234,56)
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
                baseAmount = 0;
            }

            const calculatedFees = this._calculateEupagoFees(
                baseAmount,
                providerData,
                companyCountryId,
                deliveryCountryId
            );

            if (calculatedFees > 0) {
                this._displayEupagoFeeBadge(radio, calculatedFees, providerData);
            }
        }
    },

    async _fetchEupagoProviderConfig(providerCode) {
        try {
            const provider = await this.rpc('/custom/eupago/provider_config', {
                provider_code: providerCode
            });
            
            if (!provider || !provider.company_id) {
                console.warn('[euPago Badge] No provider or missing company_id');
                return null;
            }
            return provider;
        } catch (e) {
            console.error('[euPago Badge] Could not fetch provider config:', e);
            return null;
        }
    },

    async _fetchEupagoCountryData(provider) {
        let companyCountryId = null;
        let deliveryCountryId = null;

        // Fetch company country
        try {
            const companyData = await this.rpc(`/custom/eupago/company_country/${provider.company_id[0] || provider.company_id}`, {});
            companyCountryId = companyData?.country_id || null;
        } catch (e) {
            console.error('[euPago Badge] Could not fetch company country:', e);
        }

        // Fetch delivery country
        const { docId, isInvoice } = this._extractEupagoDocumentInfo();
        try {
            const endpoint = docId 
                ? `/custom/eupago/document_shipping_country/${docId}` 
                : `/custom/eupago/document_shipping_country`;
            const docData = await this.rpc(endpoint, {
                is_invoice: isInvoice
            });
            deliveryCountryId = docData?.country_id || null;
        } catch (error) {
            console.error('[euPago Badge] Failed to fetch delivery country:', error);
        }

        return { companyCountryId, deliveryCountryId };
    },

    _extractEupagoDocumentInfo() {
        if (this.paymentContext.transactionRoute) {
            const isInvoice = this.paymentContext.transactionRoute.includes('/invoice/');
            const matches = this.paymentContext.transactionRoute.match(/\/transaction\/(\d+)/);
            const docId = matches?.[1] ? parseInt(matches[1]) : null;
            return { docId, isInvoice };
        }
        return { docId: null, isInvoice: false };
    },

    _calculateEupagoFees(baseAmount, provider, companyCountryId, deliveryCountryId) {
        const isInternational = deliveryCountryId && companyCountryId &&
                                deliveryCountryId !== companyCountryId;

        let totalFixedFees = 0;
        let totalPercentFees = 0;

        if (isInternational) {
            if (!provider.cr_eupago_is_free_international) {
                totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.cr_eupago_free_international_amount || 0)) {
                totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
            }
        } else {
            if (!provider.cr_eupago_is_free_domestic) {
                totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.cr_eupago_free_domestic_amount || 0)) {
                totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
            }
        }

        return Math.round((totalFixedFees + totalPercentFees) * 100) / 100;
    },

    _displayEupagoFeeBadge(radio, calculatedFees, providerData) {
        if (!radio) return;
        
        // Find the container associated with this radio button.
        // In Odoo 17, radio is inside a .w-100 flex container.
        const container = radio.parentElement;
        if (!container) return;

        // Remove any existing badge to avoid duplicates
        const existingBadge = container.querySelector('.eupago-fees-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        const currencyId = parseInt(this.paymentContext.currencyId);

        if (currencyId && this.orm) {
            this.orm.read('res.currency', [currencyId], ['symbol']).then(result => {
                const currencySymbol = result?.[0]?.symbol || '€';
                this._appendBadge(container, currencySymbol, calculatedFees);
            }).catch(e => {
                console.warn('[euPago Badge] Could not fetch currency symbol, using fallback', e);
                this._appendBadge(container, '€', calculatedFees);
            });
        } else {
            this._appendBadge(container, '€', calculatedFees);
        }
    },

    _appendBadge(container, currencySymbol, calculatedFees) {
        // Create badge
        const badge = document.createElement('span');
        badge.className = 'badge bg-primary ms-2 eupago-fees-badge';
        badge.style.fontSize = '12px';
        badge.style.padding = '3px 8px';
        badge.textContent = `+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees`;

        // Append badge next to the payment option label
        const label = container.querySelector('.o_payment_option_label') || container.querySelector('label');
        if (label) {
            label.appendChild(badge);
        } else {
            container.appendChild(badge);
        }
    }
});
