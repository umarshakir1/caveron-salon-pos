"""Opening balance prompt and the printed day-end slip."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout

from core.utils import format_date, money, today_str
from services.printer_service import PrinterService, build_closing_slip
from services.report_service import choose_save_path
from ui.branding import thermal_logo_path, window_icon
from ui.slip_view import SlipPreview
from ui.widgets import button, info, run_action, warn


class OpeningBalanceDialog(QDialog):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        self.setWindowTitle("Opening drawer balance")
        self.setWindowIcon(window_icon())
        self.setModal(True)
        self.setMinimumWidth(460)
        previous = db.previous_drawer(today_str())
        carried = float(previous["amount"] or 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        title = QLabel("Opening drawer balance")
        title.setObjectName("eyebrow")
        heading = QLabel("How much cash is in the drawer?")
        heading.setWordWrap(True)
        if previous["closed"] and previous["counted"] is not None:
            detail = f"Yesterday {format_date(previous['date'])} was closed with {money(previous['counted'])} counted."
        elif carried < 0:
            detail = (
                f"Yesterday {format_date(previous['date'])} expected {money(previous['expected'])} "
                "because cash left the drawer. Enter the cash you actually counted."
            )
        else:
            detail = f"Yesterday {format_date(previous['date'])}: expected {money(previous['expected'])}."
        note = QLabel(detail)
        note.setWordWrap(True)
        note.setObjectName("muted")
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 5_000_000)
        self.amount.setDecimals(0)
        self.amount.setPrefix("Rs. ")
        self.amount.setMinimumHeight(44)
        self.amount.setValue(max(0, int(round(carried))))
        start = button("Start register", "gold")
        later = button("Not now", "ghost")
        start.clicked.connect(self._save)
        later.clicked.connect(self.reject)
        layout.addWidget(title)
        layout.addWidget(heading)
        layout.addWidget(note)
        layout.addWidget(self.amount)
        row = QHBoxLayout()
        row.addWidget(later)
        row.addWidget(start)
        layout.addLayout(row)

    def _save(self) -> None:
        saved = run_action(
            self,
            lambda: self.db.set_opening_balance(today_str(), self.amount.value(), self.user.get("username") or ""),
        )
        if saved:
            self.accept()


class ClosingSlipDialog(QDialog):
    def __init__(self, snap: dict, settings: dict, parent=None, message: str = ""):
        super().__init__(parent)
        self.snap = snap
        self.settings = settings
        self.printer = PrinterService()
        self.setWindowTitle("Day-end slip")
        self.setWindowIcon(window_icon())
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.message = QLabel(message)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.preview = SlipPreview()
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.preview)
        scroll.setMinimumHeight(420)
        layout.addWidget(scroll, 1)
        actions = QHBoxLayout()
        reprint = button("Print again", "primary")
        pdf = button("Save PDF", "ghost")
        close = button("Done", "ghost")
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
        return build_closing_slip(self.snap, self.settings)

    def _refresh(self) -> None:
        logo = thermal_logo_path() if os.path.exists(thermal_logo_path()) else ""
        self.preview.set_slip(self._lines(), str(self.settings.get("paper") or "80"), logo)

    def _print(self) -> None:
        ok, message = self.printer.print_lines(self._lines(), self.settings)
        self.message.setText(message if ok else "Printer was not available. The slip is still on screen.\n" + message)

    def _pdf(self) -> None:
        path = choose_save_path(self, "Day-end slip", f"closing-{self.snap.get('date', 'slip')}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.printer.export_pdf(self._lines(), self.settings, path)
            info(self, "Day-end slip saved.")
        except Exception as exc:
            warn(self, f"Could not save the slip.\n{exc}")
