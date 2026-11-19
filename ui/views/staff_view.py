"""Staff profiles and pay setup."""

from __future__ import annotations

import os
import shutil

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.paths import user_path
from core.utils import SALARY_TYPES, STAFF_ROLES
from ui.widgets import button, page_header, page_layout, run_action, style_table, warn


class StaffView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.staff_id = None
        self.pending_photo = ""
        self.photo_path = ""
        layout = page_layout(self)
        layout.addWidget(page_header("Team", "Staff", "Profiles, roles, and commission."))
        body = QHBoxLayout()
        body.setSpacing(16)
        self.table = QTableWidget()
        style_table(self.table)
        self.table.itemSelectionChanged.connect(self._load_selected)
        body.addWidget(self.table, 3)

        form_host = QFrame()
        form_host.setObjectName("card")
        form_host.setMinimumWidth(360)
        form_host.setMaximumWidth(440)
        form_layout = QVBoxLayout(form_host)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(10)
        self.photo = QLabel("No photo")
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setFixedSize(96, 96)
        self.photo.setStyleSheet("border: 1px solid #2A2A32; border-radius: 48px;")
        upload = button("Upload photo", "ghost", tiny=True)
        upload.clicked.connect(self._pick_photo)
        self.name = QLineEdit()
        self.role = QComboBox()
        self.role.addItems(STAFF_ROLES)
        self.phone = QLineEdit()
        self.cnic = QLineEdit()
        self.cnic.setPlaceholderText("12345-1234567-1")
        self.joining = QDateEdit()
        self.joining.setCalendarPopup(True)
        self.joining.setDisplayFormat("dd MMM yyyy")
        self.joining.setDate(QDate.currentDate())
        self.salary_type = QComboBox()
        self.salary_type.addItems(SALARY_TYPES)
        self.base = QDoubleSpinBox()
        self.base.setRange(0, 5_000_000)
        self.base.setDecimals(0)
        self.base.setPrefix("Rs. ")
        self.commission = QDoubleSpinBox()
        self.commission.setRange(0, 100)
        self.commission.setSuffix(" %")
        self.active = QCheckBox("Active")
        self.active.setChecked(True)
        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Role", self.role)
        form.addRow("Phone", self.phone)
        form.addRow("CNIC", self.cnic)
        form.addRow("Joining", self.joining)
        form.addRow("Salary type", self.salary_type)
        form.addRow("Base salary", self.base)
        form.addRow("Commission", self.commission)
        form.addRow("", self.active)
        actions = QHBoxLayout()
        new = button("New", "ghost", tiny=True)
        save = button("Save profile", "primary", tiny=True)
        toggle = button("Activate / Deactivate", "gold", tiny=True)
        new.clicked.connect(self._blank)
        save.clicked.connect(self._save)
        toggle.clicked.connect(self._toggle)
        actions.addWidget(new)
        actions.addWidget(save)
        actions.addWidget(toggle)
        form_layout.addWidget(self.photo, alignment=Qt.AlignmentFlag.AlignLeft)
        form_layout.addWidget(upload, alignment=Qt.AlignmentFlag.AlignLeft)
        form_layout.addLayout(form)
        form_layout.addLayout(actions)
        form_layout.addStretch()
        body.addWidget(form_host, 0)
        layout.addLayout(body, 1)

    def refresh(self) -> None:
        rows = self.host.db.list_staff()
        self.rows = rows
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Role", "Salary", "Commission", "Status"])
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row["name"],
                row["role"],
                row["salary_type"],
                f"{row['commission_pct']:g}%",
                "Active" if row["active"] else "Inactive",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(index, column, item)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        status = self.table.horizontalHeaderItem(4)
        if status:
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _blank(self) -> None:
        self.staff_id = None
        self.pending_photo = ""
        self.photo_path = ""
        self.name.clear()
        self.phone.clear()
        self.cnic.clear()
        self.base.setValue(0)
        self.commission.setValue(0)
        self.active.setChecked(True)
        self.joining.setDate(QDate.currentDate())
        self.photo.setPixmap(QPixmap())
        self.photo.setText("No photo")

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        staff = self.host.db.get_staff(item.data(Qt.ItemDataRole.UserRole))
        if not staff:
            return
        self.staff_id = staff["id"]
        self.pending_photo = ""
        self.photo_path = staff.get("photo_path") or ""
        self.name.setText(staff["name"])
        self.role.setCurrentText(staff["role"])
        self.phone.setText(staff.get("phone") or "")
        self.cnic.setText(staff.get("cnic") or "")
        self.salary_type.setCurrentText(staff["salary_type"])
        self.base.setValue(float(staff["base_salary"] or 0))
        self.commission.setValue(float(staff["commission_pct"] or 0))
        self.active.setChecked(bool(staff["active"]))
        if staff.get("joining_date"):
            year, month, day = [int(part) for part in staff["joining_date"][:10].split("-")]
            self.joining.setDate(QDate(year, month, day))
        self._show_photo(self.photo_path)

    def _pick_photo(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Staff photo", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        self.pending_photo = path
        self._show_photo(path)

    def _show_photo(self, path: str) -> None:
        pixmap = QPixmap(path) if path and os.path.exists(path) else QPixmap()
        if pixmap.isNull():
            self.photo.setPixmap(QPixmap())
            self.photo.setText("No photo")
            return
        self.photo.setText("")
        self.photo.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))

    def _save(self) -> None:
        joining = self.joining.date()
        data = {
            "id": self.staff_id,
            "name": self.name.text(),
            "role": self.role.currentText(),
            "phone": self.phone.text(),
            "cnic": self.cnic.text(),
            "joining_date": f"{joining.year():04d}-{joining.month():02d}-{joining.day():02d}",
            "photo_path": self.photo_path,
            "salary_type": self.salary_type.currentText(),
            "base_salary": self.base.value(),
            "commission_pct": self.commission.value(),
            "active": self.active.isChecked(),
        }
        staff_id = run_action(self, lambda: self.host.db.save_staff(data))
        if not staff_id:
            return
        if self.pending_photo:
            extension = os.path.splitext(self.pending_photo)[1].lower() or ".png"
            if extension not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                warn(self, "Use a PNG or JPG photo.")
                return
            folder = user_path("assets", "staff")
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, f"staff_{staff_id}{extension}")
            shutil.copyfile(self.pending_photo, dest)
            data["id"] = staff_id
            data["photo_path"] = dest
            run_action(self, lambda: self.host.db.save_staff(data))
            self.photo_path = dest
            self.pending_photo = ""
        self.staff_id = staff_id
        self.refresh()

    def _toggle(self) -> None:
        if not self.staff_id:
            warn(self, "Select a staff profile first.")
            return
        self.active.setChecked(not self.active.isChecked())
        self._save()
