# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    "name" : "HEMFA Currency Exchange Rate on Invoice/Payment/Sale/Purchase/Cheque/Landed Cost in Odoo",
    "version" : "16.0.0.1",
    "depends" : ['base','account',
    'purchase','sale_management',"stock_landed_costs",],
    "author": "BrowseInfo",
    "summary": "100_hemfa_bi_manual_currency_exchange_rate_R_D_16.0.0.1_2023.05.11 -Invoice manual Exchange Rate. -Payment Manual Exchange Rate. -  Sale manual Exchange Rate. -Purchase Manual Exchange Rate. -Cheque Manual Exchange Rate. -Landed Cost Manual Exchange Rate",
    "license": "AGPL-3",
    'category': 'Accounting',
    "website" : "https://www.browseinfo.in",
    "data" :[
             "views/customer_invoice.xml",
             "views/account_payment_view.xml",
             "views/purchase_view.xml",
             "views/sale_view.xml",
             "views/stock_landed_cost_view.xml",
             "views/res_config_settings_views.xml",
    ],
    'qweb':[
    ],
    "application": True,
    "auto_install": False,
    "installable": True,
    'live_test_url':'https://youtu.be/nRdIuuxi9yI',
	"images":['static/description/Banner.png'],
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
