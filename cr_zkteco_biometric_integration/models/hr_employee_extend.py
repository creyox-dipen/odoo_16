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

    biometric_template_ids = fields.One2many(
        comodel_name="biometric.user.template",
        inverse_name="employee_id",
        string="Biometric Templates",
        help="Fingerprint and Face templates stored for this employee.",
    )

    def action_sync_to_devices(self):
        self.ensure_one()
        if not self.device_user_id:
            return
    
        devices = self.env["biometric.device"].sudo().search([("active", "=", True)])
        Command = self.env["biometric.device.command"].sudo()
    
        for device in devices:
            # 1. Push User Info — fields TAB separated
            Command.create({
                "device_id": device.id,
                "command_text": (
                    f"DATA UPDATE UserInfo\t"
                    f"PIN={self.device_user_id}\t"
                    f"Name={self.name}\t"
                    f"Pri=0\t"
                    f"Passwd=\t"
                    f"Card=\t"
                    f"Grp=1\t"
                    f"TZ=0000000000000000000000000000\t"
                    f"Verify=0\t"
                    f"ViceCard="
                ),
            })
    
            # 2. Push Fingerprints / Face Templates
            for template in self.biometric_template_ids:
                if template.type == "finger":
                    # ✅ Fingerprint — table: FingerTmp, Type=1, TAB separated
                    cmd = (
                        f"DATA UPDATE FingerTmp\t"
                        f"PIN={self.device_user_id}\t"
                        f"FID={template.finger_index}\t"
                        f"Size={len(template.template_data)}\t"
                        f"Valid=1\t"
                        f"TMP={template.template_data}"
                    )
                else:
                    # ✅ Face — table: FaceTemp, Type=2, TAB separated
                    cmd = (
                        f"DATA UPDATE Face\t"
                        f"PIN={self.device_user_id}\t"
                        f"FID={template.finger_index}\t"
                        f"Size={len(template.template_data)}\t"
                        f"Valid=1\t"
                        f"TMP={template.template_data}"
                    )
    
                Command.create({
                    "device_id": device.id,
                    "command_text": cmd,
                })

    def action_request_templates_from_device(self):
        """
        Sends query commands without the DATA prefix.
        """
        self.ensure_one()
        if not self.device_user_id:
            return

        devices = self.env["biometric.device"].sudo().search([("active", "=", True)])
        Command = self.env["biometric.device.command"].sudo()
        for device in devices:
            # Using OpStamp=0 (based on device logs showing OpStamp usage)
            # 1. Fetch all User Info
            Command.create({"device_id": device.id, "command_text": "DATA QUERY UserInfo OpStamp=0"})
            
            # 2. Fetch all Fingerprints
            Command.create({"device_id": device.id, "command_text": "DATA QUERY FingerTmp OpStamp=0"})
            
            # 3. Fetch all Face Templates
            Command.create({"device_id": device.id, "command_text": "DATA QUERY Face OpStamp=0"})
