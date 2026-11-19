"""Salary, commission, advances, and printable slips."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.utils import ADJUSTMENT_KINDS, money, month_bounds
from services.report_service import choose_save_path, print_html, salary_html, write_pdf
from ui.widgets import button, fill_table, info, page_header, page_layout, run_action, style_table, warn


def _tab(text: str):
    widget = button(text, "pill")
    widget.setCheckable(True)
    widget.setMinimumWidth(140)
    return widget


class PayrollView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.rows = []
        self.adjustments = []
        layout = page_layout(self)
        layout.addWidget(page_header("Accounts", "Payroll", "Base pay, commission from bills, advances, and the net slip."))
        tabs = QHBoxLayout()
        self.period_tab = _tab("This period")
        self.history_tab = _tab("History")
        self.period_tab.setChecked(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.period_tab)
        group.addButton(self.history_tab)
        self.period_tab.clicked.connect(lambda: self._show_page(0))
        self.history_tab.clicked.connect(lambda: self._show_page(1))
        tabs.addWidget(self.period_tab)
        tabs.addWidget(self.history_tab)
        tabs.addStretch()
        layout.addLayout(tabs)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        period_page = QWidget()
        period_layout = QVBoxLayout(period_page)
        period_layout.setContentsMargins(0, 0, 0, 0)
        period_layout.setSpacing(12)
        period = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("This month", "month")
        self.mode.addItem("Custom range", "custom")
        today = date.today()
        self.month = QComboBox()
        for offset in range(0, 18):
            year = today.year
            month = today.month - offset
            while month <= 0:
                month += 12
                year -= 1
            self.month.addItem(date(year, month, 1).strftime("%B %Y"), (year, month))
        self.start = QDateEdit()
        self.end = QDateEdit()
        for editor in (self.start, self.end):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd MMM yyyy")
        start, end = month_bounds(today.year, today.month)
        self._set_dates(start, end)
        calculate = button("Calculate", "primary")
        calculate.clicked.connect(self._calculate)
        self.mode.currentIndexChanged.connect(self._toggle)
        self.month.currentIndexChanged.connect(self._month_changed)
        period.addWidget(self.mode)
        period.addWidget(self.month)
        period.addWidget(self.start)
        period.addWidget(self.end)
        period.addWidget(calculate)
        period.addStretch()
        period_layout.addLayout(period)
        self.table = QTableWidget()
        style_table(self.table)
        self.table.verticalHeader().setDefaultSectionSize(44)
        period_layout.addWidget(self.table, 3)
        actions = QHBoxLayout()
        paid = button("Mark as paid", "gold")
        slip = button("Print salary slip", "primary")
        pdf = button("Save slip PDF", "ghost")
        paid.clicked.connect(self._mark_paid)
        slip.clicked.connect(self._print)
        pdf.clicked.connect(self._pdf)
        actions.addWidget(paid)
        actions.addWidget(slip)
        actions.addWidget(pdf)
        actions.addStretch()
        period_layout.addLayout(actions)

        box = QFrame()
        box.setObjectName("card")
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        grid = QGridLayout(box)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.addWidget(QLabel("Add an adjustment"), 0, 0, 1, 6)
        self.staff = QComboBox()
        self.kind = QComboBox()
        self.kind.addItems(ADJUSTMENT_KINDS)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(1, 5_000_000)
        self.amount.setDecimals(0)
        self.amount.setPrefix("Rs. ")
        self.amount.setGroupSeparatorShown(True)
        self.amount.setMinimumWidth(150)
        self.adj_date = QDateEdit()
        self.adj_date.setCalendarPopup(True)
        self.adj_date.setDate(QDate.currentDate())
        self.adj_date.setDisplayFormat("dd MMM yyyy")
        self.pay_mode = QComboBox()
        self.pay_mode.addItem("Cash", "Cash")
        self.pay_mode.addItem("Online", "JazzCash / EasyPaisa / Bank Transfer")
        self.note = QLineEdit()
        self.note.setPlaceholderText("Note")
        add = button("Add", "primary", tiny=True)
        add.clicked.connect(self._add_adjustment)
        fields = (
            ("Staff", self.staff),
            ("Type", self.kind),
            ("Amount", self.amount),
            ("Date", self.adj_date),
            ("Paid by", self.pay_mode),
        )
        for column, (caption, widget) in enumerate(fields):
            caption_label = QLabel(caption)
            caption_label.setObjectName("fieldLabel")
            widget.setMinimumHeight(36)
            grid.addWidget(caption_label, 1, column)
            grid.addWidget(widget, 2, column)
        note_label = QLabel("Note")
        note_label.setObjectName("fieldLabel")
        self.note.setMinimumHeight(36)
        grid.addWidget(note_label, 3, 0)
        grid.addWidget(self.note, 4, 0, 1, 3)
        grid.addWidget(add, 4, 3)
        period_layout.addWidget(box)
        self.stack.addWidget(period_page)

        history_page = QWidget()
        history_layout = QVBoxLayout(history_page)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.setSpacing(10)
        history_tabs = QHBoxLayout()
        self.salary_tab = _tab("Salary history")
        self.adjust_tab = _tab("Advances, tips, bonus")
        self.salary_tab.setChecked(True)
        history_group = QButtonGroup(self)
        history_group.setExclusive(True)
        history_group.addButton(self.salary_tab)
        history_group.addButton(self.adjust_tab)
        self.salary_tab.clicked.connect(lambda: self._show_history(0))
        self.adjust_tab.clicked.connect(lambda: self._show_history(1))
        history_tabs.addWidget(self.salary_tab)
        history_tabs.addWidget(self.adjust_tab)
        history_tabs.addStretch()
        history_layout.addLayout(history_tabs)
        self.history_stack = QStackedWidget()
        self.history_pay = QTableWidget()
        style_table(self.history_pay)
        self.history_pay.verticalHeader().setDefaultSectionSize(40)
        adjust_page = QWidget()
        adjust_layout = QVBoxLayout(adjust_page)
        adjust_layout.setContentsMargins(0, 0, 0, 0)
        adjust_layout.setSpacing(8)
        self.history_adj = QTableWidget()
        style_table(self.history_adj)
        self.history_adj.verticalHeader().setDefaultSectionSize(40)
        remove = button("Remove selected", "danger")
        remove.clicked.connect(self._remove_adjustment)
        adjust_layout.addWidget(self.history_adj, 1)
        adjust_layout.addWidget(remove, alignment=Qt.AlignmentFlag.AlignLeft)
        self.history_stack.addWidget(self.history_pay)
        self.history_stack.addWidget(adjust_page)
        history_layout.addWidget(self.history_stack, 1)
        self.stack.addWidget(history_page)
        self._toggle()

    def _show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.period_tab.setChecked(index == 0)
        self.history_tab.setChecked(index == 1)
        if index == 1:
            self._load_history()

    def _show_history(self, index: int) -> None:
        self.history_stack.setCurrentIndex(index)
        self.salary_tab.setChecked(index == 0)
        self.adjust_tab.setChecked(index == 1)
        self._load_history()

    def _set_dates(self, start: str, end: str) -> None:
        for editor, value in ((self.start, start), (self.end, end)):
            year, month, day = [int(part) for part in value.split("-")]
            editor.setDate(QDate(year, month, day))

    def _toggle(self) -> None:
        custom = self.mode.currentData() == "custom"
        self.month.setVisible(not custom)
        self.start.setEnabled(custom)
        self.end.setEnabled(custom)
        if not custom:
            self._month_changed()

    def _month_changed(self) -> None:
        if self.mode.currentData() != "month":
            return
        year, month = self.month.currentData()
        start, end = month_bounds(year, month)
        self._set_dates(start, end)

    def _period(self) -> tuple[str, str]:
        start = self.start.date()
        end = self.end.date()
        start_s = f"{start.year():04d}-{start.month():02d}-{start.day():02d}"
        end_s = f"{end.year():04d}-{end.month():02d}-{end.day():02d}"
        if end_s < start_s:
            start_s, end_s = end_s, start_s
        return start_s, end_s

    def refresh(self) -> None:
        current = self.staff.currentData()
        self.staff.clear()
        for member in self.host.db.list_staff():
            self.staff.addItem(member["name"], member["id"])
        if current is not None:
            index = self.staff.findData(current)
            if index >= 0:
                self.staff.setCurrentIndex(index)
        start, end = self._period()
        self.rows = self.host.db.list_payroll(start, end)
        self._fill()

    def _calculate(self) -> None:
        start, end = self._period()
        rows = run_action(self, lambda: self.host.db.build_payroll(start, end))
        if rows is not None:
            self.rows = rows
            self._fill()

    def _fill(self) -> None:
        fill_table(
            self.table,
            ["Staff", "Base", "Commission", "Tips", "Bonus", "Advances", "Deductions", "Net", "Status"],
            [
                [
                    row["staff_name"],
                    money(row["base_salary"]),
                    money(row["commission"]),
                    money(row["tips"]),
                    money(row["bonuses"]),
                    money(row["advances"]),
                    money(row["deductions"]),
                    money(row["net_payable"]),
                    row["status"].title(),
                ]
                for row in self.rows
            ],
        )

    def _selected(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.rows):
            warn(self, "Calculate the period, then select a staff row.")
            return None
        return self.rows[index]

    def _mark_paid(self) -> None:
        row = self._selected()
        if not row:
            return
        if run_action(self, lambda: self.host.db.mark_payroll_paid(row["id"]) or True):
            self.refresh()

    def _html(self):
        row = self._selected()
        if not row:
            return None
        full = self.host.db.get_payroll(row["id"])
        return salary_html(full, self.host.db.get_settings()), full

    def _print(self) -> None:
        built = self._html()
        if built:
            print_html(built[0], self)

    def _pdf(self) -> None:
        built = self._html()
        if not built:
            return
        path = choose_save_path(self, "Salary slip", f"{built[1]['staff_name']}-salary.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            write_pdf(built[0], path)
            info(self, "Salary slip saved.")
        except Exception as exc:
            warn(self, f"Could not save the slip.\n{exc}")

    def _add_adjustment(self) -> None:
        if self.staff.currentData() is None:
            warn(self, "Add a staff profile first.")
            return
        value = self.adj_date.date()
        saved = run_action(
            self,
            lambda: self.host.db.save_adjustment(
                {
                    "staff_id": self.staff.currentData(),
                    "adj_date": f"{value.year():04d}-{value.month():02d}-{value.day():02d}",
                    "kind": self.kind.currentText(),
                    "amount": self.amount.value(),
                    "notes": self.note.text(),
                    "payment_mode": self.pay_mode.currentData(),
                }
            ),
        )
        if saved:
            self.note.clear()
            self._calculate()

    def _load_history(self) -> None:
        periods = self.host.db.list_payroll_history()
        fill_table(
            self.history_pay,
            ["From", "To", "Staff", "Base", "Commission", "Tips", "Bonus", "Advances", "Deductions", "Net", "Status"],
            [
                [
                    row["period_start"],
                    row["period_end"],
                    row["staff_name"],
                    money(row["base_salary"]),
                    money(row["commission"]),
                    money(row["tips"]),
                    money(row["bonuses"]),
                    money(row["advances"]),
                    money(row["deductions"]),
                    money(row["net_payable"]),
                    (row["status"] or "").title(),
                ]
                for row in periods
            ],
        )
        self.adjustments = self.host.db.list_all_adjustments()
        fill_table(
            self.history_adj,
            ["Date", "Staff", "Type", "Paid by", "Amount", "Note"],
            [
                [
                    row["adj_date"],
                    row["staff_name"],
                    row["kind"],
                    "Cash" if (row.get("payment_mode") or "Cash") == "Cash" else "Online",
                    money(row["amount"]),
                    row["notes"] or "",
                ]
                for row in self.adjustments
            ],
        )

    def _remove_adjustment(self) -> None:
        index = self.history_adj.currentRow()
        if index < 0 or index >= len(self.adjustments):
            warn(self, "Select an advance, tip, or bonus first.")
            return
        if run_action(self, lambda: self.host.db.delete_adjustment(self.adjustments[index]["id"]) or True):
            self._load_history()
            self._calculate()
