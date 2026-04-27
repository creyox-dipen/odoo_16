# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, api, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    currency_rate = fields.Float(string="Rate")

    @api.depends('journal_id', 'statement_line_id')
    def _compute_currency_id(self):
        for invoice in self:
            company = invoice.journal_id.company_id or invoice.company_id
            # Priority: Default company currency first
            currency = (

                    invoice.currency_id
                    or invoice.journal_id.currency_id
                    or invoice.statement_line_id.foreign_currency_id
                    or company.currency_id
            )
            invoice.currency_id = currency

    @api.onchange('partner_id')
    def update_currency_according_to_customer_pricelist(self):
        if self.partner_id:
            self.currency_id = self.partner_id.property_product_pricelist.currency_id