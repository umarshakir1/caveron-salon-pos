"""Sidebar shell for the nine salon modules."""

from __future__ import annotations

import sys
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from core.utils import ROLE_LABELS, WINDOW_TITLE
from services.printer_service import PrinterService
from ui.branding import logo_path, window_icon
from ui.icons import nav_icon
from ui.theme import apply_theme, font_brand, font_ui
from ui.views.appointments_view import AppointmentsView
from ui.views.catalog_view import CatalogView
from ui.views.dashboard import DashboardView
from ui.views.drawer_view import DrawerView
from ui.views.expenses_view import ExpensesView
from ui.views.groom_view import GroomView
from ui.views.payroll_view import PayrollView
from ui.views.pos_view import PosView
from ui.views.reports_view import ReportsView
from ui.views.settings_view import SettingsView
from ui.views.staff_view import StaffView

NAV = [
    ("dashboard", "Dashboard", "dashboard", "admin"),
    ("pos", "Point of Sale", "pos", "all"),
    ("groom", "Groom Tracker", "groom", "all"),
    ("appointments", "Appointments", "appointments", "all"),
    ("catalog", "Services & Deals", "catalog", "admin"),
    ("staff", "Staff", "staff", "admin"),
    ("payroll", "Payroll", "payroll", "admin"),
    ("expenses", "Expenses & Stock", "expenses", "admin"),
    ("drawer", "Cash Drawer", "drawer", "admin"),
    ("reports", "Reports", "reports", "admin"),
    ("settings", "Settings", "settings", "admin"),
]


class MainWindow(QMainWindow):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.logged_out = False
        self._opening_prompted = False
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(window_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.printers = PrinterService()

        shell = QWidget()
        self.setCentralWidget(shell)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(248)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 18, 16, 16)
        side.setSpacing(6)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand = QLabel("CAVERON")
        self.brand.setFont(font_brand(16))
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_sub = QLabel("SALON & BARBER")
        self.brand_sub.setObjectName("eyebrow")
        self.brand_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.logo)
        side.addWidget(self.brand)
        side.addWidget(self.brand_sub)
        side.addSpacing(12)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        self.stack = QStackedWidget()
        self.views = {}
        factories = {
            "dashboard": DashboardView,
            "pos": PosView,
            "groom": GroomView,
            "appointments": AppointmentsView,
            "catalog": CatalogView,
            "staff": StaffView,
            "payroll": PayrollView,
            "expenses": ExpensesView,
            "drawer": DrawerView,
            "reports": ReportsView,
            "settings": SettingsView,
        }
        for key, label, icon, access in NAV:
            if access == "admin" and user["role"] != "admin":
                continue
            nav = QPushButton("  " + label)
            nav.setObjectName("nav")
            nav.setCheckable(True)
            nav.setCursor(Qt.CursorShape.PointingHandCursor)
            nav.setIcon(nav_icon(icon))
            nav.setIconSize(QSize(20, 20))
            nav.clicked.connect(lambda _checked=False, name=key: self.go(name))
            self.nav_group.addButton(nav)
            self.nav_buttons[key] = nav
            side.addWidget(nav)
            view = factories[key](self)
            self.views[key] = view
            self.stack.addWidget(view)
        side.addStretch()
        self.printer_label = QLabel("Printer")
        self.printer_label.setWordWrap(True)
        self.printer_label.setObjectName("muted")
        self.clock = QLabel("")
        self.clock.setFont(font_ui(10, True))
        self.hours = QLabel("")
        self.hours.setObjectName("muted")
        self.who = QLabel(f"{user['display_name']}\n{ROLE_LABELS.get(user['role'], user['role'])}")
        self.who.setObjectName("muted")
        logout = QPushButton("Sign out")
        logout.setObjectName("ghost")
        logout.setCursor(Qt.CursorShape.PointingHandCursor)
        logout.clicked.connect(self.logout)
        self.theme_button = QPushButton("Light mode")
        self.theme_button.setObjectName("ghost")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self._toggle_theme)
        side.addWidget(self.printer_label)
        side.addWidget(self.clock)
        side.addWidget(self.hours)
        side.addWidget(self.who)
        side.addWidget(self.theme_button)
        side.addWidget(logout)
        row.addWidget(self.sidebar)
        row.addWidget(self.stack, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.refresh_brand()
        self._sync_theme_button()
        self._sync_nav_icons()
        self._tick()
        first = "dashboard" if "dashboard" in self.views else "pos"
        self.go(first)

    @property
    def is_admin(self) -> bool:
        return self.user["role"] == "admin"

    def go(self, key: str) -> None:
        view = self.views.get(key)
        if view is None:
            return
        self.stack.setCurrentWidget(view)
        button = self.nav_buttons.get(key)
        if button:
            button.setChecked(True)
        if hasattr(view, "refresh"):
            view.refresh()

    def new_bill(self) -> None:
        self.go("pos")
        self.views["pos"].new_bill()

    def book_appointment(self) -> None:
        self.go("appointments")
        self.views["appointments"].prepare_new()

    def record_expense(self) -> None:
        self.go("expenses")
        self.views["expenses"].focus_expense()

    def go_drawer(self) -> None:
        self.go("drawer")

    def open_z_report(self) -> None:
        self.go("reports")
        self.views["reports"].open_preset("sales", "today")

    def open_appointment_bill(self, appointment_id: int) -> None:
        self.go("pos")
        self.views["pos"].load_appointment(appointment_id)

    def refresh_brand(self) -> None:
        settings = self.db.get_settings()
        pixmap = QPixmap(logo_path())
        if not pixmap.isNull():
            self.logo.setPixmap(pixmap.scaled(200, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.brand.setText(settings.get("salon_name") or "CAVERON")
        self.brand_sub.setText(settings.get("subtitle") or "SALON & BARBER")
        self.hours.setText(settings.get("hours") or "")
        self.setWindowIcon(window_icon())
        self._printer_status(settings)

    def _printer_status(self, settings=None) -> None:
        settings = settings or self.db.get_settings()
        target = settings.get("output_target") or "windows"
        if target == "network" and settings.get("network_ip"):
            self.printer_label.setText("Printer  ·  Network " + settings["network_ip"])
            self.printer_label.setStyleSheet("color: #2ECC71;")
            return
        if target == "usb" and settings.get("usb_vid"):
            self.printer_label.setText("Printer  ·  USB")
            self.printer_label.setStyleSheet("color: #F39C12;")
            return
        name = settings.get("printer_name") or ""
        installed = set(self.printers.list_printers())
        if name and name in installed:
            self.printer_label.setText("Printer  ·  " + name)
            self.printer_label.setStyleSheet("color: #2ECC71;")
        elif name:
            self.printer_label.setText("Printer offline  ·  " + name)
            self.printer_label.setStyleSheet("color: #F39C12;")
        else:
            self.printer_label.setText("No printer selected")
            self.printer_label.setStyleSheet("color: #8E8E9A;")

    def _tick(self) -> None:
        self.clock.setText(datetime.now().strftime("%a %d %b   %I:%M %p").replace(" 0", " "))

    def _sync_nav_icons(self) -> None:
        from PySide6.QtWidgets import QApplication

        light = QApplication.instance().property("caveronTheme") == "light"
        color = "#1C1B19" if light else "#E4E6EC"
        for key, _label, icon, _access in NAV:
            nav = self.nav_buttons.get(key)
            if nav is not None:
                nav.setIcon(nav_icon(icon, color))
                nav.setIconSize(QSize(20, 20))

    def _sync_theme_button(self) -> None:
        from PySide6.QtWidgets import QApplication

        light = QApplication.instance().property("caveronTheme") == "light"
        self.theme_button.setText("Dark mode" if light else "Light mode")

    def _toggle_theme(self) -> None:
        from PySide6.QtWidgets import QApplication

        light = QApplication.instance().property("caveronTheme") == "light"
        mode = "dark" if light else "light"
        self.db.save_settings({"theme": mode})
        apply_theme(QApplication.instance(), mode)
        self._sync_theme_button()
        self._sync_nav_icons()
        current = self.stack.currentWidget()
        if hasattr(current, "refresh"):
            current.refresh()

    def logout(self) -> None:
        self.logged_out = True
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        _dark_titlebar(self)
        if not self._opening_prompted:
            self._opening_prompted = True
            QTimer.singleShot(300, self._prompt_opening)

    def _prompt_opening(self) -> None:
        from core.utils import today_str

        from ui.drawer_dialog import OpeningBalanceDialog

        snap = self.db.drawer_snapshot(today_str())
        if snap["opened"] or snap["closed"]:
            return
        if OpeningBalanceDialog(self.db, self.user, self).exec():
            drawer = self.views.get("drawer")
            if drawer is not None and self.stack.currentWidget() is drawer:
                drawer.refresh()


def _dark_titlebar(widget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        return
