# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    currency_sync_api_key = fields.Char(string="Sync Currency Key")