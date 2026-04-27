# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class BiometricAttendanceLog(models.Model):
    """
    Stores a single raw attendance punch record received from a ZKTeco device
    via the ADMS HTTP push protocol.

    Each record corresponds to one line in an ATTLOG payload. Duplicates are
    prevented at the database level via a unique constraint on `unique_key`
    which is built from the device serial number, device user ID, and UTC timestamp.
    """

    _name = "biometric.attendance.log"
    _description = "Biometric Attendance Log"
    _order = "timestamp desc"
    _rec_name = "device_user_id"

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    device_id = fields.Many2one(
        comodel_name="biometric.device",
        string="Device",
        required=True,
        ondelete="cascade",
        index=True,
        help="The biometric device that sent this punch record.",
    )
    device_user_id = fields.Char(
        string="Device User ID",
        required=True,
        index=True,
        help="User ID as stored on the biometric device (matches hr.employee.device_user_id).",
    )
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
        compute="_compute_employee_id",
        store=True,
        index=True,
        help="Odoo employee matched to this punch via device_user_id.",
    )
    timestamp = fields.Datetime(
        string="Punch Time (UTC)",
        required=True,
        help="The punch timestamp converted to UTC from the device's local timezone.",
    )
    verify_state = fields.Selection(
        string="Verify State",
        selection=[
            ("0", "Check-in"),
            ("1", "Check-out"),
            ("4", "Check-in"),
            ("5", "Check-out"),
        ],
        help="Verification state (eg 0 - checkin, 1 - checkout, 4 - Overtime-In, 5 - Overtime-Out)",
    )
    status = fields.Selection(
        string="Status",
        selection=[
            ("new", "New"),
            ("processed", "Processed"),
            ("failed", "Failed"),
        ],
        default="new",
        index=True,
        help="Processing status of this attendance punch record.",
    )
    raw_data = fields.Text(
        string="Raw Data",
        help="The original tab-separated ATTLOG line as received from the device (for audit).",
    )
    unique_key = fields.Char(
        string="Unique Key",
        compute="_compute_unique_key",
        store=True,
        copy=False,
        index=True,
        help="Composite deduplication key: {serial_number}_{device_user_id}_{utc_timestamp}.",
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "unique_key_uniq",
            "UNIQUE(unique_key)",
            "A duplicate attendance punch record already exists for this device/user/timestamp.",
        ),
    ]

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends("device_user_id")
    def _compute_employee_id(self):
        """
        Link the log to an hr.employee by matching `device_user_id`
        against `hr.employee.device_user_id`.
        """
        for record in self:
            if record.device_user_id:
                employee = self.env["hr.employee"].search(
                    [("device_user_id", "=", record.device_user_id)], limit=1
                )
                record.employee_id = employee.id if employee else False
            else:
                record.employee_id = False

    @api.depends("device_id.serial_number", "device_user_id", "timestamp")
    def _compute_unique_key(self):
        """
        Compute a string unique key combining serial number, device user ID,
        and UTC timestamp to serve as a deduplication fingerprint.
        """
        for record in self:
            serial = (record.device_id.serial_number or "").strip()
            uid = (record.device_user_id or "").strip()
            ts = fields.Datetime.to_string(record.timestamp) if record.timestamp else ""
            record.unique_key = f"{serial}_{uid}_{ts}"
