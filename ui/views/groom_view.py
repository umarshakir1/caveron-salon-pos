"""Multi-session Royal and Essential packages."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.utils import PAY_CASH, PAY_TRANSFER, PAYMENT_MODES, format_date, money
from services.printer_service import PrinterService, build_groom_statement, build_visit_slip
from ui.dialogs import ReceiptDialog
from ui.widgets import button, confirm, fill_table, page_header, page_layout, run_action, style_table, warn


class GroomView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.rows = []
        self.current = None
        self.printer = PrinterService()
        layout = page_layout(self)
        layout.addWidget(page_header("Signature", "Groom Packages", "Royal and Essential packages across Mayon, Barat, and Valima."))
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search client, phone, or package")
        self.search.textChanged.connect(lambda _text: self.refresh())
        self.status = QComboBox()
        self.status.addItem("Active", "active")
        self.status.addItem("All", "")
        self.status.addItem("Completed", "completed")
        self.status.addItem("Cancelled", "cancelled")
        self.status.currentIndexChanged.connect(lambda _index: self.refresh())
        enroll = button("Enroll client", "primary")
        enroll.clicked.connect(self._enroll)
        tools.addWidget(self.search, 1)
        tools.addWidget(self.status)
        tools.addWidget(enroll)
        layout.addLayout(tools)
        splitter = QSplitter()
        self.table = QTableWidget()
        style_table(self.table)
        self.table.itemSelectionChanged.connect(self._selected)
        splitter.addWidget(self.table)
        self.detail = QWidget()
        self.detail_layout = QVBoxLayout(self.detail)
        self.detail_layout.setContentsMargins(8, 0, 0, 0)
        splitter.addWidget(self.detail)
        splitter.setSizes([640, 520])
        layout.addWidget(splitter, 1)
        self._empty_detail()

    def refresh(self) -> None:
        selected = self.current["id"] if self.current else None
        self.rows = self.host.db.list_contracts(self.status.currentData() or "", self.search.text().strip())
        fill_table(
            self.table,
            ["Client", "Package", "Paid", "Balance", "Sessions", "Status"],
            [
                [
                    row["customer_name"],
                    row["package_name"],
                    money(row["paid"]),
                    money(row["balance"]),
                    f"{int(row['used_qty'])} / {int(row['total_qty'])}",
                    row["status"].title(),
                ]
                for row in self.rows
            ],
        )
        if selected:
            for index, row in enumerate(self.rows):
                if row["id"] == selected:
                    self.table.blockSignals(True)
                    self.table.selectRow(index)
                    self.table.blockSignals(False)
                    contract = self.host.db.get_contract(selected)
                    if contract:
                        self.current = contract
                        self._show(contract)
                    return
        self.current = None
        self._empty_detail()

    def _empty_detail(self) -> None:
        self._clear_detail()
        note = QLabel("Select a package to see sessions, payments, and event dates.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        self.detail_layout.addWidget(note)
        self.detail_layout.addStretch()

    def _clear_detail(self) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return
        contract = self.host.db.get_contract(self.rows[row]["id"])
        if contract:
            self.current = contract
            self._show(contract)

    def _show(self, contract: dict) -> None:
        self._clear_detail()
        title = QLabel(f"{contract['customer_name']}  ·  {contract['package_name']}")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 18px;")
        money_line = QLabel(f"Price {money(contract['total_price'])}   ·   Paid {money(contract['paid'])}   ·   Balance {money(contract['balance'])}")
        money_line.setObjectName("eyebrow")
        self.detail_layout.addWidget(title)
        self.detail_layout.addWidget(money_line)
        dates = QHBoxLayout()
        self.mayon = self._date(contract.get("mayon_date"))
        self.barat = self._date(contract.get("barat_date"))
        self.valima = self._date(contract.get("valima_date"))
        for label, widget in (("Mayon", self.mayon), ("Barat", self.barat), ("Valima", self.valima)):
            box = QVBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("fieldLabel")
            box.addWidget(caption)
            box.addWidget(widget)
            dates.addLayout(box)
        self.detail_layout.addLayout(dates)
        self.notes = QTextEdit(contract.get("notes") or "")
        self.notes.setFixedHeight(60)
        save_meta = button("Save dates & notes", "ghost", tiny=True)
        save_meta.clicked.connect(self._save_meta)
        self.detail_layout.addWidget(self.notes)
        self.detail_layout.addWidget(save_meta, alignment=Qt.AlignmentFlag.AlignLeft)

        for session in contract.get("sessions") or []:
            frame = QFrame()
            frame.setObjectName("card")
            row = QHBoxLayout(frame)
            label = QLabel(f"{session['name']}   ·   {session['used_qty']} of {session['total_qty']} used")
            label.setWordWrap(True)
            use = button("Mark visit & print", "primary", tiny=True)
            undo = button("Undo", "ghost", tiny=True)
            use.clicked.connect(lambda _checked=False, sid=session["id"]: self._use(sid))
            undo.clicked.connect(lambda _checked=False, sid=session["id"]: self._undo(sid))
            row.addWidget(label, 1)
            row.addWidget(use)
            row.addWidget(undo)
            self.detail_layout.addWidget(frame)

        pay_row = QHBoxLayout()
        self.pay_amount = QSpinBox()
        self.pay_amount.setRange(0, 5_000_000)
        self.pay_amount.setPrefix("Rs. ")
        self.pay_amount.setValue(int(max(0, round(contract["balance"]))))
        self.pay_mode = QComboBox()
        for mode in (PAY_CASH, "Card / POS Machine", PAY_TRANSFER):
            self.pay_mode.addItem(mode, mode)
        record = button("Record payment", "gold", tiny=True)
        record.clicked.connect(self._pay)
        pay_row.addWidget(self.pay_amount)
        pay_row.addWidget(self.pay_mode)
        pay_row.addWidget(record)
        self.detail_layout.addLayout(pay_row)
        actions = QHBoxLayout()
        statement = button("Print statement", "ghost", tiny=True)
        complete = button("Mark complete", "ghost", tiny=True)
        cancel = button("Cancel package", "danger", tiny=True)
        statement.clicked.connect(self._statement)
        complete.clicked.connect(lambda: self._status("completed"))
        cancel.clicked.connect(self._cancel)
        actions.addWidget(statement)
        actions.addWidget(complete)
        actions.addWidget(cancel)
        self.detail_layout.addLayout(actions)
        self.detail_layout.addStretch()

    def _date(self, value: str | None) -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd MMM yyyy")
        editor.setSpecialValueText("Not set")
        editor.setMinimumDate(QDate(1900, 1, 1))
        if value:
            year, month, day = [int(part) for part in value[:10].split("-")]
            editor.setDate(QDate(year, month, day))
        else:
            editor.setDate(editor.minimumDate())
        return editor

    def _iso(self, editor: QDateEdit) -> str:
        if editor.date() == editor.minimumDate():
            return ""
        value = editor.date()
        return f"{value.year():04d}-{value.month():02d}-{value.day():02d}"

    def _save_meta(self) -> None:
        if not self.current:
            return
        self.host.db.update_contract_meta(self.current["id"], self._iso(self.mayon), self._iso(self.barat), self._iso(self.valima), self.notes.toPlainText())
        self.refresh()

    def _use(self, session_id: int) -> None:
        contract = run_action(self, lambda: self.host.db.use_groom_session(session_id))
        if not contract:
            return
        session = next(item for item in contract["sessions"] if item["id"] == session_id)
        settings = self.host.db.get_settings()
        lines = build_visit_slip(contract, session, settings)
        ok, message = self.printer.print_lines(lines, settings, {"cash_amount": 0})
        invoice = {
            "invoice_no": f"VISIT-{contract['id']}-{session_id}",
            "created_at": contract.get("created_at"),
            "customer_name": contract["customer_name"],
            "customer_phone": contract.get("phone"),
            "status": "paid",
            "items": [{"name": session["name"], "qty": 1, "unit_price": 0, "line_total": 0, "staff_name": "", "detail": f"{session['used_qty']} of {session['total_qty']}"}],
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
            "notes": contract["package_name"],
        }
        text = "Visit saved." if ok else "Visit saved. The printer did not print.\n" + message
        ReceiptDialog(invoice, settings, self, text).exec()
        self.current = contract
        self.refresh()

    def _undo(self, session_id: int) -> None:
        if run_action(self, lambda: self.host.db.undo_groom_session(session_id)):
            self.refresh()

    def _pay(self) -> None:
        if not self.current:
            return
        updated = run_action(
            self,
            lambda: self.host.db.add_groom_payment(
                self.current["id"],
                self.pay_amount.value(),
                self.pay_mode.currentData(),
                self.host.user["username"],
            ),
        )
        if not updated:
            return
        payment = updated["payments"][-1]
        invoice = self.host.db.get_invoice(payment["invoice_id"]) if payment.get("invoice_id") else None
        self.current = updated
        self.refresh()
        if invoice:
            settings = self.host.db.get_settings()
            ok, message = self.printer.print_invoice(invoice, settings)
            text = "Payment saved." if ok else "Payment saved. The printer did not print.\n" + message
            ReceiptDialog(invoice, settings, self, text).exec()

    def _statement(self) -> None:
        if not self.current:
            return
        contract = self.host.db.get_contract(self.current["id"])
        settings = self.host.db.get_settings()
        lines = build_groom_statement(contract, settings)
        ok, message = self.printer.print_lines(lines, settings, {"cash_amount": 0, "invoice_no": f"GROOM-{contract['id']:04d}"})
        fake = {
            "invoice_no": f"GROOM-{contract['id']:04d}",
            "created_at": contract.get("created_at"),
            "customer_name": contract["customer_name"],
            "customer_phone": contract.get("phone"),
            "status": "paid",
            "items": [{"name": session["name"], "qty": 1, "unit_price": 0, "line_total": 0, "staff_name": "", "detail": f"{session['used_qty']} of {session['total_qty']} used"} for session in contract["sessions"]],
            "subtotal": contract["total_price"],
            "discount_amount": 0,
            "tax_amount": 0,
            "tax_pct": 0,
            "total": contract["balance"],
            "payment_mode": "Balance due",
            "cash_amount": 0,
            "card_amount": 0,
            "transfer_amount": 0,
            "cash_tendered": contract["paid"],
            "change_due": 0,
            "notes": f"Paid {money(contract['paid'])}",
        }
        text = "Statement sent to the printer." if ok else "Printer did not print.\n" + message
        ReceiptDialog(fake, settings, self, text).exec()

    def _status(self, status: str) -> None:
        if not self.current:
            return
        run_action(self, lambda: self.host.db.set_contract_status(self.current["id"], status))
        self.refresh()

    def _cancel(self) -> None:
        if not self.current:
            return
        if not confirm(self, "Cancel this package? Payments already taken stay in revenue. Record a refund under Expenses if money is returned."):
            return
        self._status("cancelled")

    def _enroll(self) -> None:
        dialog = EnrollDialog(self.host, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()


class EnrollDialog(QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.host = host
        self.setWindowTitle("Enroll groom package")
        self.resize(520, 560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.package = QComboBox()
        self.packages = host.db.list_packages(active_only=True, groom_only=True)
        for package in self.packages:
            self.package.addItem(f"{package['name']}  ·  {money(package['price'])}", package["id"])
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.mayon = self._date()
        self.barat = self._date()
        self.valima = self._date()
        self.advance = QSpinBox()
        self.advance.setRange(0, 5_000_000)
        self.advance.setPrefix("Rs. ")
        self.mode = QComboBox()
        for mode in (PAY_CASH, "Card / POS Machine", PAY_TRANSFER):
            self.mode.addItem(mode, mode)
        self.notes = QTextEdit()
        self.notes.setFixedHeight(70)
        form.addRow("Package", self.package)
        form.addRow("Client", self.name)
        form.addRow("Phone", self.phone)
        form.addRow("Mayon", self.mayon)
        form.addRow("Barat", self.barat)
        form.addRow("Valima", self.valima)
        form.addRow("Advance now", self.advance)
        form.addRow("Payment", self.mode)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        self.package.currentIndexChanged.connect(self._fill_advance)
        self._fill_advance()
        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        save = button("Enroll & print", "primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _date(self) -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("dd MMM yyyy")
        editor.setMinimumDate(QDate(1900, 1, 1))
        editor.setDate(editor.minimumDate())
        editor.setSpecialValueText("Not set")
        return editor

    def _iso(self, editor: QDateEdit) -> str:
        if editor.date() == editor.minimumDate():
            return ""
        value = editor.date()
        return f"{value.year():04d}-{value.month():02d}-{value.day():02d}"

    def _fill_advance(self) -> None:
        package_id = self.package.currentData()
        package = next((item for item in self.packages if item["id"] == package_id), None)
        if package and self.advance.value() == 0:
            self.advance.setValue(int(package["price"]))

    def _save(self) -> None:
        data = {
            "package_id": self.package.currentData(),
            "customer_name": self.name.text(),
            "phone": self.phone.text(),
            "mayon_date": self._iso(self.mayon),
            "barat_date": self._iso(self.barat),
            "valima_date": self._iso(self.valima),
            "advance": self.advance.value(),
            "payment_mode": self.mode.currentData(),
            "notes": self.notes.toPlainText(),
            "username": self.host.user["username"],
        }
        contract = run_action(self, lambda: self.host.db.enroll_groom(data))
        if not contract:
            return
        if contract.get("payments"):
            invoice_id = contract["payments"][-1].get("invoice_id")
            invoice = self.host.db.get_invoice(invoice_id) if invoice_id else None
            if invoice:
                settings = self.host.db.get_settings()
                ok, message = PrinterService().print_invoice(invoice, settings)
                text = "Package enrolled." if ok else "Package enrolled. The printer did not print.\n" + message
                ReceiptDialog(invoice, settings, self, text).exec()
        self.accept()
