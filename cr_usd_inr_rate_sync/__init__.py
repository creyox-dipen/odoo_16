# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from . import models
from odoo import api, SUPERUSER_ID

def my_post_init_hook(cr, registry):
    print("Transferring Rate ...")
    env = api.Environment(cr, SUPERUSER_ID, {})
    account_move_model = env['account.move']

    has_manual_rate_flag = 'manual_currency_rate_active' in account_move_model._fields
    has_manual_rate_value = 'manual_currency_rate' in account_move_model._fields

    if has_manual_rate_flag and has_manual_rate_value:
        moves = account_move_model.search([])
        for move in moves:
            if move.manual_currency_rate_active:
                move.currency_rate = move.manual_currency_rate
        print("currency rate transferred successfully.")
    else:
        print("Skipping post init hook: required fields not found on account.move.")
