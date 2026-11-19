"""Draw a thermal slip to an image so preview, PDF, and graphic print match."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen

from services.barcode import code128_modules

PAPER = "#F7F4EE"
INK = "#161616"


def render_slip_image(lines: list[dict], paper: str = "80", logo_path: str = "") -> QImage:
    chars = 48 if str(paper) == "80" else 32
    normal = QFont("Consolas")
    normal.setStyleHint(QFont.StyleHint.Monospace)
    normal.setPointSize(11)
    bold = QFont(normal)
    bold.setBold(True)
    large = QFont(normal)
    large.setBold(True)
    large.setPointSize(16)
    metrics = QFontMetrics(normal)
    char_width = max(7, metrics.horizontalAdvance("0"))
    width = chars * char_width + 36
    logo = QImage()
    if logo_path and os.path.exists(logo_path):
        logo.load(logo_path)
        if not logo.isNull():
            logo = logo.scaled(width - 80, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    ops: list[tuple] = []
    y = 16
    for line in lines:
        kind = line.get("t")
        if kind == "logo" and not logo.isNull():
            ops.append(("logo", y))
            y += logo.height() + 8
        elif kind == "gap":
            y += 8
        elif kind == "rule":
            ops.append(("rule", y + 4))
            y += 14
        elif kind == "barcode":
            ops.append(("barcode", y, line.get("text") or ""))
            y += 86
        else:
            font = large if line.get("big") else bold if line.get("bold") else normal
            ops.append(("text", y, line, font))
            y += QFontMetrics(font).height() + 2
    y += 16
    image = QImage(width, max(y, 80), QImage.Format.Format_RGB32)
    image.fill(QColor(PAPER))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    if not logo.isNull():
        for op in ops:
            if op[0] == "logo":
                painter.drawImage((width - logo.width()) // 2, op[1], logo)
    for op in ops:
        if op[0] == "rule":
            painter.setPen(QPen(QColor(INK), 1))
            painter.drawLine(18, op[1], width - 18, op[1])
        elif op[0] == "barcode":
            _draw_barcode(painter, op[2], 18, op[1], width - 36)
        elif op[0] == "text":
            _, top, line, font = op
            painter.setFont(font)
            painter.setPen(QColor(INK))
            rect_height = QFontMetrics(font).height() + 2
            if line.get("t") == "pair":
                painter.drawText(18, top, width - 36, rect_height, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line.get("left") or "")
                painter.drawText(18, top, width - 36, rect_height, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, line.get("right") or "")
            else:
                align = Qt.AlignmentFlag.AlignVCenter
                if line.get("align") == "center":
                    align |= Qt.AlignmentFlag.AlignHCenter
                elif line.get("align") == "right":
                    align |= Qt.AlignmentFlag.AlignRight
                else:
                    align |= Qt.AlignmentFlag.AlignLeft
                painter.drawText(18, top, width - 36, rect_height, align, line.get("text") or "")
    painter.end()
    return image


def _draw_barcode(painter: QPainter, text: str, x: int, y: int, width: int) -> None:
    modules = code128_modules(text)
    total = sum(module[1] for module in modules) + 20
    module_px = max(1, min(3, width // max(total, 1)))
    used = (total - 20) * module_px
    cursor = x + max(0, (width - used) // 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(INK))
    for is_bar, module_width in modules:
        pixel_width = module_width * module_px
        if is_bar:
            painter.drawRect(cursor, y, pixel_width, 52)
        cursor += pixel_width
    painter.setPen(QColor(INK))
    font = QFont("Consolas", 9)
    painter.setFont(font)
    painter.drawText(x, y + 54, width, 22, Qt.AlignmentFlag.AlignHCenter, text)
