# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
import io
import base64
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None
    _logger.warning("xlsxwriter is not installed. Excel reports will not be available.")

class BiometricAttendanceReportWizard(models.TransientModel):
    _name = 'biometric.attendance.report.wizard'
    _description = 'Biometric Attendance Report Wizard'

    from_date = fields.Date(string='From Date', required=True, default=fields.Date.context_today)
    to_date = fields.Date(string='To Date', required=True, default=fields.Date.context_today)
    report_type = fields.Selection([
        ('detailed', 'Detailed Report'),
        ('summary', 'Summary Report'),
    ], string='Report Type', default='detailed', required=True)
    
    attendance_ids = fields.Many2many('hr.attendance', string='Selected Attendances')
    log_ids = fields.Many2many('biometric.attendance.log', string='Selected Logs')
    is_log_report = fields.Boolean(string='Is Log Report')

    excel_file = fields.Binary('Download Report', readonly=True)
    file_name = fields.Char('File Name', readonly=True)

    def action_export_excel(self):
        if not xlsxwriter:
            raise models.ValidationError(_("xlsxwriter is not installed on this server. Please contact your administrator."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Attendance Report')

        # Formats
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center'
        })
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss', 'border': 1})
        cell_format = workbook.add_format({'border': 1})

        # Determine if we are reporting on Logs or Attendances
        is_log_report = self.env.context.get('active_model') == 'biometric.attendance.log' or self.log_ids

        # Columns based on report type and model
        if self.report_type == 'summary':
            columns = ['Employee', 'Check In', 'Check Out', 'Work Hours']
        else:
            if is_log_report:
                columns = ['Device', 'Device UID', 'Employee', 'Punch Time', 'State', 'Status']
            else:
                columns = ['Employee', 'Check In', 'Check Out', 'Work Hours']

        for i, col in enumerate(columns):
            sheet.write(0, i, col, header_format)
            sheet.set_column(i, i, 25)

        domain = [('employee_id', '!=', False)]
        
        if is_log_report:
            domain += [
                ('timestamp', '>=', datetime.combine(self.from_date, datetime.min.time())),
                ('timestamp', '<=', datetime.combine(self.to_date, datetime.max.time())),
            ]
            if self.log_ids:
                domain.append(('id', 'in', self.log_ids.ids))
            records = self.env['biometric.attendance.log'].search(domain, order='timestamp asc')
        else:
            domain += [
                ('check_in', '>=', datetime.combine(self.from_date, datetime.min.time())),
                ('check_in', '<=', datetime.combine(self.to_date, datetime.max.time())),
            ]
            if self.attendance_ids:
                domain.append(('id', 'in', self.attendance_ids.ids))
            records = self.env['hr.attendance'].search(domain, order='check_in asc')

        row = 1
        if self.report_type == 'detailed':
            # ── Detailed Report: Show Every Record ─────────────────────────────
            for rec in records:
                if is_log_report:
                    ts_local = fields.Datetime.context_timestamp(self, rec.timestamp)
                    # 1. Device
                    sheet.write(row, 0, rec.device_id.name, cell_format)
                    # 2. Device UID
                    sheet.write(row, 1, rec.device_user_id or '', cell_format)
                    # 3. Employee
                    sheet.write(row, 2, rec.employee_id.name, cell_format)
                    # 4. Punch Time
                    sheet.write(row, 3, ts_local.strftime('%d/%m/%Y %H:%M:%S'), cell_format)
                    # 5. State
                    sheet.write(row, 4, dict(rec._fields['verify_state'].selection).get(rec.verify_state, ''), cell_format)
                    # 6. Status
                    sheet.write(row, 5, dict(rec._fields['status'].selection).get(rec.status, ''), cell_format)
                else:
                    check_in_local = fields.Datetime.context_timestamp(self, rec.check_in) if rec.check_in else None
                    check_out_local = fields.Datetime.context_timestamp(self, rec.check_out) if rec.check_out else None
                    sheet.write(row, 0, rec.employee_id.name, cell_format)
                    sheet.write(row, 1, check_in_local.strftime('%d/%m/%Y %H:%M:%S') if check_in_local else '', cell_format)
                    sheet.write(row, 2, check_out_local.strftime('%d/%m/%Y %H:%M:%S') if check_out_local else '', cell_format)
                    
                    total_seconds = rec.worked_hours * 3600
                    total_minutes = int(round(total_seconds / 60.0))
                    hours, minutes = divmod(total_minutes, 60)
                    sheet.write(row, 3, f"{hours:02d}:{minutes:02d}", cell_format)
                row += 1
        else:
            # ── Summary Report: Group by Employee and Date ─────────────────────
            summary_data = {}
            for rec in records:
                emp_id = rec.employee_id.id
                ts = rec.timestamp if is_log_report else rec.check_in
                local_ts = fields.Datetime.context_timestamp(self, ts)
                att_date = local_ts.date()
                
                if emp_id not in summary_data:
                    summary_data[emp_id] = {}
                if att_date not in summary_data[emp_id]:
                    summary_data[emp_id][att_date] = []
                summary_data[emp_id][att_date].append(rec)

            sorted_employees = sorted(summary_data.keys(), key=lambda eid: self.env['hr.employee'].browse(eid).name)
            for emp_id in sorted_employees:
                emp_name = self.env['hr.employee'].browse(emp_id).name
                sorted_dates = sorted(summary_data[emp_id].keys())
                for att_date in sorted_dates:
                    recs = summary_data[emp_id][att_date]
                    
                    if is_log_report:
                        first_in = min(r.timestamp for r in recs)
                        last_out = max(r.timestamp for r in recs)
                        total_worked_delta = last_out - first_in
                        total_worked = total_worked_delta.total_seconds() / 3600.0
                    else:
                        first_in = min(r.check_in for r in recs)
                        last_out = max(r.check_out for r in recs) if all(r.check_out for r in recs) else None
                        total_worked = sum(r.worked_hours for r in recs)
                    
                    first_in_local = fields.Datetime.context_timestamp(self, first_in)
                    last_out_local = fields.Datetime.context_timestamp(self, last_out) if last_out else None
                    
                    sheet.write(row, 0, emp_name, cell_format)
                    sheet.write(row, 1, first_in_local.strftime('%d/%m/%Y %H:%M:%S'), cell_format)
                    sheet.write(row, 2, last_out_local.strftime('%d/%m/%Y %H:%M:%S') if last_out_local else 'N/A', cell_format)
                    
                    total_seconds = total_worked * 3600
                    total_minutes = int(round(total_seconds / 60.0))
                    hours, minutes = divmod(total_minutes, 60)
                    sheet.write(row, 3, f"{hours:02d}:{minutes:02d}", cell_format)
                    row += 1

        workbook.close()
        output.seek(0)
        
        file_data = base64.b64encode(output.read())
        self.write({
            'excel_file': file_data,
            'file_name': f'Attendance_Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.attendance.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
