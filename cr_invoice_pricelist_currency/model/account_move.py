# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import api, fields, models

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange('partner_id')
    def update_currency_according_to_customer_pricelist(self):
        if self.partner_id:
            self.currency_id = self.partner_id.property_product_pricelist.currency_id
