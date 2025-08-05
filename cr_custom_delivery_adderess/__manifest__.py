# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    'name': 'cr_custom_delivery_address',
    'author': 'Creyox Technologies',
    "website": "https://www.creyox.com",
    'support': 'support@creyox.com',
    'category': 'accounting',
    'summary': """
    Custom Delivery Address
    """,
    "license": "OPL-1",
    "version": "18.0",
    'description': """
    Custom Delivery Address
    """,
    'depends': ['base', 'sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/stock_picking.xml',
        'views/account_move.xml',
        'reports/sale_order_report.xml',
        'reports/invoice_report.xml',
        'reports/delivery_report.xml',
    ],
    # 'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    # "price": '',
    # 'currency': 'USD'
}
