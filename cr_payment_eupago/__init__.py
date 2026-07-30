# -*- coding: utf-8 -*-
# -*- Part of Creyox Technologies -*-

from . import controllers
from . import models
from . import wizard

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(cr, registry):
    setup_provider(cr, registry, "eupago_mbref")
    setup_provider(cr, registry, "eupago_mbway")
    setup_provider(cr, registry, "eupago_cc")


def uninstall_hook(cr, registry):
    reset_payment_provider(cr, registry, "eupago_mbref")
    reset_payment_provider(cr, registry, "eupago_mbway")
    reset_payment_provider(cr, registry, "eupago_cc")
