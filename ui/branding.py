"""Generate the fallback monogram and the thermal logo."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen

from core.paths import ensure_dirs, user_path
from services.imaging import prepare_logo
from ui.theme import font_brand, font_ui


def logo_path() -> str:
    return user_path("assets", "caveron_logo.png")


def thermal_logo_path() -> str:
    return user_path("assets", "caveron_logo_thermal.png")


def ensure_brand_assets() -> str:
    ensure_dirs()
    path = logo_path()
    if not os.path.exists(path):
        draw_monogram(path)
    refresh_thermal()
    write_icon(path)
    return path


def refresh_thermal() -> None:
    image = prepare_logo(logo_path(), 384, 300)
    if image is not None:
        image.save(thermal_logo_path(), "PNG")


def replace_logo(source: str) -> None:
    image = QImage(source)
    if image.isNull():
        raise ValueError("That image could not be read. Use a PNG or JPG.")
    ensure_dirs()
    if not image.save(logo_path(), "PNG"):
        raise ValueError("The logo could not be saved.")
    refresh_thermal()
    write_icon(logo_path())


def restore_monogram() -> None:
    draw_monogram(logo_path())
    refresh_thermal()
    write_icon(logo_path())


def draw_monogram(path: str) -> None:
    size = 768
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor("#0B0B0D"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gold = QPen(QColor("#C9A96E"))
    gold.setWidth(8)
    painter.setPen(gold)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(48, 48, 672, 672)
    silver = QPen(QColor("#D4D6DC"))
    silver.setWidth(2)
    painter.setPen(silver)
    painter.drawEllipse(78, 78, 612, 612)
    painter.setPen(QColor("#F5F5F7"))
    painter.setFont(font_brand(150))
    painter.drawText(image.rect().adjusted(0, -20, 0, 0), Qt.AlignmentFlag.AlignCenter, "C")
    painter.setFont(font_ui(18))
    painter.setPen(QColor("#C9A96E"))
    painter.drawText(image.rect().adjusted(0, 250, 0, 0), Qt.AlignmentFlag.AlignCenter, "EST. 1987")
    painter.end()
    image.save(path, "PNG")


def write_icon(path: str) -> None:
    try:
        from PIL import Image

        icon = Image.open(path).convert("RGBA")
        icon.save(user_path("assets", "caveron.ico"), sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    except Exception:
        return


def window_icon() -> QIcon:
    return QIcon(logo_path())
