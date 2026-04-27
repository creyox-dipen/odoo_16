# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models,api, _


class account_payment(models.TransientModel):
    _inherit = 'account.payment.register'

    manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    manual_currency_rate = fields.Float('Rate', digits=(12, 6))

    @api.model
    def default_get(self, default_fields):
        rec = super(account_payment, self).default_get(default_fields)
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        active_model = self._context.get('active_model')

        # Check for selected invoices ids
        if not active_ids or active_model != 'account.move':
            return rec
        invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda move: move.is_invoice(include_receipts=True))
        for move in invoices:
            rec.update({
                'manual_currency_rate_active': move.manual_currency_rate_active,
                'manual_currency_rate': move.manual_currency_rate
            })
        return rec

    def _create_payment_vals_from_wizard(self,first_batch_result):
        res = super(account_payment, self)._create_payment_vals_from_wizard(first_batch_result)
        if self.manual_currency_rate_active:
            res.update({'manual_currency_rate_active': self.manual_currency_rate_active, 'manual_currency_rate': self.manual_currency_rate})
        return res

class AccountPayment(models.Model):
    _inherit = "account.payment"
    _description = "Payments"

    is_company_currency = fields.Boolean(compute="_get_company_amount",store=True)
    
    @api.onchange('amount','currency_id','manual_currency_rate_active','manual_currency_rate')
    @api.depends('amount','currency_id','manual_currency_rate_active','manual_currency_rate')
    def _get_company_amount(self):
        for rec in self:
            rec.is_company_currency = True
            # rec.company_amount = 0
            if rec.env.user.company_id.currency_id.id != rec.currency_id.id:
                rec.is_company_currency = False
                
                # if rec.manual_currency_rate > 0 and rec.amount:
                #     rec.company_amount = rec.amount * rec.manual_currency_rate
                # else:
                #     rec.company_amount = 0
            else:
                rec.manual_currency_rate_active = False

    def write(self,vals):
        res = super(AccountPayment, self).write(vals)

        for rec in self:
            if rec.manual_currency_rate_active:
                for line in rec.line_ids:
                    line._compute_currency_rate()
                    line._compute_amount_currency()
                    
          
        
        return res
    
    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super()._get_trigger_fields_to_synchronize()
        
        res = res + ('manual_currency_rate_active','manual_currency_rate')
       
        return res
        

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Compute amounts.
        write_off_line_vals_list = write_off_line_vals or []
        write_off_amount = write_off_line_vals.get('amount', 0.0)

        if self.payment_type == 'inbound':
            # Receive money.
            counterpart_amount = -self.amount
            write_off_amount *= -1
        elif self.payment_type == 'outbound':
            # Send money.
            counterpart_amount = self.amount
        else:
            counterpart_amount = 0.0
            write_off_amount = 0.0

        if self.manual_currency_rate_active:
            currency_rate = self.company_id.currency_id.rate / self.manual_currency_rate
            balance = counterpart_amount / currency_rate
            counterpart_amount_currency = counterpart_amount
            write_off_balance = write_off_amount / currency_rate
            write_off_amount_currency = write_off_amount
            currency_id = self.currency_id.id
        else:
            balance = self.currency_id._convert(counterpart_amount, self.company_id.currency_id, self.company_id, self.date)
            counterpart_amount_currency = counterpart_amount
            write_off_balance = self.currency_id._convert(write_off_amount, self.company_id.currency_id, self.company_id, self.date)
            write_off_amount_currency = write_off_amount
            currency_id = self.currency_id.id
        
        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                liquidity_line_name = _('Transfer to %s', self.journal_id.name)
            else:  # payment.payment_type == 'outbound':
                liquidity_line_name = _('Transfer from %s', self.journal_id.name)
        else:
            liquidity_line_name = self.payment_reference

        # Compute a default label to set on the journal items.

        payment_display_name = {
            'outbound-customer': _("Customer Reimbursement"),
            'inbound-customer': _("Customer Payment"),
            'outbound-supplier': _("Vendor Payment"),
            'inbound-supplier': _("Vendor Reimbursement"),
        }
        payment_type = self.payment_type
        partner_type = self.partner_type
        if partner_type == 'employee':
            partner_type = 'supplier'

        default_line_name = ''.join(x[1] for x in self._get_liquidity_aml_display_name_list())

        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name or default_line_name,
                'date_maturity': self.date,
                'amount_currency': -counterpart_amount_currency,
                'currency_id': currency_id,
                'debit': balance < 0.0 and -balance or 0.0,
                'credit': balance > 0.0 and balance or 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': self.payment_reference or default_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency + write_off_amount_currency if currency_id else 0.0,
                'currency_id': currency_id,
                'debit': balance + write_off_balance > 0.0 and balance + write_off_balance or 0.0,
                'credit': balance + write_off_balance < 0.0 and -balance - write_off_balance or 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]
        if write_off_balance:
            # Write-off line.
            line_vals_list.append({
                'name': write_off_line_vals.get('name') or default_line_name,
                'amount_currency': -write_off_amount_currency,
                'currency_id': currency_id,
                'debit': write_off_balance < 0.0 and -write_off_balance or 0.0,
                'credit': write_off_balance > 0.0 and write_off_balance or 0.0,
                'partner_id': self.partner_id.id,
                'account_id': write_off_line_vals.get('account_id'),
            })
        return line_vals_list + write_off_line_vals_list
