"""轻量实时曲线控件：用 QPainter 绘制滚动曲线，无第三方绘图依赖。

特性：
    - 内存窗口可配置（默认 100000 点/通道），超出自动丢弃旧数据（GC）；
    - 鼠标左键左右拖动平移时间轴（最大平移到内存最早数据）；
    - 滚轮缩放 Y 轴、Ctrl+滚轮缩放 X 轴（以光标为锚点），双击复位视图；
    - 左侧 Y 轴刻度随缩放自动调整精度（nice step / 小数位）；
    - 每条通道的设定转速以同色虚线半透明水平线显示。

用法：
    plot = LivePlot(channels=6, names=[...])
    plot.push([erpm0, erpm1, ...])   # 每次收到一帧调用一次
    plot.set_targets([...])          # 更新设定转速参考线
    plot.clear()
"""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .. import config

COLORS = ["#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6", "#1abc9c"]
BG_COLOR = "#1e1e1e"
GRID_COLOR = "#2d2d2d"
ZERO_COLOR = "#4a4a4a"
AXIS_COLOR = "#8a8a8a"
TARGET_ALPHA = 110       # 设定转速虚线透明度 (0-255)
_DEFAULT_Y = 1000.0      # 无数据时的默认 Y 半幅


def _nice_step(lo: float, hi: float, max_ticks: int = 6) -> float:
    """返回覆盖 [lo, hi] 的“漂亮”刻度步长（1/2/2.5/5 × 10^k）。"""
    span = hi - lo
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / max_ticks
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= m * mag:
            return m * mag
    return 10.0 * mag


def _decimals_for_step(step: float) -> int:
    """根据步长推断标签小数位数（如 0.5 -> 1，0.25 -> 2，500 -> 0）。"""
    s = f"{step:.6f}".rstrip("0")
    if "." in s:
        return len(s.split(".")[1])
    return 0


class LivePlot(QWidget):
    def __init__(self, channels: int = 6, names: list[str] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._channels = max(1, channels)
        self._names = names or [f"V{i + 1}" for i in range(self._channels)]
        self._max_points = max(100, int(config.get_max_points()))
        self._data = [deque(maxlen=self._max_points)
                      for _ in range(self._channels)]
        self._total = 0                 # 累计接收帧数（决定绝对索引）
        self._targets: list[float | None] = [None] * self._channels
        # X 轴时间换算：MCU 信息发送周期（可配置），每采样点对应真实时间
        self._sample_interval_s = max(
            0.01, config.get_send_interval_ms() / 1000.0)
        self._show_x_axis = config.get_show_x_axis()

        # 视图状态
        self._follow = True             # 是否自动跟随最新数据
        self._view_end_abs = 0          # 视口右缘对应的绝对采样索引
        self._points_per_px = 1.0       # X 缩放：每像素多少采样点
        self._auto_y = True             # Y 轴是否自动适配数据范围
        self._y_lo = -_DEFAULT_Y
        self._y_hi = _DEFAULT_Y

        # 交互状态
        self._dragging = False
        self._drag_px = 0.0
        self._drag_py = 0.0
        self._drag_end_abs = 0
        self._y_pan_started = False     # 垂直拖动是否已开始（超过阈值才冻结 Y）
        self._drag_auto_y = True
        self._drag_base_lo = -_DEFAULT_Y
        self._drag_base_hi = _DEFAULT_Y

        self.setMinimumHeight(200)
        self.setToolTip(
            "左键拖动：左右平移时间轴，上下平移数值（Y 轴）\n"
            "滚轮：以图像中心缩放 Y 轴\n"
            "Ctrl+滚轮：以图像中心缩放 X 轴（时间）\n"
            "双击：复位视图并跟随最新")

    # ---------------- 数据入口 ----------------
    def push(self, values) -> None:
        """追加一帧采样（长度可小于通道数，缺省为 None）。"""
        for i in range(self._channels):
            v = values[i] if i < len(values) else None
            self._data[i].append(v)
        self._total += 1
        if self._follow:
            self._view_end_abs = self._total - 1
        self.update()

    def set_targets(self, values) -> None:
        """更新每条通道的设定转速参考线（None/非法值显示为 None=不画）。"""
        changed = False
        for i in range(self._channels):
            v = values[i] if i < len(values) else None
            if v is not None:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    v = None
                if v is not None and not math.isfinite(v):
                    v = None
            if v != self._targets[i]:
                self._targets[i] = v
                changed = True
        if changed:
            self.update()

    def set_max_points(self, n: int) -> None:
        """调整每通道内存点数；超出部分立即丢弃（deque 截尾）。"""
        n = max(10, int(n))
        if n == self._max_points:
            return
        self._max_points = n
        self._data = [deque(d, maxlen=n) for d in self._data]
        self.update()

    def set_sample_interval(self, ms: int) -> None:
        """设置 MCU 信息发送周期（ms），用于换算 X 轴相对时间。"""
        self._sample_interval_s = max(0.01, int(ms) / 1000.0)
        self.update()

    def set_show_x_axis(self, on: bool) -> None:
        """是否显示 X 轴（相对时间刻度与竖向网格）。"""
        self._show_x_axis = bool(on)
        self.update()

    def clear(self) -> None:
        for d in self._data:
            d.clear()
        self._total = 0
        self._view_end_abs = 0
        self._follow = True
        self._auto_y = True
        self.update()

    def reset_view(self) -> None:
        """回到最新数据、默认缩放、Y 轴自动适配。"""
        self._follow = True
        self._auto_y = True
        self._points_per_px = 1.0
        self._view_end_abs = self._total - 1 if self._total else 0
        self.update()

    # ---------------- 几何 / 映射 ----------------
    def _plot_rect(self) -> QRectF:
        w, h = self.width(), self.height()
        margin = 6
        axis_w = 58       # 左侧 Y 轴标签宽度
        legend_h = 16
        x_axis_h = 18     # 底部 X 轴标签高度
        return QRectF(
            margin + axis_w, margin,
            max(1, w - 2 * margin - axis_w),
            max(1, h - 2 * margin - legend_h - x_axis_h))

    def _visible_bounds(self) -> tuple[int, int]:
        """可见采样绝对索引区间 [start, end]（含两端）。"""
        plot = self._plot_rect()
        visible_points = max(1, int(plot.width() * self._points_per_px))
        total = self._total
        if total == 0:
            return 0, 0
        oldest = total - len(self._data[0])
        max_end = total - 1
        min_end = oldest + visible_points - 1
        if min_end > max_end:
            min_end = max_end
        end = max(min(int(self._view_end_abs), max_end), min_end)
        start = end - visible_points + 1
        return start, end

    def _x_for(self, abs_idx: int, start: int, end: int, plot: QRectF) -> float:
        if end - start <= 0:
            return plot.right()
        frac = (abs_idx - start) / (end - start)
        return plot.left() + frac * plot.width()

    def _y_for(self, v: float, y_lo: float, y_hi: float, plot: QRectF) -> float:
        if y_hi <= y_lo:
            return plot.top()
        return plot.bottom() - (v - y_lo) / (y_hi - y_lo) * plot.height()

    def _base_y_range(self, start: int, end: int) -> tuple[float, float]:
        """可见窗口内数据的 Y 范围（带边距；下采样控制扫描量）。"""
        vals: list[float] = []
        for d in self._data:
            oldest = self._total - len(d)
            s = max(start - oldest, 0)
            e = min(end - oldest, len(d) - 1)
            if s > e:
                continue
            n = e - s + 1
            stride = max(1, n // 512)
            for i in range(s, e + 1, stride):
                v = d[i]
                if v is not None and math.isfinite(v):
                    vals.append(v)
        if not vals:
            return -_DEFAULT_Y, _DEFAULT_Y
        lo, hi = min(vals), max(vals)
        if lo == hi:
            lo -= _DEFAULT_Y
            hi += _DEFAULT_Y
        pad = max((hi - lo) * 0.1, 1.0)
        return lo - pad, hi + pad

    # ---------------- 绘制 ----------------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return
        p.fillRect(self.rect(), QColor(BG_COLOR))

        plot = self._plot_rect()
        if plot.width() <= 0 or plot.height() <= 0:
            p.end()
            return

        start, end = self._visible_bounds()
        if self._auto_y:
            self._y_lo, self._y_hi = self._base_y_range(start, end)
        y_lo, y_hi = self._y_lo, self._y_hi
        if y_hi <= y_lo:
            y_lo, y_hi = -_DEFAULT_Y, _DEFAULT_Y

        self._draw_grid(p, plot, y_lo, y_hi, start, end)
        self._draw_target_lines(p, plot, y_lo, y_hi)
        for c in range(self._channels):
            self._draw_channel(p, c, start, end, plot, y_lo, y_hi)
        self._draw_axis_labels(p, plot, y_lo, y_hi, start, end)
        self._draw_legend(p, plot)
        p.end()

    def _draw_grid(self, p, plot, y_lo, y_hi, start, end) -> None:
        # 水平网格（按 nice step）
        step = _nice_step(y_lo, y_hi, 6)
        p.setPen(QPen(QColor(GRID_COLOR), 1))
        t = math.ceil(y_lo / step) * step
        while t <= y_hi + 1e-9:
            y = self._y_for(t, y_lo, y_hi, plot)
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            t += step
        # 垂直网格（按相对时间 nice step；隐藏 X 轴时不画）
        span_s = (end - start) * self._sample_interval_s
        if self._show_x_axis and span_s > 0:
            step_s = _nice_step(-span_s, 0.0, 6)
            t_s = math.ceil(-span_s / step_s) * step_s
            while t_s <= 0.0 + 1e-9:
                frac = (t_s - (-span_s)) / span_s
                x = plot.left() + frac * plot.width()
                p.drawLine(int(x), int(plot.top()), int(x), int(plot.bottom()))
                t_s += step_s
        # 零轴加重
        if y_lo < 0.0 < y_hi:
            zy = self._y_for(0.0, y_lo, y_hi, plot)
            p.setPen(QPen(QColor(ZERO_COLOR), 1))
            p.drawLine(int(plot.left()), int(zy), int(plot.right()), int(zy))

    def _draw_target_lines(self, p, plot, y_lo, y_hi) -> None:
        """设定转速：每通道同色虚线、半透明水平线。"""
        for c in range(self._channels):
            t = self._targets[c]
            if t is None:
                continue
            if not (y_lo < t < y_hi):
                continue
            y = self._y_for(t, y_lo, y_hi, plot)
            color = QColor(COLORS[c % len(COLORS)])
            color.setAlpha(TARGET_ALPHA)
            pen = QPen(color, 1.2)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))

    def _draw_channel(self, p, c: int, start, end, plot, y_lo, y_hi) -> None:
        d = self._data[c]
        oldest = self._total - len(d)
        s = max(start - oldest, 0)
        e = min(end - oldest, len(d) - 1)
        if s > e:
            return
        n = e - s + 1
        color = COLORS[c % len(COLORS)]
        ncols = max(1, int(plot.width()))

        if n <= ncols:
            # 稀疏：逐点折线
            p.setPen(QPen(QColor(color), 1.6))
            prev: tuple[float, float] | None = None
            for i in range(s, e + 1):
                v = d[i]
                if v is None or not math.isfinite(v):
                    prev = None
                    continue
                x = self._x_for(i, start, end, plot)
                y = self._y_for(v, y_lo, y_hi, plot)
                if prev is not None:
                    p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)
        else:
            # 稠密：逐像素列 min/max 频带（下采样绘制，控制开销）
            stride = max(1, n // (ncols * 4))
            cols: dict[int, tuple[float, float]] = {}
            for i in range(s, e + 1, stride):
                v = d[i]
                if v is None or not math.isfinite(v):
                    continue
                col = int((i - start) * (ncols - 1) / (end - start)) \
                    if end > start else 0
                col = max(0, min(ncols - 1, col))
                lo, hi = cols.get(col, (v, v))
                cols[col] = (lo if lo < v else v, hi if hi > v else v)
            p.setPen(QPen(QColor(color), 1.2))
            for col, (lo, hi) in cols.items():
                x = plot.left() + col
                y0 = self._y_for(hi, y_lo, y_hi, plot)
                y1 = self._y_for(lo, y_lo, y_hi, plot)
                p.drawLine(int(x), int(y0), int(x), int(y1))

    def _draw_axis_labels(self, p, plot, y_lo, y_hi, start, end) -> None:
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        fm = QFontMetrics(font)

        # 左侧 Y 轴标签
        step = _nice_step(y_lo, y_hi, 6)
        dec = _decimals_for_step(step)
        x_right = int(plot.left()) - 5
        p.setPen(QPen(QColor(AXIS_COLOR), 1))
        t = math.ceil(y_lo / step) * step
        while t <= y_hi + 1e-9:
            y = self._y_for(t, y_lo, y_hi, plot)
            text = f"{t:.{dec}f}"
            y_text = int(y) + fm.ascent() // 2 - 1
            if y_text < fm.ascent() // 2:
                y_text = fm.ascent() // 2
            p.drawText(x_right - fm.horizontalAdvance(text), y_text, text)
            t += step

        # 底部 X 轴相对时间标签（可在设置中隐藏）
        span_s = (end - start) * self._sample_interval_s
        if self._show_x_axis and span_s > 0:
            step_s = _nice_step(-span_s, 0.0, 6)
            dec_s = _decimals_for_step(step_s)
            t_s = math.ceil(-span_s / step_s) * step_s
            while t_s <= 0.0 + 1e-9:
                frac = (t_s - (-span_s)) / span_s
                x = plot.left() + frac * plot.width()
                text = f"{t_s:.{dec_s}f}s"
                p.drawText(QRectF(x - 30, plot.bottom() + 4, 60, 14),
                           Qt.AlignHCenter | Qt.AlignVCenter, text)
                t_s += step_s

    def _draw_legend(self, p, plot) -> None:
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        x = plot.left()
        for c in range(self._channels):
            p.setPen(QPen(QColor(COLORS[c % len(COLORS)]), 1))
            p.drawText(QRectF(x, plot.bottom() + 20, 84, 16),
                       Qt.AlignLeft | Qt.AlignVCenter, self._names[c])
            x += 86

    # ---------------- 交互 ----------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_px = event.position().x()
            self._drag_py = event.position().y()
            self._drag_end_abs = self._visible_bounds()[1]
            self._y_pan_started = False
            self._drag_auto_y = self._auto_y
            self._drag_base_lo = self._y_lo
            self._drag_base_hi = self._y_hi
            self._follow = False
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self._dragging:
            return
        x = event.position().x()
        y = event.position().y()
        # 水平分量：平移时间轴
        self._view_end_abs = int(
            self._drag_end_abs - (x - self._drag_px) * self._points_per_px)
        # 垂直分量：平移 Y 轴（超过阈值才启动，避免纯横向拖动冻结自动适配）
        dy = y - self._drag_py
        if not self._y_pan_started and abs(dy) >= 3:
            self._y_pan_started = True
            if self._drag_auto_y:
                start, end = self._visible_bounds()
                self._drag_base_lo, self._drag_base_hi = \
                    self._base_y_range(start, end)
                self._auto_y = False
                self._y_lo = self._drag_base_lo
                self._y_hi = self._drag_base_hi
        if self._y_pan_started:
            plot = self._plot_rect()
            scale = (self._drag_base_hi - self._drag_base_lo) / \
                plot.height() if plot.height() > 0 else 0.0
            shift = dy * scale
            self._y_lo = self._drag_base_lo + shift
            self._y_hi = self._drag_base_hi + shift
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.reset_view()
            event.accept()

    def wheelEvent(self, event) -> None:
        # 优先用像素增量（触控板），没有则用角度增量（传统滚轮）
        delta = event.pixelDelta().y()
        if delta == 0:
            delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.2 if delta > 0 else 1 / 1.2
        # 以图像正中心为基准缩放：不拖动时缩放不改变中心位置
        center = self._plot_rect().center()
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+滚轮：缩放 X（时间）轴
            self._zoom_x(factor, center.x())
        else:
            # 普通滚轮：仅缩放 Y（数值）轴
            self._zoom_y(factor, center.y())
        event.accept()

    def _zoom_x(self, factor: float, anchor_x: float) -> None:
        """以图像中心为锚点缩放 X（时间）轴。"""
        old_ppx = self._points_per_px
        new_ppx = max(0.05, min(old_ppx / factor, 2000.0))
        # 先按旧缩放取当前视口，保证锚点（中心）是缩放前的中心
        start, end = self._visible_bounds()
        plot = self._plot_rect()
        if plot.width() <= 0 or end <= start:
            return
        frac = max(0.0, min(1.0, (anchor_x - plot.left()) / plot.width()))
        anchor_idx = start + frac * (end - start)
        new_visible = max(1, int(plot.width() * new_ppx))
        self._points_per_px = new_ppx
        # 让新视口内 frac 位置仍落在 anchor_idx：end = anchor + (1-frac)(new_visible-1)
        self._view_end_abs = int(
            anchor_idx + (1.0 - frac) * (new_visible - 1))
        self.update()

    def _zoom_y(self, factor: float, anchor_y: float) -> None:
        """以图像中心为锚点缩放 Y（数值）轴。"""
        start, end = self._visible_bounds()
        if self._auto_y:
            self._y_lo, self._y_hi = self._base_y_range(start, end)
        y_lo, y_hi = self._y_lo, self._y_hi
        span = y_hi - y_lo
        if span <= 0:
            return
        plot = self._plot_rect()
        frac = max(0.0, min(1.0, (anchor_y - plot.top()) / plot.height()))
        v_anchor = y_hi - frac * span
        new_span = max(1.0, min(span / factor, 4_000_000.0))
        self._auto_y = False
        self._y_lo = v_anchor - frac * new_span
        self._y_hi = self._y_lo + new_span
        self.update()

