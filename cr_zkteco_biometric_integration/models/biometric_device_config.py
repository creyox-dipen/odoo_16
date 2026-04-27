# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BiometricDevice(models.Model):
    """
    Represents a registered ZKTeco biometric device that pushes attendance
    data to Odoo via the ADMS HTTP protocol.

    The device is identified by its unique serial number. When the device
    sends a push, Odoo looks up the record by serial number, validates the
    optional communication key, and processes the attendance payload.
    """

    _name = "biometric.device"
    _description = "Biometric Device (ADMS)"
    _rec_name = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    name = fields.Char(
        string="Device Name",
        required=True,
        tracking=True,
        help="A descriptive label for this biometric device (e.g. 'Main Entrance').",
    )
    serial_number = fields.Char(
        string="Serial Number",
        required=True,
        copy=False,
        tracking=True,
        help=(
            "Unique hardware serial number of the ZKTeco device. "
            "Must match the SN= parameter sent by the device in every ADMS push."
        ),
    )
    device_ip = fields.Char(
        string="Device IP Address",
        copy=False,
        help=(
            "IP address of the ZKTeco device on the local network. "
            "Used to fetch user names via pyzk when auto-creating employees."
        ),
    )
    device_port = fields.Integer(
        string="Device Port",
        default=4370,
        help=(
            "TCP port of the ZKTeco device SDK service (default: 4370). "
            "Used together with Device IP to connect via pyzk."
        ),
    )
    # communication_key = fields.Char(
    #     string="Communication Key",
    #     copy=False,
    #     help=(
    #         "Optional security key configured on the device. "
    #         "If set, every ADMS request must include a matching Key= parameter."
    #     ),
    # )
    timezone = fields.Selection(
        string="Device Timezone",
        selection=[
            ("UTC", "UTC"),
            ("Asia/Kolkata", "Asia/Kolkata (IST +05:30)"),
            ("Asia/Dubai", "Asia/Dubai (GST +04:00)"),
            ("Asia/Karachi", "Asia/Karachi (PKT +05:00)"),
            ("Asia/Dhaka", "Asia/Dhaka (BST +06:00)"),
            ("Asia/Singapore", "Asia/Singapore (SGT +08:00)"),
            ("Asia/Shanghai", "Asia/Shanghai (CST +08:00)"),
            ("Asia/Riyadh", "Asia/Riyadh (AST +03:00)"),
            ("Africa/Cairo", "Africa/Cairo (EET +02:00)"),
            ("America/New_York", "America/New_York (EST -05:00)"),
            ("America/Los_Angeles", "America/Los_Angeles (PST -08:00)"),
            ("Europe/London", "Europe/London (GMT +00:00)"),
            ("Europe/Paris", "Europe/Paris (CET +01:00)"),
            ("Australia/Sydney", "Australia/Sydney (AEDT +11:00)"),
        ],
        default="Asia/Shanghai",
        required=True,
        help=(
            "Local timezone of the device. Timestamps in ADMS pushes are in device "
            "local time and will be converted to UTC before storing in Odoo."
        ),
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive devices are ignored by the ADMS endpoint.",
    )
    last_seen = fields.Datetime(
        string="Last Seen",
        readonly=True,
        copy=False,
        tracking=True,
        help="Timestamp of the last successful ADMS push received from this device.",
    )
    attendance_log_ids = fields.One2many(
        comodel_name="biometric.attendance.log",
        inverse_name="device_id",
        string="Attendance Logs",
        help="Raw attendance punch logs received from this device.",
    )
    attendance_log_count = fields.Integer(
        string="Log Count",
        compute="_compute_attendance_log_count",
        help="Total number of attendance punch logs received from this device.",
    )

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        (
            "serial_number_uniq",
            "UNIQUE(serial_number)",
            "A device with this serial number already exists. Serial numbers must be unique.",
        ),
    ]

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends("attendance_log_ids")
    def _compute_attendance_log_count(self):
        """Compute the total count of attendance logs linked to each device."""
        for record in self:
            record.attendance_log_count = len(record.attendance_log_ids)

    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------

    def action_view_logs(self):
        """
        Open the attendance logs list view filtered to this device.

        Returns:
            dict: Window action to open biometric.attendance.log filtered by device.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attendance Logs — %s") % self.name,
            "res_model": "biometric.attendance.log",
            "view_mode": "list,form",
            "domain": [("device_id", "=", self.id)],
            "context": {"default_device_id": self.id},
        }
