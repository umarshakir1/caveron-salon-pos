"""Branding, Black Copper printer, roles, and backups."""

from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.paths import user_path
from core.utils import ROLE_ADMIN, ROLE_CASHIER, ROLE_LABELS
from database.seed_data import DEFAULT_SETTINGS
from services.printer_service import PrinterService, build_receipt, sample_invoice
from ui.branding import logo_path, refresh_thermal, replace_logo, restore_monogram, thermal_logo_path
from ui.dialogs import PhraseDialog, ReceiptDialog
from ui.slip_view import SlipPreview
from ui.widgets import button, confirm, fill_table, info, page_header, page_layout, run_action, style_table, vscroll, warn


class SettingsView(QWidget):
    def __init__(self, host):
        super().__init__()
        self.host = host
        self.printer = PrinterService()
        layout = page_layout(self)
        layout.addWidget(page_header("Atelier", "Settings", "Brand, Black Copper printer, access, and backups."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._brand_tab(), "Branding & Logo")
        self.tabs.addTab(self._printer_tab(), "Thermal Printer")
        self.tabs.addTab(self._security_tab(), "Roles & Security")
        self.tabs.addTab(self._backup_tab(), "Backup & Reset")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        settings = self.host.db.get_settings()
        self._load_brand(settings)
        self._load_printer(settings)
        self._load_users()
        self._rebuild_preview()

    def _brand_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        form = QFormLayout()
        self.salon_name = QLineEdit()
        self.tagline = QLineEdit()
        self.subtitle = QLineEdit()
        self.est_year = QLineEdit()
        self.hours = QLineEdit()
        self.address = QTextEdit()
        self.address.setFixedHeight(70)
        self.phone = QLineEdit()
        self.ntn = QLineEdit()
        self.service_charge = QSpinBox()
        self.service_charge.setRange(0, 30)
        self.service_charge.setSuffix(" %")
        form.addRow("Salon name", self.salon_name)
        form.addRow("Tagline", self.tagline)
        form.addRow("Subtitle", self.subtitle)
        form.addRow("Established", self.est_year)
        form.addRow("Hours", self.hours)
        form.addRow("Address", self.address)
        form.addRow("Phone", self.phone)
        form.addRow("NTN / STRN", self.ntn)
        form.addRow("Default service charge", self.service_charge)
        save = button("Save branding", "primary")
        save.clicked.connect(self._save_brand)
        form.addRow("", save)
        layout.addLayout(form, 2)
        side = QVBoxLayout()
        self.logo_preview = QLabel()
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setMinimumSize(180, 180)
        self.thermal_preview = QLabel("Thermal logo")
        self.thermal_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thermal_preview.setMinimumSize(180, 120)
        upload = button("Upload logo", "gold")
        restore = button("Restore monogram", "ghost")
        upload.clicked.connect(self._upload_logo)
        restore.clicked.connect(self._restore_logo)
        side.addWidget(QLabel("App header"))
        side.addWidget(self.logo_preview)
        side.addWidget(QLabel("1-bit thermal version"))
        side.addWidget(self.thermal_preview)
        side.addWidget(upload)
        side.addWidget(restore)
        side.addStretch()
        layout.addLayout(side, 1)
        return page

    def _group_radios(self, *radios: QRadioButton) -> None:
        group = QButtonGroup(self)
        group.setExclusive(True)
        for radio in radios:
            radio.setAutoExclusive(False)
            group.addButton(radio)

    def _printer_tab(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        controls = QWidget()
        form = QVBoxLayout(controls)
        self.target_windows = QRadioButton("Windows printer")
        self.target_network = QRadioButton("Network IP")
        self.target_usb = QRadioButton("USB VID / PID")
        self.target_windows.setChecked(True)
        self.printer_name = QComboBox()
        refresh = button("Refresh printers", "ghost", tiny=True)
        refresh.clicked.connect(self._fill_printers)
        self.network_ip = QLineEdit()
        self.network_ip.setPlaceholderText("192.168.1.100")
        self.network_port = QSpinBox()
        self.network_port.setRange(1, 65535)
        self.network_port.setValue(9100)
        self.usb_vid = QLineEdit()
        self.usb_vid.setPlaceholderText("VID 0x0416")
        self.usb_pid = QLineEdit()
        self.usb_pid.setPlaceholderText("PID 0x5011")
        paper = QHBoxLayout()
        self.paper_80 = QRadioButton("80mm (48 chars)")
        self.paper_58 = QRadioButton("58mm (32 chars)")
        self.paper_80.setChecked(True)
        paper.addWidget(self.paper_80)
        paper.addWidget(self.paper_58)
        mode = QHBoxLayout()
        self.mode_raw = QRadioButton("Windows Spooler Raw ESC/POS")
        self.mode_graphic = QRadioButton("Windows Graphic Print")
        self.mode_raw.setChecked(True)
        mode.addWidget(self.mode_raw)
        mode.addWidget(self.mode_graphic)
        self._group_radios(self.target_windows, self.target_network, self.target_usb)
        self._group_radios(self.paper_80, self.paper_58)
        self._group_radios(self.mode_raw, self.mode_graphic)
        self.opt_logo = QCheckBox("Print Caveron logo on top of slip")
        self.opt_address = QCheckBox("Print salon address and timing")
        self.opt_stylist = QCheckBox("Show stylist name per service")
        self.opt_customer = QCheckBox("Show customer name and phone")
        self.opt_barcode = QCheckBox("Print barcode / invoice ID at bottom")
        self.opt_cut = QCheckBox("Auto-cut paper after print")
        self.opt_drawer = QCheckBox("Open cash drawer on cash payment")
        self.header_note = QLineEdit()
        self.header_note.setPlaceholderText("Receipt header note")
        self.footer_note = QTextEdit()
        self.footer_note.setFixedHeight(60)
        for widget in (
            self.target_windows,
            self.target_network,
            self.target_usb,
            self.printer_name,
            self.network_ip,
            self.network_port,
            self.usb_vid,
            self.usb_pid,
            self.paper_80,
            self.paper_58,
            self.mode_raw,
            self.mode_graphic,
            self.opt_logo,
            self.opt_address,
            self.opt_stylist,
            self.opt_customer,
            self.opt_barcode,
            self.opt_cut,
            self.opt_drawer,
            self.header_note,
            self.footer_note,
        ):
            signal = None
            if isinstance(widget, QComboBox):
                signal = widget.currentIndexChanged
            elif isinstance(widget, (QCheckBox, QRadioButton)):
                signal = widget.toggled
            elif isinstance(widget, QTextEdit):
                signal = widget.textChanged
            elif isinstance(widget, QLineEdit):
                signal = widget.textChanged
            elif isinstance(widget, QSpinBox):
                signal = widget.valueChanged
            if signal:
                signal.connect(lambda *_args: self._rebuild_preview())
        save = button("Save printer settings", "primary")
        test = button("Print test slip", "gold")
        save.clicked.connect(self._save_printer)
        test.clicked.connect(self._test_print)
        form.addWidget(self.target_windows)
        form.addWidget(self.printer_name)
        form.addWidget(refresh)
        form.addWidget(self.target_network)
        net = QHBoxLayout()
        net.addWidget(self.network_ip)
        net.addWidget(self.network_port)
        form.addLayout(net)
        form.addWidget(self.target_usb)
        usb = QHBoxLayout()
        usb.addWidget(self.usb_vid)
        usb.addWidget(self.usb_pid)
        form.addLayout(usb)
        form.addLayout(paper)
        form.addLayout(mode)
        for widget in (self.opt_logo, self.opt_address, self.opt_stylist, self.opt_customer, self.opt_barcode, self.opt_cut, self.opt_drawer):
            form.addWidget(widget)
        form.addWidget(self.header_note)
        form.addWidget(self.footer_note)
        buttons = QHBoxLayout()
        buttons.addWidget(save)
        buttons.addWidget(test)
        form.addLayout(buttons)
        form.addStretch()
        row.addWidget(controls, 1)
        self.preview = SlipPreview()
        scroll = QScrollArea()
        scroll.setWidget(self.preview)
        scroll.setWidgetResizable(False)
        scroll.setMinimumWidth(360)
        holder = QFrame()
        holder.setObjectName("card")
        holder_layout = QVBoxLayout(holder)
        holder_layout.addWidget(QLabel("Live receipt preview"))
        holder_layout.addWidget(scroll, 1)
        row.addWidget(holder, 1)
        return page

    def _security_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("Admin / Owner can open salary, reports, and settings. Receptionist / Cashier stays on POS, appointments, and the groom tracker.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        form = QHBoxLayout()
        self.user_name = QLineEdit()
        self.user_name.setPlaceholderText("Username")
        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Display name")
        self.user_role = QComboBox()
        self.user_role.addItem(ROLE_LABELS[ROLE_ADMIN], ROLE_ADMIN)
        self.user_role.addItem(ROLE_LABELS[ROLE_CASHIER], ROLE_CASHIER)
        self.user_password = QLineEdit()
        self.user_password.setPlaceholderText("Password or PIN")
        self.user_password.setEchoMode(QLineEdit.EchoMode.Password)
        add = button("Add user", "primary", tiny=True)
        add.clicked.connect(self._add_user)
        for widget in (self.user_name, self.display_name, self.user_role, self.user_password, add):
            form.addWidget(widget)
        layout.addLayout(form)
        self.user_table = QTableWidget()
        style_table(self.user_table)
        layout.addWidget(self.user_table)
        actions = QHBoxLayout()
        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("New password for selected user")
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        reset = button("Set password", "gold", tiny=True)
        deactivate = button("Deactivate / Activate", "danger", tiny=True)
        reset.clicked.connect(self._reset_password)
        deactivate.clicked.connect(self._toggle_user)
        actions.addWidget(self.new_password, 1)
        actions.addWidget(reset)
        actions.addWidget(deactivate)
        layout.addLayout(actions)
        self.users = []
        return page

    def _backup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        text = QLabel(
            "The salon file is caveron_salon.db in the application folder. "
            "A copy is written to backups/ the first time the app opens each day. "
            "Backup before you reset."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        backup = button("Export backup", "primary")
        restore = button("Restore backup", "gold")
        reset = button("Reset to the original menu", "danger")
        backup.clicked.connect(self._backup)
        restore.clicked.connect(self._restore)
        reset.clicked.connect(self._reset)
        for widget in (backup, restore, reset):
            widget.setMinimumWidth(280)
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        layout.addWidget(QLabel("CAVERON Desktop 1.0.0  ·  Offline  ·  SQLite"))
        return page

    def _load_brand(self, settings: dict) -> None:
        self.salon_name.setText(settings.get("salon_name") or "")
        self.tagline.setText(settings.get("tagline") or "")
        self.subtitle.setText(settings.get("subtitle") or "")
        self.est_year.setText(settings.get("est_year") or "")
        self.hours.setText(settings.get("hours") or "")
        self.address.setPlainText(settings.get("address") or "")
        self.phone.setText(settings.get("phone") or "")
        self.ntn.setText(settings.get("ntn") or "")
        self.service_charge.setValue(int(settings.get("service_charge_pct") or 0))
        self._show_logos()

    def _show_logos(self) -> None:
        color = QPixmap(logo_path())
        if not color.isNull():
            self.logo_preview.setPixmap(color.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        thermal = QPixmap(thermal_logo_path())
        if not thermal.isNull():
            self.thermal_preview.setPixmap(thermal.scaled(220, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _save_brand(self) -> None:
        self.host.db.save_settings(
            {
                "salon_name": self.salon_name.text().strip() or "CAVERON",
                "tagline": self.tagline.text().strip(),
                "subtitle": self.subtitle.text().strip(),
                "est_year": self.est_year.text().strip(),
                "hours": self.hours.text().strip(),
                "address": self.address.toPlainText().strip(),
                "phone": self.phone.text().strip(),
                "ntn": self.ntn.text().strip(),
                "service_charge_pct": self.service_charge.value(),
            }
        )
        self.host.refresh_brand()
        self._rebuild_preview()
        info(self, "Branding saved.")

    def _upload_logo(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Caveron logo", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        try:
            replace_logo(path)
        except Exception as exc:
            warn(self, str(exc))
            return
        self._show_logos()
        self.host.refresh_brand()
        self._rebuild_preview()

    def _restore_logo(self) -> None:
        restore_monogram()
        self._show_logos()
        self.host.refresh_brand()
        self._rebuild_preview()

    def _fill_printers(self) -> None:
        current = self.printer_name.currentText()
        self.printer_name.blockSignals(True)
        self.printer_name.clear()
        self.printer_name.addItem("", "")
        for name in self.printer.list_printers():
            self.printer_name.addItem(name, name)
        index = self.printer_name.findText(current)
        if index >= 0:
            self.printer_name.setCurrentIndex(index)
        self.printer_name.blockSignals(False)

    def _load_printer(self, settings: dict) -> None:
        self._fill_printers()
        index = self.printer_name.findText(settings.get("printer_name") or "")
        if index >= 0:
            self.printer_name.setCurrentIndex(index)
        target = settings.get("output_target") or "windows"
        self.target_windows.setChecked(target == "windows")
        self.target_network.setChecked(target == "network")
        self.target_usb.setChecked(target == "usb")
        self.network_ip.setText(settings.get("network_ip") or "")
        self.network_port.setValue(int(settings.get("network_port") or 9100))
        self.usb_vid.setText(settings.get("usb_vid") or "")
        self.usb_pid.setText(settings.get("usb_pid") or "")
        paper = str(settings.get("paper") or "80")
        self.paper_80.setChecked(paper == "80")
        self.paper_58.setChecked(paper == "58")
        self.mode_raw.setChecked(settings.get("print_mode") != "graphic")
        self.mode_graphic.setChecked(settings.get("print_mode") == "graphic")
        self.opt_logo.setChecked(bool(settings.get("opt_logo", True)))
        self.opt_address.setChecked(bool(settings.get("opt_address", True)))
        self.opt_stylist.setChecked(bool(settings.get("opt_stylist", True)))
        self.opt_customer.setChecked(bool(settings.get("opt_customer", True)))
        self.opt_barcode.setChecked(bool(settings.get("opt_barcode", True)))
        self.opt_cut.setChecked(bool(settings.get("opt_cut", True)))
        self.opt_drawer.setChecked(bool(settings.get("opt_drawer", False)))
        self.header_note.setText(settings.get("header_note") or "")
        self.footer_note.setPlainText(settings.get("footer_note") or DEFAULT_SETTINGS["footer_note"])

    def _collect_printer(self) -> dict:
        if self.target_network.isChecked():
            target = "network"
        elif self.target_usb.isChecked():
            target = "usb"
        else:
            target = "windows"
        return {
            "output_target": target,
            "printer_name": self.printer_name.currentText(),
            "network_ip": self.network_ip.text().strip(),
            "network_port": self.network_port.value(),
            "usb_vid": self.usb_vid.text().strip(),
            "usb_pid": self.usb_pid.text().strip(),
            "paper": "58" if self.paper_58.isChecked() else "80",
            "print_mode": "graphic" if self.mode_graphic.isChecked() else "raw",
            "opt_logo": self.opt_logo.isChecked(),
            "opt_address": self.opt_address.isChecked(),
            "opt_stylist": self.opt_stylist.isChecked(),
            "opt_customer": self.opt_customer.isChecked(),
            "opt_barcode": self.opt_barcode.isChecked(),
            "opt_cut": self.opt_cut.isChecked(),
            "opt_drawer": self.opt_drawer.isChecked(),
            "header_note": self.header_note.text().strip(),
            "footer_note": self.footer_note.toPlainText().strip(),
        }

    def _merged_settings(self) -> dict:
        settings = self.host.db.get_settings()
        settings.update(
            {
                "salon_name": self.salon_name.text().strip() or settings.get("salon_name"),
                "tagline": self.tagline.text().strip(),
                "subtitle": self.subtitle.text().strip(),
                "est_year": self.est_year.text().strip(),
                "hours": self.hours.text().strip(),
                "address": self.address.toPlainText().strip(),
                "phone": self.phone.text().strip(),
                "ntn": self.ntn.text().strip(),
            }
        )
        settings.update(self._collect_printer())
        return settings

    def _rebuild_preview(self) -> None:
        if not hasattr(self, "preview"):
            return
        try:
            settings = self._merged_settings()
            logo = thermal_logo_path() if settings.get("opt_logo") and os.path.exists(thermal_logo_path()) else ""
            self.preview.set_slip(build_receipt(sample_invoice(), settings), settings.get("paper") or "80", logo)
        except Exception:
            return

    def _save_printer(self) -> None:
        self.host.db.save_settings(self._collect_printer())
        self.host.refresh_brand()
        info(self, "Printer settings saved. Test slip uses the choices on this screen.")

    def _test_print(self) -> None:
        settings = self._merged_settings()
        invoice = sample_invoice()
        ok, message = self.printer.print_invoice(invoice, settings)
        text = message if ok else "The printer did not print. The preview on the right is the slip.\n" + message
        if not ok:
            ReceiptDialog(invoice, settings, self, text).exec()
        else:
            info(self, text)

    def _load_users(self) -> None:
        self.users = self.host.db.list_users()
        fill_table(
            self.user_table,
            ["Username", "Name", "Role", "Status"],
            [
                [row["username"], row["display_name"], ROLE_LABELS.get(row["role"], row["role"]), "Active" if row["active"] else "Inactive"]
                for row in self.users
            ],
        )

    def _add_user(self) -> None:
        saved = run_action(
            self,
            lambda: self.host.db.save_user(
                {
                    "username": self.user_name.text(),
                    "display_name": self.display_name.text(),
                    "role": self.user_role.currentData(),
                    "password": self.user_password.text(),
                }
            ),
        )
        if saved:
            self.user_name.clear()
            self.display_name.clear()
            self.user_password.clear()
            self._load_users()

    def _selected_user(self):
        index = self.user_table.currentRow()
        if index < 0 or index >= len(self.users):
            warn(self, "Select a user.")
            return None
        return self.users[index]

    def _reset_password(self) -> None:
        user = self._selected_user()
        if not user:
            return
        if run_action(self, lambda: self.host.db.set_password(user["id"], self.new_password.text()) or True):
            self.new_password.clear()
            info(self, "Password updated.")

    def _toggle_user(self) -> None:
        user = self._selected_user()
        if not user:
            return
        if run_action(self, lambda: self.host.db.set_user_active(user["id"], not user["active"], self.host.user["id"]) or True):
            self._load_users()

    def _backup(self) -> None:
        suggested = user_path("backups", f"caveron_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db")
        path, _filter = QFileDialog.getSaveFileName(self, "Export backup", suggested, "SQLite (*.db)")
        if not path:
            return
        try:
            self.host.db.backup_to(path)
            info(self, "Backup saved.")
        except Exception as exc:
            warn(self, f"Backup failed.\n{exc}")

    def _restore(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Restore backup", user_path("backups"), "SQLite (*.db)")
        if not path:
            return
        if not confirm(self, "Replace the current salon data with this backup?"):
            return
        try:
            self.host.db.restore_from(path)
        except Exception as exc:
            warn(self, str(exc))
            return
        info(self, "Backup restored.")
        self.host.refresh_brand()
        self.refresh()

    def _reset(self) -> None:
        dialog = PhraseDialog(
            "This deletes bills, clients, attendance, and stock, then loads the original CAVERON menu. Type RESET to continue.",
            "RESET",
            self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.host.db.factory_reset()
        except Exception as exc:
            warn(self, f"Reset failed.\n{exc}")
            return
        info(self, "The salon file was reset. Sign in again with admin / caveron1987.")
        self.host.logout()
