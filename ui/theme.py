"""Obsidian, silver, and champagne theme."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from core.paths import resource, user_path

QSS = """
QMainWindow, QDialog, QWidget#page {
    background: #0B0B0D;
    color: #F5F5F7;
}
QWidget { color: #F5F5F7; }
QLabel { background: transparent; color: #F5F5F7; }
QLabel#muted, QLabel#fieldLabel { color: #8E8E9A; }
QLabel#eyebrow { color: #C9A96E; font-size: 11px; font-weight: 600; }
QLabel#kpiValue { font-size: 16px; font-weight: 650; color: #F5F5F7; }
QLabel#price { color: #F5F5F7; font-size: 13px; font-weight: 650; }
QLabel#priceGold { color: #C9A96E; font-size: 13px; font-weight: 650; }
QFrame#card, QFrame#serviceCard, QFrame#sidebar {
    background: #141418;
    border: 1px solid #2A2A32;
    border-radius: 14px;
}
QFrame#serviceCard:hover { background: #1E1E24; border: 1px solid #A8ACB8; }
QFrame#cartLine {
    background: #141418;
    border: 1px solid #2A2A32;
    border-radius: 8px;
}
QFrame#sidebar { border-radius: 0; border: none; border-right: 1px solid #2A2A32; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QTextEdit, QPlainTextEdit {
    background: #141418;
    border: 1px solid #2A2A32;
    border-radius: 8px;
    padding: 8px 10px;
    color: #F5F5F7;
    selection-background-color: #3A3A44;
}
QSpinBox, QDoubleSpinBox { padding-right: 28px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QTextEdit:focus {
    border: 1px solid #C9A96E;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #141418;
    color: #F5F5F7;
    border: 1px solid #2A2A32;
    selection-background-color: #2A2A32;
    outline: none;
}
QPushButton {
    border-radius: 8px;
    padding: 8px 14px;
    border: 1px solid #2A2A32;
    background: #1E1E24;
    color: #F5F5F7;
}
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D4D6DC, stop:1 #A8ACB8);
    color: #0B0B0D;
    border: none;
    font-weight: 650;
}
QPushButton#primary:hover { background: #E6E7EC; }
QPushButton#gold {
    background: transparent;
    color: #C9A96E;
    border: 1px solid #C9A96E;
    font-weight: 600;
}
QPushButton#gold:hover { background: #1E1E24; }
QPushButton#ghost { background: transparent; color: #F5F5F7; border: 1px solid #2A2A32; }
QPushButton#ghost:hover { background: #1E1E24; }
QPushButton#danger { background: transparent; color: #E74C3C; border: 1px solid #E74C3C; }
QPushButton#danger:hover { background: #2A1518; }
QPushButton#nav {
    text-align: left;
    padding: 11px 14px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: #C8C8D0;
}
QPushButton#nav:hover { background: #1E1E24; color: #F5F5F7; }
QPushButton#nav:checked {
    background: #1E1E24;
    color: #F5F5F7;
    border-left: 2px solid #C9A96E;
}
QPushButton#pill {
    background: #141418;
    border: 1px solid #2A2A32;
    border-radius: 16px;
    padding: 4px 14px;
    color: #F5F5F7;
}
QPushButton#pill:checked {
    background: #D4D6DC;
    color: #0B0B0D;
    border-color: #D4D6DC;
}
QPushButton:disabled { color: #8E8E9A; background: #1E1E24; }
QTableWidget {
    background: #141418;
    alternate-background-color: #18181D;
    border: 1px solid #2A2A32;
    border-radius: 10px;
    gridline-color: #2A2A32;
    selection-background-color: #2A2A32;
    selection-color: #F5F5F7;
}
QHeaderView::section {
    background: #1E1E24;
    color: #C9A96E;
    border: none;
    border-bottom: 1px solid #2A2A32;
    padding: 8px;
    font-weight: 600;
}
QTableWidget::item { padding: 4px 6px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0B0B0D; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #2A2A32; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #A8ACB8; }
QScrollBar:horizontal { background: #0B0B0D; height: 10px; }
QScrollBar::handle:horizontal { background: #2A2A32; border-radius: 5px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QTabWidget::pane { border: 1px solid #2A2A32; border-radius: 12px; background: #0B0B0D; top: -1px; }
QTabBar::tab {
    background: #141418;
    color: #8E8E9A;
    padding: 10px 16px;
    border: 1px solid #2A2A32;
    border-bottom: none;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected { background: #D4D6DC; color: #0B0B0D; }
QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; border: 1px solid #A8ACB8; background: #141418; border-radius: 4px;
}
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #C9A96E; border-color: #C9A96E; }
QSplitter::handle { background: #2A2A32; }
QToolTip { background: #1E1E24; color: #F5F5F7; border: 1px solid #C9A96E; padding: 6px; }
QCalendarWidget {
    background: #141418;
    border: 1px solid #2A2A32;
    border-radius: 14px;
}
QCalendarWidget QWidget { background: #141418; color: #F5F5F7; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background: #141418; border: none; }
QCalendarWidget QToolButton {
    color: #F5F5F7;
    background: transparent;
    border: none;
    padding: 4px 8px;
    border-radius: 6px;
}
QCalendarWidget QToolButton:hover { background: #1E1E24; color: #C9A96E; }
QCalendarWidget QAbstractItemView {
    background: #141418;
    color: #F5F5F7;
    selection-background-color: #C9A96E;
    selection-color: #0B0B0D;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled { color: #3A3A44; }
QMessageBox { background: #141418; }
"""


def load_fonts() -> None:
    folder = resource("fonts")
    if not os.path.isdir(folder):
        return
    for name in os.listdir(folder):
        if name.lower().endswith((".ttf", ".otf")):
            QFontDatabase.addApplicationFont(os.path.join(folder, name))


def font_ui(size: int = 10, bold: bool = False) -> QFont:
    font = QFont()
    font.setFamilies(["Plus Jakarta Sans", "Inter", "Segoe UI"])
    font.setPointSize(size)
    if bold:
        font.setWeight(QFont.Weight.DemiBold)
    return font


def font_brand(size: int = 20) -> QFont:
    font = QFont()
    font.setFamilies(["Cinzel", "Playfair Display", "Georgia"])
    font.setPointSize(size)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    return font


def _arrow_stylesheet(color: str) -> str:
    from PySide6.QtGui import QImage, QPainter, QPen

    folder = user_path("assets")
    os.makedirs(folder, exist_ok=True)

    def save(name: str, points: list[tuple[int, int]]) -> str:
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        from PySide6.QtCore import QPoint

        painter.drawPolyline([QPoint(x, y) for x, y in points])
        painter.end()
        path = os.path.join(folder, name)
        image.save(path, "PNG")
        return path.replace("\\", "/")

    down = save("arrow_down.png", [(3, 5), (8, 11), (13, 5)])
    up = save("arrow_up.png", [(3, 11), (8, 5), (13, 11)])
    left = save("arrow_left.png", [(11, 3), (5, 8), (11, 13)])
    right = save("arrow_right.png", [(5, 3), (11, 8), (5, 13)])
    return f"""
QComboBox::down-arrow, QDateEdit::down-arrow, QTimeEdit::down-arrow {{
    image: url("{down}");
    width: 12px;
    height: 12px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border: none;
    background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{up}");
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{down}");
    width: 10px;
    height: 10px;
}}
QCalendarWidget QToolButton#qt_calendar_prevmonth {{
    image: url("{left}");
    qproperty-icon: none;
}}
QCalendarWidget QToolButton#qt_calendar_nextmonth {{
    image: url("{right}");
    qproperty-icon: none;
}}
"""


def _indicator_stylesheet() -> str:
    from PySide6.QtGui import QImage, QPainter, QPen

    folder = user_path("assets")
    os.makedirs(folder, exist_ok=True)
    check_path = os.path.join(folder, "indicator_check.png")
    radio_path = os.path.join(folder, "indicator_radio.png")
    check = QImage(16, 16, QImage.Format.Format_ARGB32)
    check.fill(QColor(0, 0, 0, 0))
    painter = QPainter(check)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#C9A96E"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, 16, 16, 3, 3)
    pen = QPen(QColor("#0B0B0D"))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.drawLine(4, 8, 7, 12)
    painter.drawLine(7, 12, 12, 4)
    painter.end()
    check.save(check_path, "PNG")
    radio = QImage(16, 16, QImage.Format.Format_ARGB32)
    radio.fill(QColor(0, 0, 0, 0))
    painter = QPainter(radio)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#C9A96E"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, 15, 15)
    painter.setBrush(QColor("#0B0B0D"))
    painter.drawEllipse(5, 5, 6, 6)
    painter.end()
    radio.save(radio_path, "PNG")
    check_url = check_path.replace("\\", "/")
    radio_url = radio_path.replace("\\", "/")
    return (
        f"QCheckBox::indicator:checked {{ image: url({check_url}); }}\n"
        f"QRadioButton::indicator:checked {{ image: url({radio_url}); }}\n"
    )


def theme_colors(mode: str) -> dict:
    if mode == "light":
        return {
            "window": "#F3F0E8",
            "text": "#1C1B19",
            "card": "#FFFCF7",
            "elev": "#E8E2D4",
            "line": "#D5CFC3",
            "muted": "#6F6A60",
            "ink": "#1C1B19",
        }
    return {
        "window": "#0B0B0D",
        "text": "#F5F5F7",
        "card": "#141418",
        "elev": "#1E1E24",
        "line": "#2A2A32",
        "muted": "#8E8E9A",
        "ink": "#0B0B0D",
    }


def stylesheet_for(mode: str) -> str:
    if mode != "light":
        return QSS
    text = QSS
    text = text.replace("color: #0B0B0D;", "color: @@INK@@;")
    text = text.replace("selection-color: #0B0B0D;", "selection-color: @@INK@@;")
    for source, target in (
        ("#18181D", "#F7F4EC"),
        ("#0B0B0D", "#F3F0E8"),
        ("#141418", "#FFFCF7"),
        ("#1E1E24", "#E8E2D4"),
        ("#2A2A32", "#D5CFC3"),
        ("#3A3A44", "#E4DDD0"),
        ("#2A1518", "#F8E6E4"),
        ("#F5F5F7", "#1C1B19"),
        ("#C8C8D0", "#3C3933"),
        ("#8E8E9A", "#6F6A60"),
        ("@@INK@@", "#1C1B19"),
    ):
        text = text.replace(source, target)
    return text


def apply_theme(app: QApplication, mode: str = "dark") -> None:
    mode = "light" if mode == "light" else "dark"
    colors = theme_colors(mode)
    app.setProperty("caveronTheme", mode)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["card"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["elev"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["elev"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["line"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["elev"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["muted"]))
    app.setPalette(palette)
    ink = colors["text"]
    app.setStyleSheet(stylesheet_for(mode) + _indicator_stylesheet() + _arrow_stylesheet(ink))
    app.setFont(font_ui(10))
