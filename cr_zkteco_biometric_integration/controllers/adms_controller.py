# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import pytz

# import threading

from datetime import datetime
from odoo import http, fields
from odoo.http import request

# try:
#     from zk import ZK
#     HAS_PYZK = True
# except ImportError:
#     HAS_PYZK = False
#     _pyzk_warned = False

_logger = logging.getLogger(__name__)


class AdmsController(http.Controller):
    """
    ADMS (Attendance Data Management System) HTTP controller for ZKTeco devices.

    ZKTeco biometric devices supporting the ADMS protocol push attendance records
    to this endpoint in real-time as users punch in or out.

    Protocol overview:
        - Device sends POST to /iclock/cdata?SN=<serial>&table=ATTLOG&Key=<key>
        - Request body contains tab-separated attendance lines
        - Each line: user_id  timestamp  verify  status  work_code  reserved
        - Odoo validates the device, parses the lines, and returns plain "OK"
    """

    @http.route(
        "/iclock/getrequest",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def adms_getrequest(self, **kwargs):
        serial = (kwargs.get("SN") or "").strip()
        _logger.info("ADMS: Heartbeat from device SN=%s", serial)
        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    # ---------------------------------------------------------
    # HEARTBEAT + HANDSHAKE
    # ---------------------------------------------------------
    @http.route(
        "/iclock/cdata",
        type="http",
        auth="public",  # must be same auth on both — use public
        methods=["GET", "POST"],
        csrf=False,
    )
    def adms_cdata(self, **kwargs):
        serial = (kwargs.get("SN") or "").strip()
        # comm_key = (kwargs.get("Key") or "").strip()
        table = (kwargs.get("table") or "").strip()
        options = (kwargs.get("options") or "").strip()

        _logger.info(
            "ADMS: Request from SN=%s method=%s table=%s options=%s",
            serial,
            request.httprequest.method,
            table,
            options,
        )

        # ── GET: Handshake ────────────────────────────────────────────────────
        if request.httprequest.method == "GET":
            # print("adms handshake hit")

            if not serial:
                return request.make_response(
                    "ERROR", headers=[("Content-Type", "text/plain")]
                )

            device = (
                request.env["biometric.device"]
                .sudo()
                .search([("serial_number", "=", serial)], limit=1)
            )

            # Auto-discovery: Create device if it doesn't exist
            if not device:
                _logger.info("ADMS: New device discovered SN=%s. Auto-creating...", serial)
                device = request.env["biometric.device"].sudo().create({
                    "name": f"New Device: {serial}",
                    "serial_number": serial,
                    "active": True,
                })

            if not device or not device.active:
                _logger.warning("ADMS: Unknown or inactive device SN=%s", serial)
                return request.make_response(
                    "ERROR", headers=[("Content-Type", "text/plain")]
                )

            device.sudo().write({"last_seen": fields.Datetime.now()})

            body = (
                "\n".join(
                    [
                        f"GET OPTION FROM: {serial}",
                        "ATTLOGStamp=9999",
                        "OPERLOGStamp=9999",
                        "ATTPHOTOStamp=9999",
                        "ErrorDelay=30",
                        "Delay=10",
                        "TransTimes=00:00;14:05",
                        "TransInterval=1",
                        "TransFlag=TransData AttLog OpLog AttPhoto",
                        "Realtime=1",
                        "Encrypt=None",
                    ]
                )
                + "\n"
            )

            return request.make_response(body, headers=[("Content-Type", "text/plain")])

        # ── POST: Attendance push ─────────────────────────────────────────────
        # print("adms post hit")

        device = (
            request.env["biometric.device"]
            .sudo()
            .search([("serial_number", "=", serial)], limit=1)
        )

        # Auto-discovery also handles POST if handshake was skipped
        if not device:
            _logger.info("ADMS: New device discovered via POST SN=%s. Auto-creating...", serial)
            device = request.env["biometric.device"].sudo().create({
                "name": f"New Device: {serial}",
                "serial_number": serial,
                "active": True,
            })

        if not device or not device.active:
            _logger.warning("ADMS: Unknown or inactive device SN=%s", serial)
            return request.make_response(
                "ERROR: Device not recognised",
                headers=[("Content-Type", "text/plain")],
                status=403,
            )

        # if device.communication_key and device.communication_key != comm_key:
        #     return request.make_response(
        #         "ERROR: Invalid communication key",
        #         headers=[("Content-Type", "text/plain")],
        #         status=403,
        #     )

        if table != "ATTLOG":
            return request.make_response("OK", headers=[("Content-Type", "text/plain")])

        raw_body = request.httprequest.get_data(as_text=True) or ""
        lines = [ln.strip() for ln in raw_body.splitlines() if ln.strip()]
        # print("body : ",raw_body)

        if not lines:
            return request.make_response("OK", headers=[("Content-Type", "text/plain")])

        _logger.info(
            "ADMS: Processing %d ATTLOG line(s) from SN=%s", len(lines), serial
        )

        for line in lines:
            self._process_attlog_line(device, line)

        device.sudo().write({"last_seen": fields.Datetime.now()})
        return request.make_response("OK", headers=[("Content-Type", "text/plain")])

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _parse_attlog_timestamp(self, ts_str, device_tz_name):
        """
        Parse a device-local timestamp string and convert it to a UTC datetime.

        ZKTeco devices send timestamps as "YYYY-MM-DD HH:MM:SS" in the device's
        local timezone. This method attaches the timezone and converts to UTC.

        Args:
            ts_str (str): Raw timestamp string from the ATTLOG line.
            device_tz_name (str): pytz timezone name configured on the device record.

        Returns:
            datetime: Timezone-aware UTC datetime, or None if parsing fails.
        """
        try:
            naive_dt = datetime.strptime(ts_str.strip(), "%Y-%m-%d %H:%M:%S")
            device_tz = pytz.timezone(device_tz_name or "UTC")
            local_dt = device_tz.localize(naive_dt, is_dst=False)
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            _logger.info(
                "ADMS: Timestamp conversion — device_tz=%s raw='%s' → UTC='%s'",
                device_tz_name,
                ts_str.strip(),
                utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )
            return utc_dt
        except Exception as e:
            _logger.warning("ADMS: Failed to parse timestamp '%s': %s", ts_str, e)
            return None

    # def _fetch_user_name_from_device(self, device, device_user_id):
    #     """
    #     Connect to the ZKTeco device via pyzk SDK and retrieve the user name
    #     that corresponds to the given device_user_id.

    #     The device is contacted over TCP using the IP address and port stored
    #     on the ``biometric.device`` record.  If pyzk is not installed, the
    #     device IP is not configured, or any network/SDK error occurs the
    #     method returns ``None`` and the caller should fall back to a default
    #     name.

    #     Args:
    #         device (biometric.device): The Odoo device record containing
    #             ``device_ip`` and ``device_port``.
    #         device_user_id (str): The numeric user ID string as sent by the
    #             device in the ATTLOG line.

    #     Returns:
    #         str or None: The user's name stored on the device, or ``None`` if
    #         it could not be retrieved.
    #     """
    #     global _pyzk_warned

    #     if not HAS_PYZK:
    #         if not _pyzk_warned:
    #             _logger.warning(
    #                 "ADMS: pyzk is not installed — cannot fetch user names from device. "
    #                 "Install it with: pip install pyzk"
    #             )
    #             _pyzk_warned = True
    #         return None

    #     if not device.device_ip:
    #         _logger.debug(
    #             "ADMS: Device IP not configured for SN=%s — skipping pyzk name lookup",
    #             device.serial_number,
    #         )
    #         return None

    #     port = device.device_port or 4370
    #     zk = ZK(
    #         device.device_ip,
    #         port=port,
    #         timeout=5,
    #         password=0,
    #         force_udp=False,
    #         ommit_ping=True,
    #     )
    #     conn = None
    #     try:
    #         conn = zk.connect()
    #         users = conn.get_users()
    #         uid_int = int(device_user_id)
    #         for user in users:
    #             if user.uid == uid_int or str(user.user_id) == str(device_user_id):
    #                 name = (user.name or "").strip()
    #                 if name:
    #                     _logger.info(
    #                         "ADMS: Resolved name='%s' for device_user_id=%s from device SN=%s",
    #                         name, device_user_id, device.serial_number,
    #                     )
    #                     return name
    #         _logger.info(
    #             "ADMS: User device_user_id=%s not found on device SN=%s",
    #             device_user_id, device.serial_number,
    #         )
    #         return None
    #     except Exception as exc:
    #         _logger.warning(
    #             "ADMS: pyzk failed to fetch user name for device_user_id=%s from %s:%s — %s",
    #             device_user_id, device.device_ip, port, exc,
    #         )
    #         return None
    #     finally:
    #         if conn:
    #             try:
    #                 conn.disconnect()
    #             except Exception:
    #                 pass

    def _get_or_create_employee(self, device, device_user_id):
        """
        Look up an hr.employee by device_user_id.  If none is found, attempt
        to resolve the user's real name from the ZKTeco device via pyzk and
        then automatically create a new employee record.

        The name resolution order is:
            1. Real name fetched from the device via pyzk.
            2. Fallback: ``"Biometric User <device_user_id>"``.

        Args:
            device (biometric.device): The Odoo device record.  Used to open
                a pyzk connection when a new employee must be created.
            device_user_id (str): The user ID as sent by the ZKTeco device.

        Returns:
            hr.employee: Existing or newly created employee record.
        """
        Employee = request.env["hr.employee"].sudo()
        employee = Employee.search([("device_user_id", "=", device_user_id)], limit=1)
        if not employee:
            _logger.info(
                "ADMS: Auto-creating employee for device_user_id=%s", device_user_id
            )
            # Try to fetch the real name stored on the device
            # real_name = self._fetch_user_name_from_device(device, device_user_id)
            employee_name = "Biometric User %s" % device_user_id

            employee = Employee.create(
                {
                    "name": employee_name,
                    "device_user_id": device_user_id,
                }
            )
            _logger.info(
                "ADMS: Created employee name='%s' device_user_id=%s",
                employee_name,
                device_user_id,
            )
        return employee

    # -------------------------------------------------------------------------
    # pyzk Voice Helpers
    # -------------------------------------------------------------------------

    # def _play_device_voice(self, device, voice_index):
    #     """
    #     Connect to the ZKTeco device via pyzk and play a built-in voice prompt.
    #
    #     Useful voice indexes:
    #         0  = Thank You
    #         2  = Access Denied
    #         3  = Invalid ID
    #         4  = Please try again
    #         9  = Duplicated punch
    #
    #     Args:
    #         device (biometric.device): The device record (must have device_ip set).
    #         voice_index (int): Index of the built-in voice message to play.
    #     """
    #     if not HAS_PYZK or not device.device_ip:
    #         return
    #
    #     zk = ZK(
    #         device.device_ip,
    #         port=device.device_port or 4370,
    #         timeout=5,
    #         password=0,
    #         force_udp=False,
    #         ommit_ping=True,
    #     )
    #     conn = None
    #     try:
    #         conn = zk.connect()
    #         conn.test_voice(index=voice_index)
    #     except Exception as exc:
    #         _logger.warning(
    #             "ADMS: Failed to play voice (index=%s) on device SN=%s: %s",
    #             voice_index, device.serial_number, exc,
    #         )
    #     finally:
    #         if conn:
    #             try:
    #                 conn.disconnect()
    #             except Exception:
    #                 pass

    # def _play_device_voice_async(self, device, voice_index):
    #     """
    #     Fire-and-forget wrapper around ``_play_device_voice``.
    #
    #     Launches the pyzk connection in a daemon thread so the ADMS HTTP
    #     response is not blocked by the device round-trip.
    #
    #     Args:
    #         device (biometric.device): The device record.
    #         voice_index (int): Built-in voice index to play.
    #     """
    #     thread = threading.Thread(
    #         target=self._play_device_voice,
    #         args=(device, voice_index),
    #         daemon=True,
    #     )
    #     thread.start()

    # -------------------------------------------------------------------------
    # Attendance Processing
    # -------------------------------------------------------------------------

    def _process_attendance(self, device, employee, utc_dt, punch_type):
        """
        Create or update an ``hr.attendance`` record based on the explicit
        punch type reported by the ZKTeco device.

        Punch type mapping (from ATTLOG status field):
            ``"in"``  — status 0 (Check In) or 4 (Overtime In)
            ``"out"`` — status 1 (Check Out) or 5 (Overtime Out)

        Rules:
            - ``"in"``  → always creates a new ``check_in`` record.
            - ``"out"`` → finds the most-recent open record (``check_out`` is
              False) and sets its ``check_out``.
              If no open record exists the punch is invalid: voice index 4
              ("Please try again") is played on the device asynchronously and
              the method returns ``False`` to signal the caller to skip saving.

        Args:
            device (biometric.device): The device record (used for voice playback).
            employee (hr.employee): The employee record.
            utc_dt (datetime): UTC-naive punch datetime.
            punch_type (str): ``"in"`` or ``"out"``.

        Returns:
            bool: ``True`` if an attendance record was written, ``False`` if the
            punch was invalid and was deliberately skipped.
        """
        Attendance = request.env["hr.attendance"].sudo()

        if punch_type == "in":
            # Guard: skip if an open check-in already exists (no check_out yet)
            open_attendance = Attendance.search(
                [
                    ("employee_id", "=", employee.id),
                    ("check_out", "=", False),
                ],
                limit=1,
            )
            if open_attendance:
                _logger.warning(
                    "ADMS: Check-in punch received but employee=%s already has an "
                    "open check-in at %s — playing duplicate voice and skipping",
                    employee.name,
                    open_attendance.check_in,
                )
                # self._play_device_voice_async(device, 9)
                return False

            Attendance.create(
                {
                    "employee_id": employee.id,
                    "check_in": utc_dt,
                }
            )
            _logger.info(
                "ADMS: Check-in created for employee=%s at %s (UTC)",
                employee.name,
                utc_dt,
            )
            return True

        # punch_type == "out"
        open_attendance = Attendance.search(
            [
                ("employee_id", "=", employee.id),
                ("check_out", "=", False),
            ],
            order="check_in desc",
            limit=1,
        )

        if not open_attendance:
            _logger.warning(
                "ADMS: Check-out punch received but no open check-in exists "
                "for employee=%s — playing 'please try again' voice and skipping",
                employee.name,
            )
            # self._play_device_voice_async(device, 4)
            return False

        if utc_dt > open_attendance.check_in:
            open_attendance.write({"check_out": utc_dt})
            _logger.info(
                "ADMS: Check-out set for employee=%s at %s (UTC)",
                employee.name,
                utc_dt,
            )
            return True

        _logger.warning(
            "ADMS: Punch time %s is not after last check-in %s "
            "for employee=%s — skipping attendance update",
            utc_dt,
            open_attendance.check_in,
            employee.name,
        )
        return False

    def _process_attlog_line(self, device, line):
        """
        Parse a single tab-separated ATTLOG line, resolve the punch type from
        the status field, and create both the raw attendance log and the
        ``hr.attendance`` record.

        ATTLOG line format (tab-separated, 0-indexed):
            [0] user_id   [1] timestamp   [2] verify   [3] status
            [4] work_code [5..] reserved

        Status codes handled:
            0  = Check In      → punch_type ``"in"``
            1  = Check Out     → punch_type ``"out"``
            4  = Overtime In   → punch_type ``"in"``
            5  = Overtime Out  → punch_type ``"out"``
            other             → logged and skipped (no ``hr.attendance`` record)

        Args:
            device (biometric.device): The device record that sent this line.
            line (str): One raw ATTLOG line string.
        """
        # Status code → punch_type mapping
        PUNCH_TYPE_MAP = {
            0: "in",  # Check In
            1: "out",  # Check Out
            4: "in",  # Overtime In
            5: "out",  # Overtime Out
        }

        parts = line.split("\t")
        if len(parts) < 2:
            _logger.warning("ADMS: Malformed ATTLOG line (too few fields): %r", line)
            return

        device_user_id = parts[0].strip()
        ts_str = parts[1].strip()
        verify_state = parts[2].strip() if len(parts) > 2 else ""
        verify_mode = parts[3].strip() if len(parts) > 3 else ""

        if not device_user_id or not ts_str:
            _logger.warning("ADMS: Empty user_id or timestamp in line: %r", line)
            return

        # Resolve punch type from status code
        try:
            status_code = int(verify_state)
        except (ValueError, TypeError):
            status_code = -1

        punch_type = PUNCH_TYPE_MAP.get(status_code)
        if punch_type is None:
            _logger.info(
                "ADMS: Unsupported punch status=%r for device_user_id=%s — "
                "attendance record will not be created",
                verify_mode,
                device_user_id,
            )

        # Convert timestamp to UTC
        utc_dt = self._parse_attlog_timestamp(ts_str, device.timezone)
        if not utc_dt:
            return

        # Build unique key for deduplication
        utc_ts_str = fields.Datetime.to_string(utc_dt)
        unique_key = f"{device.serial_number}_{device_user_id}_{utc_ts_str}"

        # Skip duplicates
        Log = request.env["biometric.attendance.log"].sudo()
        if Log.search([("unique_key", "=", unique_key)], limit=1):
            _logger.debug("ADMS: Duplicate punch skipped — unique_key=%s", unique_key)
            return

        # Get or auto-create employee
        employee = self._get_or_create_employee(device, device_user_id)

        # Create raw attendance log
        try:
            Log.create(
                {
                    "device_id": device.id,
                    "device_user_id": device_user_id,
                    "employee_id": employee.id,
                    "timestamp": utc_dt,
                    "verify_state": verify_state,
                    "raw_data": line,
                    "unique_key": unique_key,
                    "status": "new",
                }
            )
            _logger.info(
                "ADMS: Created attendance log for unique_key=%s employee=%s",
                unique_key,
                employee.name,
            )
        except Exception as e:
            _logger.error(
                "ADMS: Failed to create attendance log for unique_key=%s: %s",
                unique_key,
                e,
            )
            return

        # Skip hr.attendance processing for unsupported status codes
        if punch_type is None:
            Log.search([("unique_key", "=", unique_key)]).write({"status": "processed"})
            return

        # Process hr.attendance record
        try:
            success = self._process_attendance(device, employee, utc_dt, punch_type)
            log_status = "processed" if success else "failed"
            Log.search([("unique_key", "=", unique_key)]).write({"status": log_status})
        except Exception as e:
            _logger.error(
                "ADMS: Failed to process hr.attendance for employee=%s unique_key=%s: %s",
                employee.name,
                unique_key,
                e,
            )
            Log.search([("unique_key", "=", unique_key)]).write({"status": "failed"})
