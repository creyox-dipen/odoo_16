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
    "license": "OPL-1",
    "version": "16.0.0.0",
    "description": """
    Zkteco Biometric Integration
    """,
    "depends": ["base", "hr_attendance", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/biometric_device_config.xml",
        "views/biometric_attendance_log.xml",
        "views/hr_employee.xml",
        "views/biometric_dashboard_view.xml",
        "views/menu.xml",
        "wizard/biometric_enroll_wizard_view.xml",
        "wizard/biometric_user_transfer_wizard_view.xml",
        "wizard/biometric_attendance_report_wizard_view.xml",
        "wizard/calculate_attendance_wizard_view.xml",
        "wizard/daily_summary_report_wizard_view.xml",
        "wizard/absence_report_wizard_view.xml",
        "wizard/daily_attendance_report_wizard_view.xml",
        "report/attendance_reports.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cr_zkteco_biometric_integration/static/src/xml/biometric_dashboard.xml",
            "cr_zkteco_biometric_integration/static/src/scss/biometric_dashboard.scss",
            "cr_zkteco_biometric_integration/static/src/js/biometric_dashboard.js",
        ],
    },
    "installable": True,
    "application": True,
    # "price": 0.00,
    # "currency": "USD",
}
