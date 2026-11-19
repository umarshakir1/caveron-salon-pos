"""Bills, prices, and client dialogs."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.utils import format_dt, money
from services.printer_service import PrinterService, build_receipt
from services.report_service import choose_save_path
from ui.branding import thermal_logo_path
from ui.slip_view import SlipPreview
from ui.widgets import button, fill_table, info, style_table, warn


class PriceDialog(QDialog):
    def __init__(self, name: str, min_price: float, max_price: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agreed price")
        self.setModal(True)
        self.price = float(min_price)
        self.min_price = float(min_price)
        self.max_price = float(max_price)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        title = QLabel(name)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 18px;")
        hint = QLabel(f"Menu range {money(min_price)} – {money(max_price)}. The chair can agree a nearby price.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        row = QHBoxLayout()
        mid = round((min_price + max_price) / 2)
        for label, value in (("Minimum", min_price), ("Middle", mid), ("Maximum", max_price)):
            preset = button(f"{label}\n{money(value)}", "ghost")
            preset.clicked.connect(lambda _checked=False, amount=value: self._set(amount))
            row.addWidget(preset)
        layout.addLayout(row)
        self.spin = QSpinBox()
        self.spin.setRange(1, 1_000_000)
        self.spin.setValue(int(min_price))
        self.spin.setPrefix("Rs. ")
        self.spin.valueChanged.connect(self._on_spin)
        layout.addWidget(self.spin)
        self.note = QLabel("")
        self.note.setObjectName("eyebrow")
        layout.addWidget(self.note)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = button("Cancel", "ghost")
        ok = button("Add to bill", "primary")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        actions.addWidget(cancel)
        actions.addWidget(ok)
        layout.addLayout(actions)
        self.resize(460, 280)

    def _set(self, amount: float) -> None:
        self.spin.setValue(int(round(amount)))

    def _on_spin(self, value: int) -> None:
        if value < self.min_price or value > self.max_price:
            self.note.setText("Outside the menu range. It can still be billed.")
        else:
            self.note.setText("")

    def _accept(self) -> None:
        self.price = float(self.spin.value())
        self.accept()


class CustomerDialog(QDialog):
    def __init__(self, parent=None, name: str = "", phone: str = "", notes: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Client")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.phone = QLineEdit(phone)
        self.phone.setPlaceholderText("03xx xxxxxxx")
        self.notes = QTextEdit(notes)
        self.notes.setFixedHeight(70)
        form.addRow("Name", self.name)
        form.addRow("Phone", self.phone)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = button("Cancel", "ghost")
        save = button("Save client", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._accept)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)
        self.resize(420, 280)

    def _accept(self) -> None:
        if not self.name.text().strip() or len(self.phone.text().strip()) < 7:
            warn(self, "Name and a phone number are required.")
            return
        self.accept()

    def values(self) -> tuple[str, str, str]:
        return self.name.text().strip(), self.phone.text().strip(), self.notes.toPlainText().strip()


class ReceiptDialog(QDialog):
    def __init__(self, invoice: dict, settings: dict, parent=None, message: str = ""):
        super().__init__(parent)
        self.invoice = invoice
        self.settings = settings
        self.printer = PrinterService()
        self.setWindowTitle(invoice.get("invoice_no") or "Slip")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.message = QLabel(message)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.preview = SlipPreview()
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setWidget(self.preview)
        scroll.setMinimumHeight(420)
        layout.addWidget(scroll, 1)
        actions = QHBoxLayout()
        reprint = button("Print again", "primary")
        pdf = button("Save PDF", "ghost")
        close = button("Close", "ghost")
        reprint.clicked.connect(self._print)
        pdf.clicked.connect(self._pdf)
        close.clicked.connect(self.accept)
        actions.addWidget(reprint)
        actions.addWidget(pdf)
        actions.addStretch()
        actions.addWidget(close)
        layout.addLayout(actions)
        self._refresh()
        self.resize(520, 760)

    def _lines(self):
        return build_receipt(self.invoice, self.settings)

    def _refresh(self) -> None:
        logo = thermal_logo_path() if os.path.exists(thermal_logo_path()) else ""
        self.preview.set_slip(self._lines(), str(self.settings.get("paper") or "80"), logo)

    def _print(self) -> None:
        ok, message = self.printer.print_invoice(self.invoice, self.settings)
        self.message.setText(message if ok else "Printer was not available. The slip is still on screen.\n" + message)

    def _pdf(self) -> None:
        path = choose_save_path(self, "Save slip", f"{self.invoice.get('invoice_no', 'slip')}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.printer.export_pdf(self._lines(), self.settings, path)
            info(self, "Slip saved.")
        except Exception as exc:
            warn(self, f"Could not save the PDF.\n{exc}")


class HistoryDialog(QDialog):
    def __init__(self, db, customer: dict, settings: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.settings = settings
        self.setWindowTitle(customer["name"])
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{customer['name']}  ·  {customer['phone']}  ·  {customer['loyalty_points']} loyalty points"))
        self.table = QTableWidget()
        style_table(self.table)
        self.rows = db.customer_history(customer["id"], 30)
        fill_table(
            self.table,
            ["Invoice", "When", "Total", "Status"],
            [[row["invoice_no"], format_dt(row["created_at"]), money(row["total"]), row["status"]] for row in self.rows],
        )
        layout.addWidget(self.table)
        open_slip = button("View slip", "primary")
        open_slip.clicked.connect(self._open)
        layout.addWidget(open_slip, alignment=Qt.AlignmentFlag.AlignRight)
        self.resize(640, 420)

    def _open(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            warn(self, "Select a bill first.")
            return
        invoice = self.db.get_invoice(self.rows[row]["id"])
        if invoice:
            ReceiptDialog(invoice, self.settings, self).exec()


class PhraseDialog(QDialog):
    def __init__(self, message: str, phrase: str, parent=None):
        super().__init__(parent)
        self.phrase = phrase
        self.setWindowTitle("Confirm")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        label = QLabel(message)
        label.setWordWrap(True)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(phrase)
        layout.addWidget(label)
        layout.addWidget(self.edit)
        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        self.ok = button("Reset", "danger")
        cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self._accept)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.ok)
        layout.addLayout(actions)
        self.resize(460, 200)

    def _accept(self) -> None:
        if self.edit.text().strip() != self.phrase:
            warn(self, f"Type {self.phrase} to continue.")
            return
        self.accept()
