"""Owner and cashier sign-in."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ui.branding import logo_path
from ui.theme import font_brand
from ui.widgets import button, warn


class LoginDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = None
        self.setWindowTitle("CAVERON — Sign in")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(True)
        self.setMinimumSize(780, 520)
        self.resize(1100, 720)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.brand = QWidget()
        self.brand.setMinimumWidth(260)
        brand_layout = QVBoxLayout(self.brand)
        self.brand_layout = brand_layout
        brand_layout.setContentsMargins(48, 48, 48, 48)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        word = QLabel("CAVERON")
        word.setFont(font_brand(36))
        tag = QLabel("CRAFT YOUR STYLE")
        tag.setObjectName("eyebrow")
        sub = QLabel("SALON  &  BARBER")
        sub.setFont(font_brand(14))
        est = QLabel("EST. 1987")
        est.setObjectName("muted")
        hours = QLabel("Open daily  12PM – 12AM")
        hours.setObjectName("muted")
        brand_layout.addStretch()
        brand_layout.addWidget(self.logo)
        brand_layout.addWidget(word)
        brand_layout.addWidget(tag)
        brand_layout.addWidget(sub)
        brand_layout.addWidget(est)
        brand_layout.addSpacing(12)
        brand_layout.addWidget(hours)
        brand_layout.addStretch()

        form_host = QWidget()
        form_host.setMinimumWidth(340)
        self.form = QVBoxLayout(form_host)
        form = self.form
        form.setContentsMargins(64, 64, 64, 48)
        form.addStretch()
        title = QLabel("Sign in")
        title.setFont(font_brand(28))
        note = QLabel("Admin sees the full salon. Reception stays on the desk: billing, appointments, and groom packages.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setMaximumWidth(460)
        self.password = QLineEdit()
        self.password.setMaximumWidth(460)
        self.password.setPlaceholderText("Password or PIN")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal = button("Show password", "ghost", tiny=True)
        self.reveal.setCheckable(True)
        self.reveal.toggled.connect(self._toggle)
        enter = button("Enter salon", "primary")
        enter.setMinimumHeight(48)
        enter.setMaximumWidth(460)
        enter.clicked.connect(self._login)
        self.password.returnPressed.connect(self._login)
        self.username.returnPressed.connect(self.password.setFocus)
        hint = QLabel("First sign-in  ·  Owner  admin / caveron1987    Reception  cashier / cashier123")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        form.addWidget(title)
        form.addWidget(note)
        form.addSpacing(18)
        form.addWidget(self.username)
        form.addWidget(self.password)
        form.addWidget(self.reveal, alignment=Qt.AlignmentFlag.AlignLeft)
        form.addSpacing(8)
        form.addWidget(enter)
        form.addSpacing(16)
        form.addWidget(hint)
        form.addStretch()

        root.addWidget(self.brand, 5)
        root.addWidget(form_host, 6)
        self._fit_login()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "brand_layout"):
            self._fit_login()

    def _fit_login(self) -> None:
        wide = self.width() >= 980
        compact = self.width() < 860
        margin = 28 if compact else 48 if not wide else 64
        self.brand_layout.setContentsMargins(margin, margin, margin, margin)
        self.form.setContentsMargins(margin, margin, margin, max(24, margin - 8))
        side = 160 if compact else 220 if not wide else 280
        self.logo.setPixmap(
            QPixmap(logo_path()).scaled(side, int(side * 0.78), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def _toggle(self, visible: bool) -> None:
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.reveal.setText("Hide password" if visible else "Show password")

    def _login(self) -> None:
        user = self.db.authenticate(self.username.text(), self.password.text())
        if not user:
            warn(self, "That username or password was not accepted.")
            return
        self.user = user
        self.accept()
