# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields

class BiometricUserTemplate(models.Model):
    """
    Stores biometric templates (fingerprints, face data) for an employee.
    These are mathematical representations used by the ZKTeco devices.
    """
    _name = "biometric.user.template"
    _description = "Biometric User Template"

    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
        required=True,
        ondelete="cascade",
    )
    device_user_id = fields.Char(
        related="employee_id.device_user_id",
        store=True,
        string="Device User ID",
    )
    type = fields.Selection(
        selection=[
            ("finger", "Fingerprint"),
            ("face", "Face"),
        ],
        string="Template Type",
        required=True,
    )
    template_data = fields.Text(
        string="Template Data",
        required=True,
        help="The raw mathematical string provided by the device.",
    )
    finger_index = fields.Integer(
        string="Index",
        default=0,
        help="For fingerprints, which finger (0-9). For face, usually 0.",
    )
    uid = fields.Integer(
        string="UID",
        help="Internal UID on the device (optional).",
    )
