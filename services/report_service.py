"""PDF, Excel, and CSV export for salon reports and salary slips."""

from __future__ import annotations

import csv
import html

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QFileDialog, QWidget

from core.utils import format_date, money


def report_html(report: dict, settings: dict, start: str, end: str) -> str:
    salon = html.escape(settings.get("salon_name") or "CAVERON")
    tagline = html.escape(settings.get("tagline") or "CRAFT YOUR STYLE")
    subtitle = html.escape(settings.get("subtitle") or "SALON & BARBER")
    title = html.escape(report.get("title") or "Report")
    period = f"{format_date(start)} to {format_date(end)}"
    metric_cells = []
    for metric in report.get("metrics") or []:
        if metric.get("plain"):
            value = str(int(metric["raw"]))
        else:
            value = money(metric["raw"])
        metric_cells.append(
            f"<td style='padding:8px 12px;border:1px solid #d9d3c5;'><div style='color:#8a7340;font-size:11px;'>{html.escape(metric['label'])}</div><div style='font-size:16px;'><b>{html.escape(value)}</b></div></td>"
        )
    notes = "".join(f"<p style='color:#444;'>{html.escape(note)}</p>" for note in report.get("notes") or [])
    headers = "".join(
        f"<th style='text-align:left;padding:6px 8px;background:#141418;color:#f5f5f7;'>{html.escape(str(header))}</th>"
        for header in report.get("headers") or []
    )
    body = []
    for row in report.get("rows") or []:
        cells = "".join(f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;'>{html.escape(str(cell))}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    if not body:
        span = max(1, len(report.get("headers") or []))
        body.append(f"<tr><td colspan='{span}' style='padding:12px;color:#666;'>Nothing in this range.</td></tr>")
    return f"""
    <html><body style="font-family:Segoe UI,sans-serif;color:#161616;">
    <div style="border-bottom:2px solid #C9A96E;padding-bottom:8px;margin-bottom:12px;">
      <div style="font-size:22px;letter-spacing:3px;"><b>{salon}</b></div>
      <div style="color:#8a7340;">{tagline} · {subtitle}</div>
    </div>
    <h2 style="margin:0 0 4px 0;">{title}</h2>
    <p style="margin:0 0 12px 0;color:#555;">{period}</p>
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;margin-bottom:12px;"><tr>{''.join(metric_cells)}</tr></table>
    {notes}
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">
      <tr>{headers}</tr>
      {''.join(body)}
    </table>
    </body></html>
    """


def closing_slip_html(snap: dict, settings: dict) -> str:
    salon = html.escape(settings.get("salon_name") or "CAVERON")
    tagline = html.escape(settings.get("tagline") or "CRAFT YOUR STYLE")

    def line(label, value, strong=False):
        weight = "font-weight:700;" if strong else ""
        return (
            f"<tr><td style='padding:5px 8px;border-bottom:1px solid #ece7dc;'>{html.escape(label)}</td>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;text-align:right;{weight}'>{html.escape(value)}</td></tr>"
        )

    variance = snap.get("variance")
    if variance == "match":
        result = "Drawer matches. Counted cash equals the expected balance."
    elif variance == "short":
        result = f"Drawer is short by {money(abs(snap['difference']))}."
    elif variance == "over":
        result = f"Drawer is over by {money(snap['difference'])}."
    else:
        result = "Drawer is still open. Count the cash to close the day."
    actual = "—" if snap.get("actual") is None else money(snap["actual"])
    difference = "—" if snap.get("difference") is None else money(snap["difference"])
    staff_rows = []
    for member in snap.get("staff") or []:
        commission = (
            f"{member['percent']:g}% · {money(member['commission'])}"
            if member["percent"]
            else "No commission on this pay type"
        )
        staff_rows.append(
            "<tr>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;'>{html.escape(member['name'])}</td>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;text-align:right;'>{html.escape(money(member['work']))}</td>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;text-align:right;'>{html.escape(commission)}</td>"
            "</tr>"
        )
    if not staff_rows:
        staff_rows.append("<tr><td colspan='3' style='padding:8px;color:#666;'>No staff sales or advances today.</td></tr>")
    advance_rows = []
    for row in snap.get("advances") or []:
        advance_rows.append(
            "<tr>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;'>{html.escape(row['staff_name'])}</td>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;'>{html.escape(row['payment_mode'])}</td>"
            f"<td style='padding:5px 8px;border-bottom:1px solid #ece7dc;text-align:right;'>{html.escape(money(row['amount']))}</td>"
            "</tr>"
        )
    if not advance_rows:
        advance_rows.append("<tr><td colspan='3' style='padding:8px;color:#666;'>No staff advances today.</td></tr>")
    return f"""
    <html><body style="font-family:Segoe UI,sans-serif;color:#161616;">
    <div style="border-bottom:2px solid #C9A96E;padding-bottom:8px;">
      <div style="font-size:22px;letter-spacing:3px;"><b>{salon}</b></div>
      <div style="color:#8a7340;">{tagline}</div>
      <div>Day-end closing slip · {html.escape(format_date(snap['date']))}</div>
    </div>
    <p style="margin-top:12px;"><b>{html.escape(result)}</b></p>
    <h3 style="margin-bottom:4px;">Daily financial summary</h3>
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:460px;">
      {line("Opening balance", money(snap["opening"]))}
      {line("Total cash sales", money(snap["cash_sales"]))}
      {line("Total online sales", money(snap["online_sales"]))}
      {line("Daily cash expenses", money(snap["daily_cash_expenses"]))}
      {line("Monthly cash expenses", money(snap["monthly_cash_expenses"]))}
      {line("Total cash expenses", money(snap["cash_expenses"]))}
      {line("Total cash advances", money(snap["cash_advances"]))}
      {line("Total cash payments", money(snap["cash_payments"]))}
      {line("Expected drawer balance", money(snap["expected"]), True)}
      {line("Actual drawer balance", actual, True)}
      {line("Shortage / excess", difference, True)}
    </table>
    <p style="color:#555;">Expected = opening + cash sales − cash expenses − cash advances. Online sales and online expenses stay out of the till. Cash payments are the cash that left the drawer.</p>
    <h3 style="margin-bottom:4px;">Staff performance</h3>
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">
      <tr>
        <th style="text-align:left;padding:6px 8px;background:#141418;color:#f5f5f7;">Staff</th>
        <th style="text-align:right;padding:6px 8px;background:#141418;color:#f5f5f7;">Work completed</th>
        <th style="text-align:right;padding:6px 8px;background:#141418;color:#f5f5f7;">Commission</th>
      </tr>
      {''.join(staff_rows)}
    </table>
    <h3 style="margin-bottom:4px;">Staff advances today</h3>
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:100%;">
      <tr>
        <th style="text-align:left;padding:6px 8px;background:#141418;color:#f5f5f7;">Staff</th>
        <th style="text-align:left;padding:6px 8px;background:#141418;color:#f5f5f7;">Paid by</th>
        <th style="text-align:right;padding:6px 8px;background:#141418;color:#f5f5f7;">Amount</th>
      </tr>
      {''.join(advance_rows)}
    </table>
    </body></html>
    """


def salary_html(row: dict, settings: dict) -> str:
    salon = html.escape(settings.get("salon_name") or "CAVERON")

    def line(label, value):
        return f"<tr><td style='padding:6px 8px;'>{html.escape(label)}</td><td style='padding:6px 8px;text-align:right;'>{html.escape(value)}</td></tr>"

    return f"""
    <html><body style="font-family:Segoe UI,sans-serif;color:#161616;">
    <div style="border-bottom:2px solid #C9A96E;padding-bottom:8px;">
      <div style="font-size:22px;letter-spacing:3px;"><b>{salon}</b></div>
      <div>Staff Salary Slip</div>
    </div>
    <p><b>{html.escape(row['staff_name'])}</b><br>{html.escape(row.get('role') or '')}<br>
    Period {html.escape(format_date(row['period_start']))} to {html.escape(format_date(row['period_end']))}</p>
    <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;width:420px;">
      {line('Base salary', money(row['base_salary']))}
      {line('Commission', money(row['commission']))}
      {line('Tips', money(row['tips']))}
      {line('Bonuses', money(row['bonuses']))}
      {line('Advances', '-' + money(row['advances']))}
      {line('Deductions', '-' + money(row['deductions']))}
      <tr><td style="padding:8px;border-top:2px solid #161616;"><b>Net payable</b></td>
          <td style="padding:8px;border-top:2px solid #161616;text-align:right;"><b>{money(row['net_payable'])}</b></td></tr>
    </table>
    <p style="color:#555;">{html.escape(row.get('note') or '')}<br>Status: {html.escape(row.get('status') or '')}</p>
    </body></html>
    """


def write_pdf(html_text: str, path: str) -> None:
    document = QTextDocument()
    document.setHtml(html_text)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    document.print_(printer)


def print_html(html_text: str, parent: QWidget | None) -> bool:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Print")
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return False
    document = QTextDocument()
    document.setHtml(html_text)
    document.print_(printer)
    return True


def write_xlsx(report: dict, settings: dict, start: str, end: str, path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    book = Workbook()
    summary = book.active
    summary.title = "Summary"
    summary["A1"] = settings.get("salon_name") or "CAVERON"
    summary["A1"].font = Font(bold=True, size=16, color="0B0B0D")
    summary["A2"] = report.get("title") or "Report"
    summary["A3"] = f"{start} to {end}"
    header_fill = PatternFill("solid", fgColor="141418")
    header_font = Font(color="F5F5F7", bold=True)
    summary.append([])
    summary.append(["Metric", "Value"])
    for cell in summary[5]:
        cell.fill = header_fill
        cell.font = header_font
    for metric in report.get("metrics") or []:
        value = int(metric["raw"]) if metric.get("plain") else float(metric["raw"])
        summary.append([metric["label"], value])
    for note in report.get("notes") or []:
        summary.append([note, ""])
    detail = book.create_sheet("Detail")
    detail.append(report.get("headers") or [])
    for cell in detail[1]:
        cell.fill = header_fill
        cell.font = header_font
    for row in report.get("rows") or []:
        detail.append(list(row))
    for sheet in (summary, detail):
        for column in sheet.columns:
            letter = column[0].column_letter
            sheet.column_dimensions[letter].width = 28
    book.save(path)


def write_csv(report: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([report.get("title") or "Report"])
        for metric in report.get("metrics") or []:
            value = int(metric["raw"]) if metric.get("plain") else metric["raw"]
            writer.writerow([metric["label"], value])
        writer.writerow([])
        writer.writerow(report.get("headers") or [])
        for row in report.get("rows") or []:
            writer.writerow(list(row))


def choose_save_path(parent: QWidget, title: str, suggested: str, file_filter: str) -> str:
    path, _ = QFileDialog.getSaveFileName(parent, title, suggested, file_filter)
    return path
