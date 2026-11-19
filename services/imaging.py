"""Monochrome logo conversion for thermal slips."""

from __future__ import annotations

import os

from PySide6.QtGui import QImage, qRgb


def prepare_logo(path: str, max_width: int, max_height: int = 160) -> QImage | None:
    if not path or not os.path.exists(path):
        return None
    source = QImage(path)
    if source.isNull():
        return None
    from PySide6.QtCore import Qt

    source = source.convertToFormat(QImage.Format.Format_ARGB32)
    scaled = source.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    width = max(8, (scaled.width() + 7) // 8 * 8)
    height = scaled.height()
    gray = [[255] * width for _ in range(height)]
    opaque = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(scaled.width()):
            color = scaled.pixelColor(x, y)
            if color.alpha() < 40:
                gray[y][x] = 255
                continue
            gray[y][x] = int(0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue())
            opaque[y][x] = True
    split = _split_ink(gray, scaled.width(), height)
    if split is not None:
        gray = split
    else:
        _normalize_artwork(gray, opaque, width, height, scaled.width())
    for y in range(height):
        for x in range(width):
            old = gray[y][x]
            new = 0 if old < 128 else 255
            gray[y][x] = new
            if split is None:
                error = old - new
                _spread(gray, y, x + 1, error * 7 / 16, width, height)
                _spread(gray, y + 1, x - 1, error * 3 / 16, width, height)
                _spread(gray, y + 1, x, error * 5 / 16, width, height)
                _spread(gray, y + 1, x + 1, error * 1 / 16, width, height)
    image = QImage(width, height, QImage.Format.Format_Mono)
    image.setColor(0, qRgb(0, 0, 0))
    image.setColor(1, qRgb(255, 255, 255))
    image.fill(1)
    for y in range(height):
        for x in range(width):
            image.setPixel(x, y, 0 if gray[y][x] < 128 else 1)
    return image


def _normalize_artwork(gray, opaque, width, height, content_width):
    samples = []
    for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        samples.append(gray[y][min(x, content_width - 1)])
    corner = sum(samples) / len(samples)
    darkest = min((gray[y][x] for y in range(height) for x in range(width) if opaque[y][x]), default=0)
    if corner < 145:
        for y in range(height):
            for x in range(width):
                gray[y][x] = 255 - gray[y][x]
    elif darkest > 135:
        for y in range(height):
            for x in range(width):
                if opaque[y][x]:
                    gray[y][x] = 255 - gray[y][x]


def _split_ink(gray, content_width, height):
    """Pull a black mark out of the silver/black CAVERON lockup."""
    split = _split_column(gray, content_width, height)
    if split is None:
        return None
    step = 4
    left = [gray[y][x] for y in range(0, height, step) for x in range(0, split, step)]
    right = [gray[y][x] for y in range(0, height, step) for x in range(split, content_width, step)]
    if len(left) < 8 or len(right) < 8:
        return None
    left_bg = _percentile(left, 0.8)
    right_bg = _percentile(right, 0.2)
    if left_bg < right_bg + 70:
        return None
    left_cut = min(110, left_bg - 70)
    right_cut = max(right_bg + 36, 72)
    ink = [row[:] for row in gray]
    for y in range(height):
        for x in range(len(gray[0])):
            value = gray[y][x]
            if x >= content_width:
                ink[y][x] = 255
            elif x < split:
                ink[y][x] = 0 if value < left_cut else 255
            else:
                ink[y][x] = 0 if value > right_cut else 255
    for y in range(height):
        row = ink[y]
        for x in (split - 1, split, split + 1):
            if x < 4 or x + 4 >= content_width or row[x] != 0:
                continue
            if row[x - 4] == 255 and row[x + 4] == 255:
                row[x] = 255
        for x in range(1, content_width - 1):
            if row[x] == 255 and row[x - 1] == 0 and row[x + 1] == 0:
                row[x] = 0
    return ink


def _split_column(gray, content_width, height):
    if content_width < 24:
        return None
    step = max(1, height // 48)
    means = []
    for x in range(content_width):
        total = 0
        count = 0
        for y in range(0, height, step):
            total += gray[y][x]
            count += 1
        means.append(total / max(1, count))
    window = max(2, content_width // 90)
    best = None
    best_drop = 0
    for x in range(window, content_width - window):
        left = sum(means[x - window : x]) / window
        right = sum(means[x : x + window]) / window
        drop = left - right
        if drop > best_drop:
            best_drop = drop
            best = x
    if best is None or best_drop < 55:
        return None
    return best


def _percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def _spread(gray, y, x, amount, width, height):
    if 0 <= y < height and 0 <= x < width:
        gray[y][x] = min(255, max(0, gray[y][x] + amount))


def image_to_raster(image: QImage) -> bytes:
    width = image.width()
    height = image.height()
    width_bytes = (width + 7) // 8
    data = bytearray()
    for y in range(height):
        for block in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = block * 8 + bit
                if x < width and image.pixelColor(x, y).lightness() < 128:
                    byte |= 1 << (7 - bit)
            data.append(byte)
    header = bytes(
        [
            0x1D,
            0x76,
            0x30,
            0x00,
            width_bytes & 0xFF,
            (width_bytes >> 8) & 0xFF,
            height & 0xFF,
            (height >> 8) & 0xFF,
        ]
    )
    return header + bytes(data)
