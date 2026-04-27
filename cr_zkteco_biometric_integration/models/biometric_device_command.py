# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class BiometricDeviceCommand(models.Model):
    """
    Stores commands to be sent to the biometric device via ADMS.
    The device pulls these commands during its heartbeat (getrequest).
    """
    _name = "biometric.device.command"
    _description = "Biometric Device Command"
    _order = "create_date desc"

    device_id = fields.Many2one(
        comodel_name="biometric.device",
        string="Device",
        required=True,
        ondelete="cascade",
    )
    command_text = fields.Char(
        string="Command Text",
        required=True,
        help="The actual command string sent to the device (e.g., REBOOT, CLEAR LOG).",
    )
    status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="pending",
        string="Status",
        index=True,
    )
    response_text = fields.Text(
        string="Device Response",
        readonly=True,
    )

    def name_get(self):
        return [(rec.id, f"{rec.device_id.name}: {rec.command_text}") for rec in self]
