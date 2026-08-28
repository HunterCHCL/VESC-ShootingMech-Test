"""轻量实时曲线控件：用 QPainter 绘制滚动曲线，无第三方绘图依赖。

用法：
    plot = LivePlot(channels=6, names=[...])
    plot.push([erpm0, erpm1, ...])   # 每次收到一帧调用一次
    plot.clear()
"""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

COLORS = ["#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6", "#1abc9c"]
BG_COLOR = "#1e1e1e"
GRID_COLOR = "#2d2d2d"
ZERO_COLOR = "#4a4a4a"


class LivePlot(QWidget):
    MAX_POINTS = 400  # 每通道保留的最大采样点数（滚动窗口）

    def __init__(self, channels: int = 6, names: list[str] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channels = max(1, channels)
        self._names = names or [f"V{i + 1}" for i in range(self._channels)]
        self._data = [deque(maxlen=self.MAX_POINTS)
                      for _ in range(self._channels)]
        self.setMinimumHeight(200)

    def push(self, values) -> None:
        """追加一帧采样（长度可小于通道数，缺省为 None）。"""
        for i in range(self._channels):
            v = values[i] if i < len(values) else None
            self._data[i].append(v)
        self.update()

    def clear(self) -> None:
        for d in self._data:
            d.clear()
        self.update()

    def _range(self) -> tuple[float, float]:
        """Y 轴范围：取所有有效样本的 min/max 并加边距；无样本时用默认。"""
        vals = [v for d in self._data for v in d
                if v is not None and math.isfinite(v)]
        if not vals:
            return -1000.0, 1000.0
        lo, hi = min(vals), max(vals)
        if lo == hi:
            lo -= 1000.0
            hi += 1000.0
        pad = max((hi - lo) * 0.1, 1.0)
        return lo - pad, hi + pad

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return

        margin = 8
        legend_h = 16
        plot = QRectF(margin, margin, w - 2 * margin, h - 2 * margin - legend_h)
        if plot.width() <= 0 or plot.height() <= 0:
            p.end()
            return

        p.fillRect(self.rect(), QColor(BG_COLOR))

        vmin, vmax = self._range()
        span = vmax - vmin

        # 网格
        p.setPen(QPen(QColor(GRID_COLOR), 1))
        for i in range(1, 5):
            y = plot.top() + plot.height() * i / 5
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
        for i in range(1, 8):
            x = plot.left() + plot.width() * i / 8
            p.drawLine(int(x), int(plot.top()), int(x), int(plot.bottom()))

        # 0 轴
        if vmin < 0.0 < vmax:
            zy = plot.bottom() - (0.0 - vmin) / span * plot.height()
            p.setPen(QPen(QColor(ZERO_COLOR), 1))
            p.drawLine(int(plot.left()), int(zy), int(plot.right()), int(zy))

        # 曲线
        step = plot.width() / (self.MAX_POINTS - 1) if self.MAX_POINTS > 1 \
            else plot.width()
        for c in range(self._channels):
            data = self._data[c]
            if not data:
                continue
            p.setPen(QPen(QColor(COLORS[c % len(COLORS)]), 1.6))
            n = len(data)
            prev: tuple[float, float] | None = None
            for i in range(n):
                v = data[i]
                if v is None or not math.isfinite(v):
                    prev = None  # 无效样本断开线段
                    continue
                x = plot.right() - (n - 1 - i) * step
                y = plot.bottom() - (v - vmin) / span * plot.height()
                if prev is not None:
                    p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)

        # 图例
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        x = plot.left()
        for c in range(self._channels):
            p.setPen(QPen(QColor(COLORS[c % len(COLORS)]), 1))
            p.drawText(QRectF(x, plot.bottom() + 4, 64, legend_h),
                       Qt.AlignLeft | Qt.AlignVCenter, self._names[c])
            x += 66

        p.end()
