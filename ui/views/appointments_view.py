"""Walk-in tokens and booked chairs."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QSizePolicy,
    QTableWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from core.utils import money, price_label
from ui.widgets import button, field, fill_table, page_header, page_layout, run_action, style_table, warn


class AppointmentsView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.rows = []
        self.editing_id = None
        layout = page_layout(self)
        layout.addWidget(page_header("Queue", "Appointments", "Walk-in tokens and booked chairs."))

        body = QHBoxLayout()
        body.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(10)
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.setFixedWidth(292)
        self.calendar.setFixedHeight(268)
        self.calendar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._style_calendar()
        self.calendar.selectionChanged.connect(self.refresh)
        self.day_label = QLabel("Today")
        self.day_label.setObjectName("muted")
        self.day_label.setWordWrap(True)
        left.addWidget(self.calendar)
        left.addWidget(self.day_label)
        left.addStretch()
        body.addLayout(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        form = QFrame()
        form.setObjectName("card")
        form_layout = QVBoxLayout(form)
        form_layout.setSpacing(10)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Walk-in name")
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("03xx")
        self.service = QComboBox()
        self.service.setMinimumWidth(220)
        self.staff = QComboBox()
        self.staff.setMinimumWidth(150)
        self.chair = QComboBox()
        self.chair.setMinimumWidth(96)
        chair_box = QWidget()
        chair_line = QHBoxLayout(chair_box)
        chair_line.setContentsMargins(0, 0, 0, 0)
        chair_line.setSpacing(6)
        chairs = button("Chairs", "ghost", tiny=True)
        chairs.clicked.connect(self._manage_chairs)
        chair_line.addWidget(self.chair, 1)
        chair_line.addWidget(chairs)
        self.time = QTimeEdit()
        self.time.setDisplayFormat("hh:mm AP")
        self.time.setTime(QTime.currentTime())
        self.time.setMinimumWidth(108)
        self.notes = QTextEdit()
        self.notes.setFixedHeight(68)
        self.notes.setPlaceholderText("Notes for the chair, optional")
        identity = QHBoxLayout()
        identity.setSpacing(10)
        identity.addWidget(field("Client", self.name), 2)
        identity.addWidget(field("Phone", self.phone), 1)
        booking = QHBoxLayout()
        booking.setSpacing(10)
        booking.addWidget(field("Service or deal", self.service), 3)
        booking.addWidget(field("Stylist", self.staff), 2)
        booking.addWidget(field("Chair", chair_box), 1)
        booking.addWidget(field("Time", self.time), 1)
        form_layout.addLayout(identity)
        form_layout.addLayout(booking)
        form_layout.addWidget(field("Notes", self.notes))
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.save_button = button("Save appointment", "primary")
        token = button("Issue walk-in token", "gold")
        clear = button("New", "ghost")
        self.save_button.clicked.connect(self._save)
        token.clicked.connect(self._token)
        clear.clicked.connect(self.prepare_new)
        actions.addWidget(self.save_button)
        actions.addWidget(token)
        actions.addWidget(clear)
        actions.addStretch()
        form_layout.addLayout(actions)
        right_layout.addWidget(form)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter this day by name, phone, or token")
        self.filter.textChanged.connect(lambda _text: self.refresh())
        right_layout.addWidget(self.filter)
        self.table = QTableWidget()
        style_table(self.table)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.cellDoubleClicked.connect(lambda *_args: self._edit_selected())
        right_layout.addWidget(self.table, 1)
        body.addWidget(right, 1)
        layout.addLayout(body, 1)

    def _style_calendar(self) -> None:
        weekend = QTextCharFormat()
        weekend.setForeground(QColor("#C9A96E"))
        self.calendar.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend)
        self.calendar.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend)

    def prepare_new(self) -> None:
        self.editing_id = None
        self.name.clear()
        self.phone.clear()
        self.notes.clear()
        self.save_button.setText("Save appointment")
        self.calendar.setSelectedDate(QDate.currentDate())
        self.time.setTime(QTime.currentTime())

    def _load_chairs(self) -> None:
        current = self.chair.currentText()
        self.chair.blockSignals(True)
        self.chair.clear()
        self.chair.addItems(self.host.db.list_chairs())
        index = self.chair.findText(current)
        self.chair.setCurrentIndex(index if index >= 0 else 0)
        self.chair.blockSignals(False)

    def _manage_chairs(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Chairs")
        dialog.setMinimumSize(380, 420)
        dialog.resize(420, 480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        note = QLabel("Add the chairs you actually have. Any stays on the booking list for walk-ins that are not seated yet.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        names = QListWidget()
        for name in self.host.db.list_chairs():
            if name != "Any":
                names.addItem(name)
        entry = QLineEdit()
        entry.setPlaceholderText("New chair, for example Chair 7")
        add_row = QHBoxLayout()
        add = button("Add", "primary", tiny=True)
        remove = button("Remove", "danger", tiny=True)

        def add_chair():
            text = entry.text().strip()
            if not text or text.lower() == "any":
                return
            for index in range(names.count()):
                if names.item(index).text().lower() == text.lower():
                    names.setCurrentRow(index)
                    entry.clear()
                    return
            names.addItem(text)
            entry.clear()

        def remove_chair():
            row = names.currentRow()
            if row >= 0:
                names.takeItem(row)

        add.clicked.connect(add_chair)
        entry.returnPressed.connect(add_chair)
        remove.clicked.connect(remove_chair)
        add_row.addWidget(entry, 1)
        add_row.addWidget(add)
        add_row.addWidget(remove)
        actions = QHBoxLayout()
        cancel = button("Cancel", "ghost")
        save = button("Save chairs", "primary")
        cancel.clicked.connect(dialog.reject)
        save.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addWidget(note)
        layout.addWidget(names, 1)
        layout.addLayout(add_row)
        layout.addLayout(actions)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        saved = [names.item(index).text().strip() for index in range(names.count())]
        self.host.db.save_chairs(saved)
        self._load_chairs()

    def refresh(self) -> None:
        self._load_chairs()
        self._load_options()
        selected = self.calendar.selectedDate()
        day = f"{selected.year():04d}-{selected.month():02d}-{selected.day():02d}"
        self.rows = self.host.db.list_appointments(day, self.filter.text().strip())
        waiting = sum(1 for row in self.rows if row["status"] == "Waiting")
        seated = sum(1 for row in self.rows if row["status"] == "In Chair")
        self.day_label.setText(f"{selected.toString('d MMMM yyyy')}\n{len(self.rows)} booked  ·  {waiting} waiting  ·  {seated} in chair")
        fill_table(
            self.table,
            ["Token", "Time", "Client", "Phone", "Service", "Stylist", "Chair", "Status", "Actions"],
            [
                [
                    row["token"] or "",
                    row["appt_time"],
                    row["customer_name"],
                    row["phone"] or "",
                    row["service_name"] or "",
                    row["staff_name"] or "",
                    row["chair"] or "",
                    row["status"],
                    "",
                ]
                for row in self.rows
            ],
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(88)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for column in (0, 1, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(8, 348)
        for index, row in enumerate(self.rows):
            self.table.setCellWidget(index, 8, self._actions(row))
            self.table.setRowHeight(index, 52)

    def _load_options(self) -> None:
        current_service = self.service.currentData()
        current_staff = self.staff.currentData()
        self.service.blockSignals(True)
        self.staff.blockSignals(True)
        self.service.clear()
        self.staff.clear()
        self.staff.addItem("Unassigned", None)
        for member in self.host.db.list_staff(active_only=True):
            self.staff.addItem(member["name"], member["id"])
        for service in self.host.db.list_services(active_only=True):
            label = f"{service['name']}  ·  {price_label(service['min_price'], service['max_price'], service['is_variable'])}"
            self.service.addItem(label, ("service", service["id"], service["name"]))
        for package in self.host.db.list_packages(active_only=True):
            self.service.addItem(f"{package['name']}  ·  {money(package['price'])}", ("package", package["id"], package["name"]))
        if current_service is not None:
            for index in range(self.service.count()):
                if self.service.itemData(index) == current_service:
                    self.service.setCurrentIndex(index)
        staff_index = self.staff.findData(current_staff)
        if staff_index >= 0:
            self.staff.setCurrentIndex(staff_index)
        self.service.blockSignals(False)
        self.staff.blockSignals(False)

    def _actions(self, row: dict) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        chair = button("In chair", "ghost", tiny=True)
        done = button("Done", "ghost", tiny=True)
        bill = button("Bill", "primary", tiny=True)
        cancel = button("Cancel", "danger", tiny=True)
        chair.clicked.connect(lambda _checked=False, rid=row["id"]: self._status(rid, "In Chair"))
        done.clicked.connect(lambda _checked=False, rid=row["id"]: self._status(rid, "Completed"))
        bill.clicked.connect(lambda _checked=False, rid=row["id"]: self.host.open_appointment_bill(rid))
        cancel.clicked.connect(lambda _checked=False, rid=row["id"]: self._status(rid, "Cancelled"))
        if row["status"] in ("Completed", "Cancelled") or row.get("invoice_id"):
            bill.setEnabled(False)
        if row["status"] == "Cancelled":
            chair.setEnabled(False)
            done.setEnabled(False)
        for widget in (chair, done, bill, cancel):
            widget.setMinimumWidth(widget.fontMetrics().horizontalAdvance(widget.text()) + 28)
            widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(widget)
        layout.addStretch()
        return host

    def _status(self, appointment_id: int, status: str) -> None:
        if run_action(self, lambda: self.host.db.set_appointment_status(appointment_id, status)) is not False:
            self.refresh()

    def _payload(self, walkin: bool) -> dict:
        picked = self.service.currentData()
        if not picked:
            raise ValueError("Choose a service or deal.")
        kind, ref_id, name = picked
        selected = self.calendar.selectedDate()
        customer = None
        if len(self.phone.text().strip()) >= 7 and self.name.text().strip():
            customer = self.host.db.upsert_customer(self.name.text(), self.phone.text())
        return {
            "id": self.editing_id,
            "customer_id": customer["id"] if customer else None,
            "customer_name": self.name.text(),
            "phone": self.phone.text(),
            "staff_id": self.staff.currentData(),
            "service_id": ref_id if kind == "service" else None,
            "package_id": ref_id if kind == "package" else None,
            "service_name": name,
            "appt_date": f"{selected.year():04d}-{selected.month():02d}-{selected.day():02d}",
            "appt_time": self.time.time().toString("HH:mm") if not walkin else datetime.now().strftime("%H:%M"),
            "chair": self.chair.currentText(),
            "notes": self.notes.toPlainText(),
            "is_walkin": walkin,
        }

    def _save(self) -> None:
        saved = run_action(self, lambda: self.host.db.save_appointment(self._payload(False)))
        if saved:
            self.prepare_new()
            self.refresh()

    def _token(self) -> None:
        self.editing_id = None
        saved = run_action(self, lambda: self.host.db.save_appointment(self._payload(True)))
        if saved:
            self.prepare_new()
            self.refresh()

    def _edit_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return
        data = self.rows[row]
        if data["status"] in ("Completed", "Cancelled"):
            warn(self, "Completed and cancelled rows stay as history.")
            return
        self.editing_id = data["id"]
        self.name.setText(data["customer_name"])
        self.phone.setText(data["phone"] or "")
        self.notes.setPlainText(data["notes"] or "")
        self.chair.setCurrentText(data["chair"] or "Any")
        hours, minutes = [int(part) for part in (data["appt_time"] or "12:00").split(":")[:2]]
        self.time.setTime(QTime(hours, minutes))
        target = ("service", data["service_id"]) if data.get("service_id") else ("package", data.get("package_id"))
        for index in range(self.service.count()):
            item = self.service.itemData(index)
            if item and item[0] == target[0] and item[1] == target[1]:
                self.service.setCurrentIndex(index)
        staff_index = self.staff.findData(data.get("staff_id"))
        if staff_index >= 0:
            self.staff.setCurrentIndex(staff_index)
        self.save_button.setText("Update appointment")
