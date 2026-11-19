"""Shared controls for the salon desktop."""

from __future__ import annotations

import logging
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils import money, preset_range
from ui.theme import font_brand, font_ui


def button(text: str, kind: str = "primary", tiny: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName(kind)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setMinimumHeight(30 if tiny else 40)
    return widget


def field(label: str, widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    caption = QLabel(label)
    caption.setObjectName("fieldLabel")
    layout.addWidget(caption)
    layout.addWidget(widget)
    return box


def card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def page_layout(widget: QWidget) -> QVBoxLayout:
    widget.setObjectName("page")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(28, 22, 28, 22)
    layout.setSpacing(16)
    return layout


def page_header(kicker: str, title: str, subtitle: str) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    eyebrow = QLabel(kicker.upper())
    eyebrow.setObjectName("eyebrow")
    heading = QLabel(title)
    heading.setFont(font_brand(22))
    note = QLabel(subtitle)
    note.setObjectName("muted")
    note.setWordWrap(True)
    layout.addWidget(eyebrow)
    layout.addWidget(heading)
    layout.addWidget(note)
    return box


def vscroll(inner: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(inner)
    return area


def style_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setDefaultSectionSize(40)
    table.setWordWrap(False)


def fill_table(table: QTableWidget, headers: list[str], rows: list[list]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if text.startswith("Rs.") or text.endswith("%"):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row_index, column, item)
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)


def warn(parent, text: str) -> None:
    QMessageBox.warning(parent, "CAVERON", text)


def info(parent, text: str) -> None:
    QMessageBox.information(parent, "CAVERON", text)


def confirm(parent, text: str) -> bool:
    answer = QMessageBox.question(parent, "CAVERON", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    return answer == QMessageBox.StandardButton.Yes


def run_action(parent, fn):
    try:
        return fn()
    except ValueError as exc:
        warn(parent, str(exc))
    except Exception as exc:
        logging.exception("Action failed")
        warn(parent, f"Something went wrong.\n{exc}")
    return None


class KpiCard(QFrame):
    def __init__(self, kicker: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(118)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        self.kicker = QLabel(kicker.upper())
        self.kicker.setObjectName("eyebrow")
        self.kicker.setWordWrap(True)
        self.value = QLabel("Rs. 0")
        self.value.setObjectName("kpiValue")
        self.value.setFont(font_ui(16, bold=True))
        self.value.setMinimumHeight(24)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.kicker)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)
        layout.addStretch()

    def set_value(self, value: str, hint: str = "") -> None:
        self.value.setText(value)
        self.hint.setText(hint)


class ServiceCard(QFrame):
    chosen = Signal(object)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.setObjectName("serviceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(210)
        self.setFixedHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        badge = QLabel("DEAL" if payload.get("kind") == "package" else ("RANGE" if payload.get("variable") else "SERVICE"))
        badge.setObjectName("eyebrow")
        name = QLabel(payload["name"])
        name.setFont(font_ui(12, bold=True))
        name.setWordWrap(True)
        price = QLabel(payload["price_text"])
        price.setObjectName("priceGold" if payload.get("kind") == "package" else "price")
        meta = QLabel(payload.get("meta") or "")
        meta.setObjectName("muted")
        layout.addWidget(badge)
        layout.addWidget(name)
        layout.addStretch()
        layout.addWidget(price)
        layout.addWidget(meta)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.chosen.emit(self.payload)
        super().mouseReleaseEvent(event)


class DateRangeBar(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.preset = QComboBox()
        self.preset.addItem("Today", "today")
        self.preset.addItem("Yesterday", "yesterday")
        self.preset.addItem("This Week", "week")
        self.preset.addItem("This Month", "month")
        self.preset.addItem("Custom Range", "custom")
        self.start = QDateEdit()
        self.end = QDateEdit()
        for editor in (self.start, self.end):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd MMM yyyy")
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.start.dateChanged.connect(self._manual)
        self.end.dateChanged.connect(self._manual)
        layout.addWidget(self.preset)
        layout.addWidget(self.start)
        layout.addWidget(QLabel("to"))
        layout.addWidget(self.end)
        layout.addStretch()
        self._apply_preset("today", emit=False)

    def _preset_changed(self):
        key = self.preset.currentData()
        if key != "custom":
            self._apply_preset(key, emit=True)
        else:
            self.changed.emit()

    def _manual(self):
        if self.preset.currentData() != "custom":
            self.preset.blockSignals(True)
            index = self.preset.findData("custom")
            self.preset.setCurrentIndex(index)
            self.preset.blockSignals(False)
        self.changed.emit()

    def _apply_preset(self, key: str, emit: bool) -> None:
        start, end = preset_range(key)
        for editor, value in ((self.start, start), (self.end, end)):
            editor.blockSignals(True)
            editor.setDate(QDate(value.year, value.month, value.day))
            editor.blockSignals(False)
        if emit:
            self.changed.emit()

    def set_preset(self, key: str) -> None:
        index = self.preset.findData(key)
        if index >= 0:
            self.preset.setCurrentIndex(index)
        if key != "custom":
            self._apply_preset(key, emit=True)

    def range_strings(self) -> tuple[str, str]:
        start = _qdate(self.start.date())
        end = _qdate(self.end.date())
        if end < start:
            start, end = end, start
        return start.isoformat(), end.isoformat()


def _qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def metric_text(metric: dict) -> str:
    if metric.get("plain"):
        return str(int(metric["raw"]))
    return money(metric["raw"])
