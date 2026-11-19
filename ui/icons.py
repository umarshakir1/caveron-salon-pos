"""Small silver line icons for the sidebar."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

_CACHE: dict[str, QIcon] = {}


def nav_icon(kind: str, color: str = "#E4E6EC") -> QIcon:
    key = f"{kind}:{color}"
    if key not in _CACHE:
        _CACHE[key] = QIcon(_paint(kind, color))
    return _CACHE[key]


def _paint(kind: str, color: str) -> QPixmap:
    pix = QPixmap(48, 48)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(2.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "dashboard":
        painter.drawRoundedRect(8, 8, 14, 14, 3, 3)
        painter.drawRoundedRect(26, 8, 14, 14, 3, 3)
        painter.drawRoundedRect(8, 26, 14, 14, 3, 3)
        painter.drawRoundedRect(26, 26, 14, 14, 3, 3)
    elif kind == "pos":
        painter.drawRoundedRect(14, 8, 20, 32, 3, 3)
        painter.drawLine(18, 16, 30, 16)
        painter.drawLine(18, 22, 30, 22)
        painter.drawLine(18, 28, 26, 28)
    elif kind == "groom":
        painter.drawEllipse(14, 16, 20, 20)
        painter.drawPolyline([QPointF(16, 20), QPointF(24, 10), QPointF(32, 20)])
    elif kind == "appointments":
        painter.drawRoundedRect(10, 12, 28, 26, 3, 3)
        painter.drawLine(10, 20, 38, 20)
        painter.drawLine(18, 8, 18, 16)
        painter.drawLine(30, 8, 30, 16)
    elif kind == "catalog":
        painter.drawLine(12, 14, 36, 14)
        painter.drawLine(12, 24, 36, 24)
        painter.drawLine(12, 34, 28, 34)
    elif kind == "staff":
        painter.drawEllipse(18, 8, 12, 12)
        painter.drawArc(10, 28, 28, 20, 0 * 16, 180 * 16)
    elif kind == "payroll":
        painter.drawRoundedRect(8, 14, 32, 20, 3, 3)
        painter.drawEllipse(20, 18, 8, 8)
    elif kind == "expenses":
        painter.drawRect(10, 16, 28, 20)
        painter.drawLine(10, 16, 24, 8)
        painter.drawLine(24, 8, 38, 16)
    elif kind == "drawer":
        painter.drawRoundedRect(10, 16, 28, 18, 3, 3)
        painter.drawLine(10, 22, 38, 22)
        painter.drawLine(24, 22, 24, 28)
    elif kind == "reports":
        painter.drawLine(12, 36, 12, 22)
        painter.drawLine(22, 36, 22, 14)
        painter.drawLine(32, 36, 32, 18)
        painter.drawLine(8, 38, 40, 38)
    else:
        painter.drawEllipse(14, 14, 20, 20)
        painter.drawEllipse(20, 20, 8, 8)
    painter.end()
    return pix
