# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "Merge Duplicate Data Extended",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Sales",
    "summary": """
       The Merge Duplicate Data Extended module helps you keep your Odoo database clean by finding and managing duplicate records in any model. Users can search for duplicates based on the fields they select, either across all records or only within the selected ones. Once duplicates are identified, you can easily merge them into a single original record, and the system will automatically update all references of the duplicate with the original record throughout Odoo.

        This module also gives you flexibility in handling duplicate records after merging—you can choose to delete them, archive them, or simply leave them unchanged. In addition, access rights are fully controlled by the admin, who can decide which users have permission to merge duplicate data. With this, you ensure only authorized users can perform sensitive merge operations while maintaining accurate, consistent, and reliable data across your entire Odoo system.
    """,
    "license": "OPL-1",
    "version": "16.0",
    "description": """
        The Merge Duplicate Data Extended module helps you keep your Odoo database clean by finding and managing duplicate records in any model. Users can search for duplicates based on the fields they select, either across all records or only within the selected ones. Once duplicates are identified, you can easily merge them into a single original record, and the system will automatically update all references of the duplicate with the original record throughout Odoo.

        This module also gives you flexibility in handling duplicate records after merging—you can choose to delete them, archive them, or simply leave them unchanged. In addition, access rights are fully controlled by the admin, who can decide which users have permission to merge duplicate data. With this, you ensure only authorized users can perform sensitive merge operations while maintaining accurate, consistent, and reliable data across your entire Odoo system.
    """,
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/merge_access.xml",
        "views/res_partner.xml",
        "views/find_duplicate_wiz.xml",
        "views/merge_menu.xml",
    ],
    # "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "price": 40,
    "currency": "USD",
}
