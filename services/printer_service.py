"""ESC/POS and Windows graphic printing for Black Copper and other printers."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from core.paths import resource
from core.utils import PAY_CASH, PAY_SPLIT, format_date, money, now_str, pair_line, slip_text, wrap_text
from services.imaging import image_to_raster, prepare_logo
from services.slip_render import render_slip_image

PAPER_CHARS = {"80": 48, "58": 32}
PAPER_DOTS = {"80": 512, "58": 384}


def sample_invoice() -> dict:
    return {
        "invoice_no": "CV-TEST-0001",
        "created_at": now_str(),
        "customer_name": "Ali Hassan",
        "customer_phone": "03001234567",
        "status": "paid",
        "items": [
            {"name": "Hair Cut", "qty": 1, "unit_price": 500, "line_total": 500, "staff_name": "Ahmed Khan", "detail": ""},
            {"name": "Beard", "qty": 1, "unit_price": 300, "line_total": 300, "staff_name": "Bilal Raza", "detail": ""},
            {
                "name": "Deal 4",
                "qty": 1,
                "unit_price": 800,
                "line_total": 800,
                "staff_name": "Ahmed Khan",
                "detail": "Bespoke Hair Cut\nBeard Sculpting / Shave\nSignature Blowout / Texture & Style",
            },
        ],
        "subtotal": 1600,
        "discount_amount": 100,
        "tax_pct": 0,
        "tax_amount": 0,
        "total": 1500,
        "payment_mode": PAY_CASH,
        "cash_amount": 1500,
        "card_amount": 0,
        "transfer_amount": 0,
        "cash_tendered": 2000,
        "change_due": 500,
        "notes": "",
    }


def build_receipt(invoice: dict, settings: dict) -> list[dict]:
    width = PAPER_CHARS.get(str(settings.get("paper") or "80"), 48)
    lines: list[dict] = []

    def center(text: str, bold: bool = False, big: bool = False) -> None:
        for part in wrap_text(text, max(8, width // 2 if big else width)):
            lines.append({"t": "text", "align": "center", "text": part, "bold": bold, "big": big})

    def left(text: str, bold: bool = False) -> None:
        for part in wrap_text(text, width) or [""]:
            lines.append({"t": "text", "align": "left", "text": part, "bold": bold})

    def pair(label: str, value: str, bold: bool = False) -> None:
        value = slip_text(value)
        room = max(8, width - len(value) - 1)
        chunks = wrap_text(label, room) or [""]
        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                lines.append({"t": "pair", "left": chunk, "right": value, "bold": bold})
            else:
                lines.append({"t": "text", "align": "left", "text": chunk, "bold": bold})

    def rule() -> None:
        lines.append({"t": "rule"})

    if settings.get("opt_logo", True):
        lines.append({"t": "logo"})
    center(settings.get("salon_name") or "CAVERON", bold=True, big=True)
    center(settings.get("tagline") or "CRAFT YOUR STYLE")
    center(settings.get("subtitle") or "SALON & BARBER")
    center(settings.get("est_year") or "EST. 1987")
    if settings.get("opt_address", True):
        if settings.get("address"):
            center(settings["address"])
        if settings.get("phone"):
            center(settings["phone"])
        if settings.get("ntn"):
            center("NTN / STRN " + settings["ntn"])
        if settings.get("hours"):
            center(settings["hours"])
    if settings.get("header_note"):
        lines.append({"t": "gap"})
        center(settings["header_note"])
    rule()
    if invoice.get("status") == "void":
        center("VOID BILL", bold=True)
        rule()
    pair("Invoice", invoice.get("invoice_no") or "")
    pair("Date", (invoice.get("created_at") or "")[:16])
    if settings.get("opt_customer", True):
        pair("Client", invoice.get("customer_name") or "Walk-in Client")
        if invoice.get("customer_phone"):
            pair("Phone", invoice["customer_phone"])
    rule()
    for item in invoice.get("items") or []:
        pair(item.get("name") or "Item", money(item.get("line_total") or 0))
        qty = int(item.get("qty") or 1)
        if qty > 1:
            left(f"  {qty} x {money(item.get('unit_price') or 0)}")
        if settings.get("opt_stylist", True) and item.get("staff_name"):
            left(f"  Stylist: {item['staff_name']}")
        detail = item.get("detail") or ""
        for detail_line in detail.splitlines():
            left("  " + detail_line)
    rule()
    pair("Subtotal", money(invoice.get("subtotal") or 0))
    if float(invoice.get("discount_amount") or 0):
        pair("Discount", "-" + money(invoice["discount_amount"]))
    if float(invoice.get("tax_amount") or 0):
        pair(f"Service {float(invoice.get('tax_pct') or 0):g}%", money(invoice["tax_amount"]))
    pair("TOTAL", money(invoice.get("total") or 0), bold=True)
    pair("Payment", invoice.get("payment_mode") or "")
    mode = invoice.get("payment_mode") or ""
    if mode == PAY_CASH:
        pair("Received", money(invoice.get("cash_tendered") or 0))
        pair("Change", money(invoice.get("change_due") or 0))
    elif mode == PAY_SPLIT:
        if float(invoice.get("cash_amount") or 0):
            pair("Cash", money(invoice["cash_amount"]))
        if float(invoice.get("card_amount") or 0):
            pair("Card", money(invoice["card_amount"]))
        if float(invoice.get("transfer_amount") or 0):
            pair("Transfer", money(invoice["transfer_amount"]))
    if invoice.get("notes"):
        left(invoice["notes"])
    rule()
    footer = settings.get("footer_note") or "Thank you for visiting CAVERON - Craft Your Style"
    center(footer)
    if settings.get("opt_barcode", True) and invoice.get("invoice_no"):
        lines.append({"t": "gap"})
        lines.append({"t": "barcode", "text": invoice["invoice_no"]})
    lines.append({"t": "gap"})
    return lines


def build_closing_slip(snap: dict, settings: dict) -> list[dict]:
    width = PAPER_CHARS.get(str(settings.get("paper") or "80"), 48)
    lines: list[dict] = []

    def center(text: str, bold: bool = False, big: bool = False) -> None:
        for part in wrap_text(text, max(8, width // 2 if big else width)):
            lines.append({"t": "text", "align": "center", "text": part, "bold": bold, "big": big})

    def left(text: str, bold: bool = False) -> None:
        for part in wrap_text(text, width) or [""]:
            lines.append({"t": "text", "align": "left", "text": part, "bold": bold})

    def pair(label: str, value: str, bold: bool = False) -> None:
        value = slip_text(value)
        room = max(8, width - len(value) - 1)
        chunks = wrap_text(label, room) or [""]
        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                lines.append({"t": "pair", "left": chunk, "right": value, "bold": bold})
            else:
                lines.append({"t": "text", "align": "left", "text": chunk, "bold": bold})

    def rule() -> None:
        lines.append({"t": "rule"})

    if settings.get("opt_logo", True):
        lines.append({"t": "logo"})
    center(settings.get("salon_name") or "CAVERON", bold=True, big=True)
    center(settings.get("tagline") or "CRAFT YOUR STYLE")
    center("DAY END SLIP", bold=True)
    center(format_date(snap.get("date") or ""))
    rule()
    variance = snap.get("variance")
    if variance == "match":
        center("DRAWER MATCHED", bold=True)
    elif variance == "short":
        center("SHORT " + money(abs(snap.get("difference") or 0)), bold=True)
    elif variance == "over":
        center("OVER " + money(snap.get("difference") or 0), bold=True)
    else:
        center("REGISTER STILL OPEN", bold=True)
    rule()
    pair("Opening", money(snap.get("opening") or 0))
    pair("Cash sales", money(snap.get("cash_sales") or 0))
    pair("Online sales", money(snap.get("online_sales") or 0))
    pair("Daily expenses", money(snap.get("daily_cash_expenses") or 0))
    pair("Monthly expenses", money(snap.get("monthly_cash_expenses") or 0))
    pair("Cash advances", money(snap.get("cash_advances") or 0))
    pair("Cash out", money(snap.get("cash_payments") or 0))
    online_expenses = float(snap.get("daily_other_expenses") or 0) + float(snap.get("monthly_other_expenses") or 0)
    pair("Online expenses", money(online_expenses))
    rule()
    pair("EXPECTED", money(snap.get("expected") or 0), bold=True)
    counted = "—" if snap.get("actual") is None else money(snap.get("actual") or 0)
    pair("COUNTED", counted, bold=True)
    if snap.get("difference") is None:
        pair("DIFFERENCE", "—", bold=True)
    else:
        pair("DIFFERENCE", money(snap.get("difference") or 0), bold=True)
    rule()
    center("STAFF", bold=True)
    staff = snap.get("staff") or []
    if not staff:
        center("No staff sales today")
    for member in staff:
        pair(member.get("name") or "Staff", money(member.get("work") or 0))
        if member.get("percent"):
            left(f"  {float(member['percent']):g}%  {money(member.get('commission') or 0)}")
        else:
            left("  No commission")
    rule()
    center("ADVANCES", bold=True)
    advances = snap.get("advances") or []
    if not advances:
        center("No advances today")
    for row in advances:
        pair(row.get("staff_name") or "Staff", money(row.get("amount") or 0))
        left("  " + (row.get("payment_mode") or "Cash"))
    if snap.get("note"):
        rule()
        left(snap["note"])
    rule()
    center("Online sales and expenses stay out")
    center("End of register")
    lines.append({"t": "gap"})
    return lines


def build_visit_slip(contract: dict, session: dict, settings: dict) -> list[dict]:
    invoice = {
        "invoice_no": f"VISIT-{contract['id']}-{session['id']}",
        "created_at": now_str(),
        "customer_name": contract.get("customer_name"),
        "customer_phone": contract.get("phone"),
        "status": "paid",
        "items": [
            {
                "name": session["name"],
                "qty": 1,
                "unit_price": 0,
                "line_total": 0,
                "staff_name": "",
                "detail": f"Session {session['used_qty']} of {session['total_qty']}\n{contract.get('package_name')}",
            }
        ],
        "subtotal": 0,
        "discount_amount": 0,
        "tax_pct": 0,
        "tax_amount": 0,
        "total": 0,
        "payment_mode": "Package visit",
        "cash_amount": 0,
        "card_amount": 0,
        "transfer_amount": 0,
        "cash_tendered": 0,
        "change_due": 0,
        "notes": f"Balance {money(contract.get('balance') or 0)}",
    }
    return build_receipt(invoice, settings)


def build_groom_statement(contract: dict, settings: dict) -> list[dict]:
    items = []
    for session in contract.get("sessions") or []:
        items.append(
            {
                "name": session["name"],
                "qty": 1,
                "unit_price": 0,
                "line_total": 0,
                "staff_name": "",
                "detail": f"{session['used_qty']} of {session['total_qty']} used",
            }
        )
    notes = []
    if contract.get("mayon_date"):
        notes.append("Mayon " + contract["mayon_date"])
    if contract.get("barat_date"):
        notes.append("Barat " + contract["barat_date"])
    if contract.get("valima_date"):
        notes.append("Valima " + contract["valima_date"])
    notes.append(f"Paid {money(contract.get('paid') or 0)}  Balance {money(contract.get('balance') or 0)}")
    invoice = {
        "invoice_no": f"GROOM-{contract['id']:04d}",
        "created_at": contract.get("created_at") or now_str(),
        "customer_name": contract.get("customer_name"),
        "customer_phone": contract.get("phone"),
        "status": "paid",
        "items": items or [{"name": contract.get("package_name"), "qty": 1, "unit_price": contract.get("total_price") or 0, "line_total": contract.get("total_price") or 0, "staff_name": "", "detail": ""}],
        "subtotal": contract.get("total_price") or 0,
        "discount_amount": 0,
        "tax_pct": 0,
        "tax_amount": 0,
        "total": contract.get("balance") or 0,
        "payment_mode": "Balance due",
        "cash_amount": 0,
        "card_amount": 0,
        "transfer_amount": 0,
        "cash_tendered": contract.get("paid") or 0,
        "change_due": 0,
        "notes": " | ".join(notes),
    }
    lines = build_receipt(invoice, settings)
    return lines


class PrinterService:
    def list_printers(self) -> list[str]:
        names: list[str] = []
        try:
            import win32print

            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            for printer in win32print.EnumPrinters(flags):
                names.append(printer[2])
        except Exception:
            logging.exception("win32print enumeration failed")
        if not names:
            try:
                names = list(QPrinterInfo.availablePrinterNames())
            except Exception:
                logging.exception("Qt printer enumeration failed")
        unique = []
        for name in names:
            if name and name not in unique:
                unique.append(name)

        def rank(name: str) -> tuple[int, str]:
            lowered = name.lower()
            keys = ("black copper", "bc-85", "bc-90", "bc-80", "pos-80", "pos-58", "thermal", "xp-")
            for index, key in enumerate(keys):
                if key in lowered:
                    return index, lowered
            return 99, lowered

        return sorted(unique, key=rank)

    def print_invoice(self, invoice: dict, settings: dict) -> tuple[bool, str]:
        return self.print_lines(build_receipt(invoice, settings), settings, invoice)

    def print_lines(self, lines: list[dict], settings: dict, invoice: dict | None = None) -> tuple[bool, str]:
        try:
            target = settings.get("output_target") or "windows"
            if target == "network":
                self._send_network(self._raw_bytes(lines, settings, invoice), settings)
            elif target == "usb":
                self._send_usb(self._raw_bytes(lines, settings, invoice), settings)
            elif settings.get("print_mode") == "graphic":
                self._send_graphic(lines, settings)
                if settings.get("opt_drawer") and invoice and float(invoice.get("cash_amount") or 0) > 0:
                    self._try_drawer(settings)
            else:
                self._send_windows_raw(self._raw_bytes(lines, settings, invoice), settings)
            return True, "Slip sent to the printer."
        except Exception as exc:
            logging.exception("Print failed")
            return False, str(exc)

    def export_pdf(self, lines: list[dict], settings: dict, path: str) -> None:
        image = self._image(lines, settings)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        self._paint_printer(printer, image, settings)
        if not os.path.exists(path):
            raise RuntimeError("PDF was not created.")

    def _image(self, lines: list[dict], settings: dict):
        return render_slip_image(lines, str(settings.get("paper") or "80"), self._logo_path(settings))

    def _logo_path(self, settings: dict) -> str:
        if not settings.get("opt_logo", True):
            return ""
        thermal = resource("assets", "caveron_logo_thermal.png")
        if os.path.exists(thermal):
            return thermal
        return resource("assets", "caveron_logo.png")

    def _raw_bytes(self, lines: list[dict], settings: dict, invoice: dict | None) -> bytes:
        width = PAPER_CHARS.get(str(settings.get("paper") or "80"), 48)
        chunks = [b"\x1b@", b"\x1bt\x00"]
        for line in lines:
            kind = line.get("t")
            if kind == "logo":
                logo = prepare_logo(self._logo_path(settings), PAPER_DOTS.get(str(settings.get("paper") or "80"), 512))
                if logo is not None:
                    chunks.append(b"\x1ba\x01")
                    chunks.append(image_to_raster(logo))
                    chunks.append(b"\n")
                    chunks.append(b"\x1ba\x00")
            elif kind == "gap":
                chunks.append(b"\n")
            elif kind == "rule":
                chunks.append(("-" * width + "\n").encode("cp437", errors="replace"))
            elif kind == "barcode":
                text = slip_text(line.get("text") or "")[:40]
                payload = b"{B" + text.encode("ascii", errors="replace")
                chunks.append(b"\x1ba\x01")
                chunks.append(bytes([0x1D, 0x68, 70, 0x1D, 0x77, 2, 0x1D, 0x48, 2]))
                chunks.append(bytes([0x1D, 0x6B, 73, len(payload)]) + payload)
                chunks.append(b"\n")
                chunks.append(b"\x1ba\x00")
            else:
                align = b"\x1ba\x01" if line.get("align") == "center" else b"\x1ba\x00"
                chunks.append(align)
                chunks.append(b"\x1bE" + (b"\x01" if line.get("bold") or line.get("big") else b"\x00"))
                chunks.append(b"\x1d!" + (b"\x11" if line.get("big") else b"\x00"))
                if kind == "pair":
                    text = pair_line(line.get("left") or "", line.get("right") or "", width)
                else:
                    text = slip_text(line.get("text") or "")
                chunks.append(text.encode("cp437", errors="replace") + b"\n")
                chunks.append(b"\x1d!\x00")
                chunks.append(b"\x1bE\x00")
        chunks.append(b"\n\n")
        if invoice and settings.get("opt_drawer") and float(invoice.get("cash_amount") or 0) > 0:
            chunks.append(b"\x1bp\x00\x19\xfa")
        if settings.get("opt_cut", True):
            chunks.append(b"\x1dVB\x00")
        return b"".join(chunks)

    def _send_windows_raw(self, payload: bytes, settings: dict) -> None:
        name = (settings.get("printer_name") or "").strip()
        if not name:
            raise RuntimeError("No Windows printer is selected. Choose one in Settings, or save a PDF from the slip.")
        try:
            import win32print
        except Exception as exc:
            raise RuntimeError("Windows raw printing is unavailable. Switch Print Mode to Windows Graphic Print.") from exc
        handle = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(handle, 1, ("CAVERON Slip", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                written = win32print.WritePrinter(handle, payload)
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)
        if not written:
            raise RuntimeError("The printer accepted the job but wrote no data.")

    def _send_graphic(self, lines: list[dict], settings: dict) -> None:
        name = (settings.get("printer_name") or "").strip()
        if not name:
            raise RuntimeError("No Windows printer is selected.")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(name)
        self._paint_printer(printer, self._image(lines, settings), settings)

    def _paint_printer(self, printer: QPrinter, image, settings: dict) -> None:
        paper = str(settings.get("paper") or "80")
        width_mm = 80.0 if paper == "80" else 58.0
        height_mm = max(50.0, width_mm * image.height() / max(1, image.width()))
        printer.setPageSize(QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter))
        printer.setPageMargins(QMarginsF(1, 1, 1, 1), QPageLayout.Unit.Millimeter)
        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError("Windows could not start the print job. Check that the printer is online.")
        painter.drawImage(painter.viewport(), image)
        painter.end()

    def _send_network(self, payload: bytes, settings: dict) -> None:
        ip = (settings.get("network_ip") or "").strip()
        if not ip:
            raise RuntimeError("Enter the printer IP address.")
        port = int(settings.get("network_port") or 9100)
        try:
            from escpos.printer import Network
        except Exception as exc:
            raise RuntimeError("Network printing needs the python-escpos package.") from exc
        printer = Network(ip, port=port, timeout=8)
        try:
            self._write_escpos(printer, payload)
        finally:
            try:
                printer.close()
            except Exception:
                pass

    def _send_usb(self, payload: bytes, settings: dict) -> None:
        vid = _parse_id(settings.get("usb_vid") or "")
        pid = _parse_id(settings.get("usb_pid") or "")
        if vid is None or pid is None:
            raise RuntimeError("Enter the USB VID and PID, for example 0x0416 and 0x5011.")
        try:
            from escpos.printer import Usb
        except Exception as exc:
            raise RuntimeError("USB printing needs the python-escpos package.") from exc
        printer = Usb(vid, pid, timeout=8)
        try:
            self._write_escpos(printer, payload)
        finally:
            try:
                printer.close()
            except Exception:
                pass

    @staticmethod
    def _write_escpos(printer, payload: bytes) -> None:
        if hasattr(printer, "_raw"):
            printer._raw(payload)
        else:
            printer.device.write(payload)

    def _try_drawer(self, settings: dict) -> None:
        try:
            self._send_windows_raw(b"\x1b@\x1bp\x00\x19\xfa", settings)
        except Exception:
            logging.exception("Cash drawer kick failed")


def _parse_id(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    except ValueError:
        return None
