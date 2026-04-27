# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "USD INR Daily Sync",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "accounting",
    "summary": """
    USD INR Daily Sync
    """,
    "license": "OPL-1",
    "version": "16.0.0.0",
    "description": """
    USD INR Daily Sync
    """,
    "depends": ["base", "account"],
    "data": [
        "security/ir.model.access.csv",
        "views/fetch_currency_rate.xml",
        "views/res_company.xml",
        "views/account_move.xml",
    ],
    'post_init_hook' : 'my_post_init_hook',
    "installable": True,
    "application": True,
    "currency": "USD",
}
