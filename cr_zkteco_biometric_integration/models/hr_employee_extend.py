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

    def action_sync_to_devices(self, device_ids=None):
        self.ensure_one()
        if not self.device_user_id:
            return
    
        if device_ids:
            devices = self.env["biometric.device"].sudo().browse(device_ids)
        else:
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

    def action_open_enroll_wizard(self):
        self.ensure_one()
        return {
            'name': 'Remote Biometric Enrollment',
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.enroll.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
            }
        }

    def action_open_transfer_wizard(self):
        self.ensure_one()
        return {
            'name': 'Transfer to Devices',
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.user.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
            }
        }

    def _process_biometric_punch(self, device, utc_dt, punch_type):
        """
        Processes a single punch for this employee and updates hr.attendance.
        Returns True if successful, False otherwise.
        """
        self.ensure_one()
        Attendance = self.env["hr.attendance"].sudo()

        # 1. Rule: Min. Punch Interval
        if device.min_punch_interval > 0:
            last_attendance = Attendance.search([
                ("employee_id", "=", self.id)
            ], order="check_in desc", limit=1)
            
            last_time = False
            if last_attendance:
                last_time = last_attendance.check_out or last_attendance.check_in
            
            if last_time:
                import datetime
                diff = (utc_dt - last_time).total_seconds() / 60.0
                if abs(diff) < device.min_punch_interval:
                    return False

        if punch_type == "in":
            # Check for existing open attendance
            open_attendance = Attendance.search([
                ("employee_id", "=", self.id),
                ("check_out", "=", False),
            ], limit=1)
            if not open_attendance:
                Attendance.create({"employee_id": self.id, "check_in": utc_dt})
                return True
            return False
        
        elif punch_type == "out":
            open_attendance = Attendance.search([
                ("employee_id", "=", self.id),
                ("check_out", "=", False),
            ], order="check_in desc", limit=1)
            if open_attendance and utc_dt > open_attendance.check_in:
                open_attendance.write({"check_out": utc_dt})
                return True
            return False
            
        return False

    def _run_biometric_auto_checkout(self):
        """
        Finds open attendances for employees and closes them if auto-checkout is enabled on the device.
        """
        from datetime import datetime, time
        import pytz
        
        devices = self.env["biometric.device"].sudo().search([("auto_checkout", "=", True)])
        for device in devices:
            # We look for open attendances for employees linked to this device
            open_attendances = self.env["hr.attendance"].sudo().search([
                ("check_out", "=", False)
            ])
            
            for att in open_attendances:
                # Convert auto_checkout_time (float) to time object
                hours = int(device.auto_checkout_time)
                minutes = int((device.auto_checkout_time - hours) * 60)
                
                # We close it using the device timezone's "today at X time"
                tz = pytz.timezone(device.timezone or 'UTC')
                
                # Ensure the check_in date is used
                checkout_dt_tz = tz.localize(datetime.combine(att.check_in.date(), time(hours, minutes)))
                checkout_dt_utc = checkout_dt_tz.astimezone(pytz.UTC).replace(tzinfo=None)
                
                # Only close if it's currently later than the checkout time
                if datetime.now() > checkout_dt_utc and att.check_in < checkout_dt_utc:
                    _logger.info("Auto-Checkout: Closing attendance for %s at %s", att.employee_id.name, checkout_dt_utc)
                    att.write({"check_out": checkout_dt_utc})
