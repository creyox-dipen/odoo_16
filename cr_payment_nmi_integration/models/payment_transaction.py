# -*- coding: utf-8 -*-
# Part of Creyox Technologies

import logging
import urllib.parse
import time

from odoo import _, api, models
from odoo.exceptions import ValidationError

from odoo.addons.cr_payment_nmi_integration.controllers.main import NmiController


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    """Extends the payment.transaction model with NMI-specific logic.
    
    Compatible with Odoo 17 CE.
    """

    _inherit = 'payment.transaction'

    def _get_specific_processing_values(self, processing_values):
        """Override to add NMI-specific processing values."""
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'nmi':
            return res

        if self.payment_method_code == 'ach_direct_debit':
            res.update({
                'reference': self.reference,
                'amount': self.amount,
                'partner_name': self.partner_name,
                'ach_process_url': NmiController._ach_process_url,
            })
        return res

    def _get_specific_rendering_values(self, processing_values):
        """Override to build provider-specific rendering values.

        NMI uses a direct flow via custom controllers. We return an empty dict
        to signal Odoo to use _processDirectFlow and skip the redirect form.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'nmi':
            return res
        return res

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override to find a transaction from incoming NMI notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)

        if provider_code != 'nmi' or len(tx) == 1:
            return tx

        if notification_data.get('_ach_flow'):
            reference = notification_data.get('orderid') or notification_data.get('reference')
        else:
            reference = notification_data.get('ekashu_reference')

        if not reference:
            raise ValidationError("Nmi: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'nmi')])
        if not tx:
            raise ValidationError("Nmi: " + _("No transaction found matching reference %s.", reference))
        return tx

    def _process_notification_data(self, notification_data):
        """Override to update the transaction state from NMI notification data."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'nmi':
            return

        # Synchronize transaction amount if a surcharge was applied
        amount = notification_data.get('amount') or notification_data.get('ekashu_amount')
        if amount:
            float_amount = float(amount)
            if notification_data.get('_ach_flow') and float_amount != self.amount:
                self.sudo().write({'amount': float_amount})

        # ---- ACH Direct Post response ----------------------------------------
        if notification_data.get('_ach_flow'):
            response_code = notification_data.get('response')
            response_text = notification_data.get('responsetext', 'Unknown error')
            transaction_id = notification_data.get('transactionid', '')

            if not response_code:
                raise ValidationError("NMI ACH: " + _("Received response with missing status code."))

            if response_code == '1':
                # Approved
                self.provider_reference = transaction_id
                self._set_done()
                if self.tokenize:
                    self._tokenize_from_notification_data(notification_data)
                _logger.info("ACH transaction %s approved (id=%s).", self.reference, transaction_id)
            elif response_code == '2':
                # Declined
                _logger.warning("ACH transaction %s declined: %s", self.reference, response_text)
                self._set_canceled()
            else:
                # Error
                _logger.warning("ACH transaction %s failed: %s", self.reference, response_text)
                self._set_error("NMI ACH: " + response_text)
            return

        # ---- Ekashu card callback --------------------------------------------
        auth_result = notification_data.get('ekashu_auth_result')
        if not auth_result:
            raise ValidationError("NMI: " + _("Received data with missing status code."))

        if auth_result == 'success':
            self.provider_reference = notification_data.get('ekashu_reference', self.reference)
            self._set_done()
            if self.tokenize:
                self._tokenize_from_notification_data(notification_data)
        else:
            _logger.warning("Invalid auth result (%s) for %s.", auth_result, self.reference)
            self._set_error("NMI: " + _("Unknown success code: %s", auth_result))

    # ===== TOKENIZATION HELPERS (Odoo 17 local methods) =====

    def _tokenize_from_notification_data(self, notification_data):
        """Local helper to create a payment token for NMI."""
        self.ensure_one()
        token_values = self._extract_token_values(notification_data)
        if not token_values.get('provider_ref'):
             _logger.warning("NMI: Tokenization requested but no vault ID found.")
             return

        token_values.update({
            'provider_id': self.provider_id.id,
            'payment_method_id': self.payment_method_id.id,
            'partner_id': self.partner_id.id,
        })
        token = self.env['payment.token'].create(token_values)
        self.write({'token_id': token.id, 'tokenize': False})
        _logger.info("NMI: Created token %s for %s.", token.id, self.reference)

    def _extract_token_values(self, payment_data):
        """Extract NMI token values from notification data."""
        vault_id = payment_data.get('customer_vault_id')
        if not vault_id:
            return {}

        if payment_data.get('ccnumber_last4'):
            token_name = _("Card ending in %s", payment_data['ccnumber_last4'])
        else:
            account_no = payment_data.get('checkaccount', '')
            last_4 = account_no[-4:] if len(account_no) >= 4 else account_no
            token_name = _("ACH account ending in %s", last_4) if last_4 else _("ACH account")

        return {
            'provider_ref': vault_id,
            'payment_details': token_name,
            'nmi_card_type': payment_data.get('card_type', 'unknown'),
        }

    # ===== SERVER-SIDE PAYMENTS =====

    def _send_payment_request(self):
        """Override to send a token payment request to NMI Direct Post."""
        super()._send_payment_request()
        if self.provider_code != 'nmi':
            return

        if not self.token_id:
            raise ValidationError("NMI: " + _("No token provided."))

        provider = self.provider_id
        amount_to_charge = self.amount
        surcharge_amount = 0.0
        
        # Surcharge logic for Saved Cards
        fee_percentage = 0.0
        fee_product_code = ''
        fee_label = ''
        
        if self.token_id.nmi_card_type in ('credit', 'charge') and provider.is_nmi_card_fee and provider.nmi_credit_card_fee > 0:
            fee_percentage = provider.nmi_credit_card_fee
            fee_product_code = 'CREDIT_CARD_FEE'
            fee_label = "Credit Card Surcharge"
        elif self.token_id.nmi_card_type == 'debit' and provider.is_nmi_card_fee and provider.nmi_debit_card_fee > 0:
            fee_percentage = provider.nmi_debit_card_fee
            fee_product_code = 'DEBIT_CARD_FEE'
            fee_label = "Debit Card Surcharge"

        if fee_percentage > 0:
            surcharge_amount = self.currency_id.round((self.amount * fee_percentage) / 100)
            amount_to_charge = self.amount + surcharge_amount
            
            for order in self.sale_order_ids:
                fee_product = self.env['product.product'].sudo().search([('default_code', '=', fee_product_code)], limit=1)
                existing_fee_line = order.order_line.filtered(lambda l: "Surcharge" in l.name)
                if not existing_fee_line:
                    self.env['sale.order.line'].sudo().create({
                        'order_id': order.id,
                        'name': f"{fee_label} ({fee_percentage}%)",
                        'product_id': fee_product.id if fee_product else False,
                        'product_uom_qty': 1,
                        'price_unit': surcharge_amount,
                        'sequence': 999,
                    })
                else:
                    existing_fee_line.sudo().write({'price_unit': surcharge_amount})
            
            self.sudo().write({'amount': amount_to_charge})

        # Build payload
        attempt_orderid = '%s_%d' % (self.reference, int(time.time()))
        post_payload = {
            'security_key': provider.nmi_security_key,
            'type': 'sale',
            'customer_vault_id': self.token_id.provider_ref,
            'amount': "{:.2f}".format(amount_to_charge),
            'surcharge': "{:.2f}".format(surcharge_amount) if surcharge_amount > 0 else '',
            'orderid': attempt_orderid,
            'currency': self.currency_id.name or 'USD',
        }

        try:
            import requests as http_requests
            nmi_response = http_requests.post(provider._nmi_get_direct_post_url(), data=post_payload, timeout=30)
            nmi_response.raise_for_status()
        except Exception as e:
            raise ValidationError("NMI: Connection error — %s" % str(e))

        result = dict(urllib.parse.parse_qsl(nmi_response.text))
        result['_ach_flow'] = True
        result['amount'] = result.get('amount') or post_payload.get('amount')
        result['currency'] = result.get('currency') or post_payload.get('currency')
        self._handle_notification_data('nmi', result)
