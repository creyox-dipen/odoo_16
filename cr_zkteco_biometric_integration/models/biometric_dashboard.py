# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, api, fields, _
from datetime import datetime, date, timedelta
import pytz


class BiometricDashboard(models.AbstractModel):
    _name = "biometric.dashboard"
    _description = "Biometric Dashboard Logic"

    @api.model
    def get_dashboard_data(self):
        uid = self.env.context.get("uid", self.env.user.id)
        user = self.env["res.users"].browse(uid)
        company = user.company_id

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Convert to UTC for database queries
        tz = pytz.timezone(user.tz or "UTC")
        today_start_utc = (
            tz.localize(today_start).astimezone(pytz.utc).replace(tzinfo=None)
        )
        today_end_utc = tz.localize(today_end).astimezone(pytz.utc).replace(tzinfo=None)

        # 1. Total Active Employees
        all_employees = self.env["hr.employee"].search(
            [("active", "=", True), ("company_id", "=", company.id)]
        )
        total_employees = len(all_employees)

        # 2. Batch check statuses for today
        status_map = all_employees.get_attendance_statuses_for_date_batch(today, tz)

        present_count = 0
        absent_count = 0
        leave_count = 0

        presented_employees = []
        absented_employees = []
        leaved_employees = []

        for e in all_employees:
            status, reason = status_map.get(e.id, ("absent", False))
            img = False
            if e.image_128:
                try:
                    img = e.image_128.decode("utf-8")
                except:
                    img = e.image_128

            emp_data = {
                "id": e.id,
                "name": e.name,
                "job": e.job_id.name or "",
                "image": img,
                "details": reason or "",
            }

            if status == "present":
                present_count += 1
                if len(presented_employees) < 50:
                    presented_employees.append(emp_data)
            elif status in ("leave", "holiday"):
                leave_count += 1
                if len(leaved_employees) < 50:
                    leaved_employees.append(emp_data)
            elif status == "absent":
                absent_count += 1
                if len(absented_employees) < 50:
                    absented_employees.append(emp_data)

        # 4. Device Status
        devices = self.env["biometric.device"].search([])
        device_stats = []
        for dev in devices:
            is_online = False
            last_seen_str = _("Never seen")
            if dev.last_seen:
                # If seen in last 10 minutes, consider online
                if (datetime.now() - dev.last_seen) < timedelta(minutes=10):
                    is_online = True
                last_seen_str = dev.last_seen.strftime("%Y-%m-%d %H:%M:%S")

            device_stats.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "sn": dev.serial_number,
                    "status": "online" if is_online else "offline",
                    "last_seen": last_seen_str,
                }
            )

        # 5. Recent Punches (Last 10)
        recent_punches = []
        logs = self.env["biometric.attendance.log"].search(
            [], order="timestamp desc", limit=10
        )
        for log in logs:
            # Convert timestamp back to user timezone for display
            ts_utc = pytz.utc.localize(log.timestamp)
            ts_user = ts_utc.astimezone(tz)

            recent_punches.append(
                {
                    "employee": log.employee_id.name,
                    "device": log.device_id.name,
                    "time": ts_user.strftime("%I:%M:%S %p"),
                    "type": (
                        "Check In" if log.verify_state in ["0", "4"] else "Check Out"
                    ),
                }
            )

        # 7. Late/Early Counts
        late_arrival_count = self.env["hr.attendance"].search_count(
            [
                ("check_in", ">=", today_start_utc),
                ("check_in", "<=", today_end_utc),
                ("is_late", "=", True),
            ]
        )
        early_leaving_count = self.env["hr.attendance"].search_count(
            [
                ("check_out", ">=", today_start_utc),
                ("check_out", "<=", today_end_utc),
                ("is_early_leaving", "=", True),
            ]
        )

        return {
            "total_employees": total_employees,
            "present_count": present_count,
            "absent_count": absent_count,
            "leave_count": leave_count,
            "late_count": late_arrival_count,
            "early_count": early_leaving_count,
            "device_stats": device_stats,
            "recent_punches": recent_punches,
            "presented_employees": presented_employees,
            "absented_employees": absented_employees,
            "leaved_employees": leaved_employees,
        }
