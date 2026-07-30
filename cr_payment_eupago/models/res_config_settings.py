# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Patching the field to add the missing string attribute
    # which causes an UncaughtPromiseError in Settings view if missing.
    pay_invoices_online = fields.Boolean(string="Pay Invoices Online")
