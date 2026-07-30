# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.addons.cr_payment_eupago import const

_logger = logging.getLogger(__name__)


class EupagoRefundWizard(models.TransientModel):
    _name = "cr.eupago.refund.wizard"
    _description = "euPago Refund Wizard"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
    )
    transaction_id = fields.Many2one(
        "payment.transaction",
        string="euPago Transaction",
        required=True,
    )
    currency_id = fields.Many2one(
        related="move_id.currency_id",
        string="Currency",
    )
    amount_to_refund = fields.Monetary(
        string="Refund Amount",
        currency_field="currency_id",
        required=True,
    )

    def action_confirm_refund(self):
        self.ensure_one()
        
        # Validate invoice payment state
        if self.move_id.payment_state not in ("paid", "in_payment"):
            raise UserError(_("You can only refund paid invoices."))

        # 1. Validations
        if self.amount_to_refund <= 0:
            raise UserError(_("Refund amount must be strictly positive."))
            
        if self.amount_to_refund > self.transaction_id.amount:
            raise UserError(_("You cannot refund more than the original transaction amount."))
            
        if self.transaction_id.provider_code not in (const.PROVIDER_CODE_CC, const.PROVIDER_CODE_MBWAY):
            raise UserError(_("Only euPago Credit Card and MB WAY transactions can be refunded via API."))

        _logger.info(
            "Initiating euPago refund for invoice %s. Amount: %s",
            self.move_id.name,
            self.amount_to_refund,
        )

        # 2. Create Refund Transaction
        try:
            refund_tx = self.env["payment.transaction"].create({
                "amount": -self.amount_to_refund,  # Refund tx amounts are negative in Odoo
                "currency_id": self.currency_id.id,
                "partner_id": self.transaction_id.partner_id.id,
                "provider_id": self.transaction_id.provider_id.id,
                "payment_method_id": self.transaction_id.payment_method_id.id,
                "operation": "refund",
                "source_transaction_id": self.transaction_id.id,
                "payment_id": False, # CRITICAL: prevent inheriting the charge's payment_id
                "reference": self.env["payment.transaction"]._compute_reference(
                    self.transaction_id.provider_code, prefix=self.transaction_id.reference
                ),
            })
            
            # 3. Call euPago API
            refund_tx._send_refund_request()
            
            # 4. Trigger post-processing and create Credit Note
            if refund_tx.state == "done":
                # Credit Note is already created and posted by _generate_refund_credit_note()
                # which is triggered inside _set_done() → no need to create it again here.
                # Retrieve the Credit Note that was linked to refund_tx.invoice_ids.
                credit_note = refund_tx.invoice_ids.filtered(
                    lambda inv: inv.move_type == "out_refund" and inv.state == "posted"
                )[:1]

                if not credit_note:
                    _logger.info("euPago wizard: no posted Credit Note found on refund_tx %s — skipping payment registration", refund_tx.reference)
                else:
                    _logger.info("euPago wizard: using Credit Note %s for payment registration", credit_note.name)

                    # CRITICAL: Clear any inherited payment_id from the original charge transaction.
                    # Odoo copies the source_transaction's payment_id to refund_tx, so we must
                    # clear it to prevent pointing to the original inbound payment.
                    refund_tx.sudo().payment_id = False

                    # The Credit Note is already created and posted by _generate_refund_credit_note()
                    # which ran inside _set_done(). For a euPago API refund, the money goes back
                    # to the customer via euPago — there is no separate Odoo payment entry to create.
                    # Trigger Odoo's native post-processing for the transaction.
                    # CRITICAL: We MUST clear default_move_id from the context. 
                    # The wizard was opened with default_move_id=invoice.id.
                    # If we don't clear it, account.payment.create() will try to use the existing 
                    # invoice move instead of creating a new one, causing a journal edit error!
                    if not refund_tx.is_post_processed:
                        refund_tx.with_context(default_move_id=False)._finalize_post_processing()
                        _logger.info(
                            "euPago wizard: successfully completed post-processing for refund tx %s (Credit Note %s reconciled)",
                            refund_tx.reference,
                            credit_note.name,
                        )
            
        except UserError:
            # Re-raise standard Odoo errors (like our own UserError)
            raise
        except Exception as e:
            _logger.error("euPago refund error: %s", e)
            raise UserError(_("euPago refund failed:\n%s", str(e)))

        return {"type": "ir.actions.act_window_close"}
