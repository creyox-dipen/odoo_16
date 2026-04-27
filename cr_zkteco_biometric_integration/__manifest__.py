# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
{
    "name": "ZKTeco Biometric Integration",
    "author": "Creyox Technologies",
    "website": "https://www.creyox.com",
    "support": "support@creyox.com",
    "category": "Extra Tools",
    "summary": """
    ZKTeco Biometric ADMS Live Attendance Integration for Odoo 16.
    """,
    # "license": "OPL-1",
    "version": "16.0.0.0",
    "description": """
    Zkteco Biometric Integration
    """,
    "depends": ["base", "hr_attendance", "mail"],
    # 'external_dependencies': {
    #     'python': ['pyzk']
    # },
    "data": [
        "security/ir.model.access.csv",
        "views/biometric_device_config.xml",
        "views/biometric_attendance_log.xml",
        "views/hr_employee.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
    # "price": 0.00,
    # "currency": "USD",
}
