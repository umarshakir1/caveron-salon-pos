"""On-screen thermal slip."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from services.slip_render import render_slip_image


class SlipPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self.setMinimumSize(280, 200)

    def set_slip(self, lines: list[dict], paper: str, logo_path: str) -> None:
        self._image = render_slip_image(lines, paper, logo_path)
        self.setFixedSize(self._image.size())
        self.update()

    def paintEvent(self, _event):
        if self._image is None:
            return
        painter = QPainter(self)
        painter.drawImage(0, 0, self._image)
        painter.end()
