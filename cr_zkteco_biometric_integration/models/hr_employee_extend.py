# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields


class HrEmployeeExtend(models.Model):
    """
    Extends hr.employee to store the ZKTeco biometric device user ID.
    This field is used to match punch records received via ADMS to the
    correct Odoo employee.
    """

    _inherit = "hr.employee"

    device_user_id = fields.Char(
        string="Biometric User ID",
        index=True,
        copy=False,
        groups="hr.group_hr_user",
        help=(
            "The user ID enrolled on the ZKTeco biometric device. "
            "This is matched against incoming ADMS attendance punches "
            "to identify the employee."
        ),
    )
