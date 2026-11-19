"""Opening float, yesterday's cash, and the day-end slip."""

from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.utils import format_date, money
from services.printer_service import build_closing_slip
from services.report_service import choose_save_path
from ui.branding import thermal_logo_path
from ui.drawer_dialog import ClosingSlipDialog
from ui.slip_view import SlipPreview
from ui.widgets import button, info, page_header, page_layout, run_action, warn


class DrawerView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.snap = None
        self.previous = None
        layout = page_layout(self)
        layout.addWidget(
            page_header(
                "Till",
                "Cash Drawer",
                "Set the opening cash, count the till, then end the register.",
            )
        )
        row = QHBoxLayout()
        row.setSpacing(18)

        form = QFrame()
        form.setObjectName("card")
        form.setFixedWidth(460)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(8)

        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd MMM yyyy")
        today = date.today()
        self.day.setDate(QDate(today.year, today.month, today.day))
        self.day.dateChanged.connect(lambda _value: self.refresh())
        self.yesterday = QLabel("")
        self.yesterday.setWordWrap(True)
        self.use_yesterday = button("Use yesterday's cash", "gold")
        self.use_yesterday.clicked.connect(self._use_yesterday)
        self.opening = QDoubleSpinBox()
        self.opening.setRange(0, 5_000_000)
        self.opening.setDecimals(0)
        self.opening.setPrefix("Rs. ")
        self.opening.setGroupSeparatorShown(True)
        self.opening.setMinimumHeight(36)
        save_open = button("Save opening balance", "primary")
        save_open.clicked.connect(self._save_opening)
        self.actual = QDoubleSpinBox()
        self.actual.setRange(0, 5_000_000)
        self.actual.setDecimals(0)
        self.actual.setPrefix("Rs. ")
        self.actual.setGroupSeparatorShown(True)
        self.actual.setMinimumHeight(36)
        self.note = QTextEdit()
        self.note.setFixedHeight(64)
        self.note.setPlaceholderText("Note for this close, optional")
        self.expected_value = QLabel("")
        self.cash_out_value = QLabel("")
        self.online_value = QLabel("")
        self.status_value = QLabel("")
        self.status_value.setWordWrap(True)
        close_day = button("End register", "gold")
        reprint = button("Print slip", "primary")
        pdf = button("Save PDF", "ghost")
        close_day.clicked.connect(self._close_day)
        reprint.clicked.connect(self._print)
        pdf.clicked.connect(self._pdf)

        for caption, widget in (
            ("Business day", self.day),
            ("Opening balance", self.opening),
        ):
            label = QLabel(caption)
            label.setObjectName("fieldLabel")
            form_layout.addWidget(label)
            form_layout.addWidget(widget)
        form_layout.addWidget(self.yesterday)
        open_actions = QHBoxLayout()
        open_actions.setSpacing(8)
        open_actions.addWidget(self.use_yesterday, 1)
        open_actions.addWidget(save_open, 1)
        form_layout.addLayout(open_actions)
        counted = QLabel("Actual cash counted")
        counted.setObjectName("fieldLabel")
        form_layout.addWidget(counted)
        form_layout.addWidget(self.actual)
        note_label = QLabel("Note")
        note_label.setObjectName("fieldLabel")
        form_layout.addWidget(note_label)
        form_layout.addWidget(self.note)
        for caption, value in (
            ("Expected now", self.expected_value),
            ("Cash out", self.cash_out_value),
            ("Online, not in drawer", self.online_value),
        ):
            form_layout.addLayout(self._money_row(caption, value))
        form_layout.addWidget(self.status_value)
        form_layout.addWidget(close_day)
        slip_actions = QHBoxLayout()
        slip_actions.setSpacing(8)
        slip_actions.addWidget(reprint, 1)
        slip_actions.addWidget(pdf, 1)
        form_layout.addLayout(slip_actions)

        self.preview = SlipPreview()
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.preview)
        preview_card = QFrame()
        preview_card.setObjectName("card")
        preview_card.setFixedWidth(460)
        preview_card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel("DAY-END SLIP")
        title.setObjectName("eyebrow")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        preview_layout.addWidget(title)
        preview_layout.addWidget(scroll, 1)

        row.addWidget(form, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(preview_card, 0)
        row.addStretch(1)
        layout.addLayout(row, 1)

    def _money_row(self, caption: str, value: QLabel):
        line = QHBoxLayout()
        line.setSpacing(12)
        label = QLabel(caption)
        label.setObjectName("fieldLabel")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setMinimumWidth(120)
        line.addWidget(label)
        line.addStretch(1)
        line.addWidget(value)
        return line

    def _iso(self) -> str:
        value = self.day.date()
        return f"{value.year():04d}-{value.month():02d}-{value.day():02d}"

    def refresh(self) -> None:
        day = self._iso()
        self.snap = self.host.db.drawer_snapshot(day)
        self.previous = self.host.db.previous_drawer(day)
        self.opening.blockSignals(True)
        if self.snap["opened"]:
            self.opening.setValue(int(round(self.snap["opening"])))
        else:
            self.opening.setValue(int(round(self.previous["amount"])))
        self.opening.blockSignals(False)
        if self.snap["actual"] is not None:
            self.actual.setValue(int(round(self.snap["actual"])))
        self.opening.setEnabled(not self.snap["closed"])
        self.actual.setEnabled(not self.snap["closed"])
        previous = self.previous
        if previous["closed"] and previous["counted"] is not None:
            state = "closed"
            shown = money(previous["counted"])
        elif previous["amount"] < 0:
            state = "not closed, cash was short"
            shown = money(previous["expected"])
        else:
            state = "not closed"
            shown = money(previous["expected"])
        self.yesterday.setText(f"Yesterday {format_date(previous['date'])}  ·  {shown}  ·  {state}")
        self.use_yesterday.setEnabled(not self.snap["closed"] and previous["amount"] >= 0)
        self._show_result()
        self._paint_slip()

    def _show_result(self) -> None:
        snap = self.snap
        if snap["variance"] == "match":
            text = f"Matched. Expected {money(snap['expected'])} equals the counted cash."
            color = "#1E7A45"
        elif snap["variance"] == "short":
            text = f"Short by {money(abs(snap['difference']))}. Expected {money(snap['expected'])}, counted {money(snap['actual'])}."
            color = "#A33B32"
        elif snap["variance"] == "over":
            text = f"Over by {money(snap['difference'])}. Expected {money(snap['expected'])}, counted {money(snap['actual'])}."
            color = "#8C6A2F"
        else:
            text = ""
            color = ""
        online = float(snap.get("daily_other_expenses") or 0) + float(snap.get("monthly_other_expenses") or 0)
        self.expected_value.setText(money(snap["expected"]))
        self.cash_out_value.setText(money(snap["cash_payments"]))
        self.online_value.setText(money(online))
        if not snap["opened"]:
            text = "Save the opening balance to start the register."
        self.status_value.setText(text)
        self.status_value.setVisible(bool(text))
        self.status_value.setStyleSheet(f"color: {color};" if color else "")

    def _use_yesterday(self) -> None:
        if self.snap and self.snap["closed"]:
            warn(self, "This day is already closed.")
            return
        self.opening.setValue(int(round(self.previous["amount"])))

    def _save_opening(self) -> None:
        saved = run_action(
            self,
            lambda: self.host.db.set_opening_balance(self._iso(), self.opening.value(), self.host.user.get("username") or ""),
        )
        if saved:
            self.refresh()

    def _paint_slip(self) -> None:
        if not self.snap:
            return
        settings = self.host.db.get_settings()
        logo = thermal_logo_path() if os.path.exists(thermal_logo_path()) else ""
        self.preview.set_slip(build_closing_slip(self.snap, settings), str(settings.get("paper") or "80"), logo)

    def _close_day(self) -> None:
        if self.snap and self.snap["closed"]:
            self._show_slip("This register is already closed. Printing the saved slip.")
            return
        if not self.snap["opened"]:
            warn(self, "Save the opening balance first.")
            return
        saved = run_action(
            self,
            lambda: self.host.db.close_drawer(
                self._iso(),
                self.actual.value(),
                self.host.user.get("username") or "",
                self.note.toPlainText(),
            ),
        )
        if saved:
            self.snap = saved
            self.refresh()
            self._show_slip(self._close_message(saved), auto_print=True)

    def _close_message(self, snap: dict) -> str:
        if snap["variance"] == "match":
            return "Register closed. The drawer matches. The slip is printing."
        if snap["variance"] == "short":
            return f"Register closed. Short by {money(abs(snap['difference']))}. The slip is printing."
        return f"Register closed. Over by {money(snap['difference'])}. The slip is printing."

    def _show_slip(self, message: str, auto_print: bool = False) -> None:
        settings = self.host.db.get_settings()
        if auto_print:
            ok, printed = self.host.printers.print_lines(build_closing_slip(self.snap, settings), settings)
            if not ok:
                message = "Register closed. Printer was not available, so the slip is on screen.\n" + printed
            else:
                message = message + "\n" + printed
        ClosingSlipDialog(self.snap, settings, self, message).exec()

    def _print(self) -> None:
        if self.snap:
            self._show_slip("Day-end slip.", auto_print=True)

    def _pdf(self) -> None:
        if not self.snap:
            return
        path = choose_save_path(self, "Day-end slip", f"closing-{self.snap['date']}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.host.printers.export_pdf(build_closing_slip(self.snap, self.host.db.get_settings()), self.host.db.get_settings(), path)
            info(self, "Day-end slip saved.")
        except Exception as exc:
            warn(self, f"Could not save the slip.\n{exc}")
