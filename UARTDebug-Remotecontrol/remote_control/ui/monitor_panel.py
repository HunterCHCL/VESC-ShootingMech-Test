"""数据监听页：六路实时转速读数（左上）+ 实时曲线（右上）+ 滚动日志（下）。

上半部分为左右布局：左侧紧凑读数、右侧实时曲线，二者之间用可拖动分隔条；
上半区域与底部日志之间也用可拖动分隔条，三个区域可按需缩放。
数据来源：MCU 每 100ms 回传的状态帧（6 × float32 erpm）。

显示单位（ERPM / RPM，7 ERPM = 1 RPM）：读数 / 曲线 / 日志按当前显示单位
换算；发送与接收的数据始终为 ERPM（协议不变）。
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from .. import config, theme
from .live_plot import COLORS, LivePlot
from .plot_legend import PlotLegend

VESC_NAMES = ["V1/R1", "V2/R2", "V3/R3", "V4/F1", "V5/F2", "V6/F3"]


def _splitter_style(p: dict) -> str:
    """按主题配色生成分隔条样式。"""
    return (f"QSplitter::handle {{ background:{p['splitter']}; }} "
            f"QSplitter::handle:hover {{ background:{p['accent']}; }}")


def _fmt(v, decimals: int = 0) -> str:
    """格式化数值；None / 非有限值显示「—」。"""
    if v is None or not math.isfinite(v):
        return "—"
    return f"{v:.{decimals}f}"


class MonitorPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self._c = dict(theme.colors())
        theme.on_change(self._apply_theme)

        # ---- 左上：六路实时读数（紧凑） ----
        readouts = QWidget()
        readouts.setMinimumWidth(190)
        cell = QGridLayout(readouts)
        cell.setHorizontalSpacing(12)
        cell.setVerticalSpacing(4)
        cell.setContentsMargins(8, 8, 8, 8)
        self._labels: list[QLabel] = []
        self._unit = config.get_unit()        # 当前显示单位：erpm / rpm
        self._last_erpm: list | None = None   # 最近一帧实测（ERPM，协议单位）
        for i in range(6):
            name = QLabel(VESC_NAMES[i])
            name.setAlignment(Qt.AlignCenter)
            name.setStyleSheet(
                f"font-weight:bold;font-size:11px;color:{COLORS[i]};")
            val = QLabel("—")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet(
                "font-size:17px;font-weight:bold;"
                f"color:{self._c['readout_val']};font-family:Consolas;")
            val.setMinimumHeight(30)
            col = i % 2
            row = (i // 2) * 2
            cell.addWidget(name, row, col)
            cell.addWidget(val, row + 1, col)
            self._labels.append(val)
        for i in range(2):
            cell.setColumnStretch(i, 1)

        # ---- 右上：实时曲线 + 可点击图例 ----
        self.plot = LivePlot(6, VESC_NAMES)
        self.hint = QLabel(
            "拖拽平移（左右=时间轴，上下=数值）· 滚轮缩放 Y · "
            "Ctrl+滚轮缩放 X · 双击复位；虚线为设定转速")
        self.hint.setStyleSheet(
            f"background:{self._c['plot_bg']};"
            f"color:{self._c['hint']};font-size:11px;padding:4px;")
        self.legend = PlotLegend(VESC_NAMES)
        self.legend.item_visible_changed.connect(self.plot.set_channel_visible)
        self.legend.item_highlight_changed.connect(self._on_legend_highlight)
        # 右上容器：提示 + 曲线 + 图例整片区域与绘图区同色（黑色），
        # 避免白天模式下透出浅色背景形成白色间隔/白条。
        self._right = QWidget()
        self._right.setStyleSheet(
            f"background:{self._c['plot_bg']};")
        rv = QVBoxLayout(self._right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        rv.addWidget(self.hint)
        rv.addWidget(self.plot, 1)
        rv.addWidget(self.legend, 0)

        # ---- 上半部分：左右分栏（读数 | 曲线），可拖动分隔条 ----
        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.addWidget(readouts)
        self.top_splitter.addWidget(self._right)
        self.top_splitter.setStretchFactor(0, 0)
        self.top_splitter.setStretchFactor(1, 1)
        self.top_splitter.setSizes(config.get_top_splitter_sizes())
        self.top_splitter.setHandleWidth(6)
        self.top_splitter.setStyleSheet(_splitter_style(self._c))
        self.top_splitter.splitterMoved.connect(self._save_splitter_sizes)

        # ---- 底部：滚动日志 ----
        self.btn_clear = QPushButton("清空")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setStyleSheet("font-family:Consolas;font-size:12px;")
        log_row = QHBoxLayout()
        self.lbl_log_header = QLabel(f"最近接收 ({self._unit}×6):")
        log_row.addWidget(self.lbl_log_header)
        log_row.addStretch(1)
        log_row.addWidget(self.btn_clear)
        log_panel = QWidget()
        lv = QVBoxLayout(log_panel)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addLayout(log_row)
        lv.addWidget(self.log, 1)

        # ---- 整体：上下分栏（上半 | 日志），可拖动分隔条 ----
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.top_splitter)
        self.main_splitter.addWidget(log_panel)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes(config.get_main_splitter_sizes())
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet(_splitter_style(self._c))
        self.main_splitter.splitterMoved.connect(self._save_splitter_sizes)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.main_splitter, 1)

        self.btn_clear.clicked.connect(self.clear)

    def update_erpm(self, erpm: list) -> None:
        """刷新读数 + 追加曲线与日志（按当前显示单位换算）。"""
        self._last_erpm = list(erpm)
        self._render(erpm)

    def _render(self, erpm: list) -> None:
        """按当前显示单位渲染读数、曲线与日志（None 显示「—」）。"""
        disp = [config.to_display(v, self._unit) if v is not None else None
                for v in erpm]
        for lbl, v in zip(self._labels, disp):
            lbl.setText(_fmt(v))
        self.plot.push(disp)
        self.log.appendPlainText(",".join(_fmt(v) for v in disp))

    def set_unit(self, unit: str) -> None:
        """切换显示单位：更新表头，按新单位重绘读数；清空旧单位的曲线/日志。"""
        if unit == self._unit:
            return
        self._unit = unit
        self.lbl_log_header.setText(f"最近接收 ({unit}×6):")
        self.plot.clear()
        self.log.clear()
        if self._last_erpm is not None:
            self._render(self._last_erpm)
        else:
            for lbl in self._labels:
                lbl.setText("—")

    def set_targets(self, targets: list) -> None:
        """更新曲线上的设定转速参考线（来自控制页目标值）。"""
        self.plot.set_targets(targets)

    def _on_legend_highlight(self, index: int, on: bool) -> None:
        """图例右键：突出显示（置顶）该电机，-1 表示取消。"""
        self.plot.set_highlight(index if on else -1)

    def _save_splitter_sizes(self, *_args) -> None:
        """分隔条拖动中只更新内存，关闭窗口时统一写盘。"""
        config.set_top_splitter_sizes(list(self.top_splitter.sizes()))
        config.set_main_splitter_sizes(list(self.main_splitter.sizes()))

    def clear(self) -> None:
        self.plot.clear()
        self.log.clear()
        for lbl in self._labels:
            lbl.setText("—")

    def _apply_theme(self) -> None:
        """主题切换：刷新分隔条 / 读数 / 提示文字配色。"""
        self._c = dict(theme.colors())
        self._right.setStyleSheet(
            f"background:{self._c['plot_bg']};")
        style = _splitter_style(self._c)
        self.top_splitter.setStyleSheet(style)
        self.main_splitter.setStyleSheet(style)
        for lbl in self._labels:
            lbl.setStyleSheet(
                "font-size:17px;font-weight:bold;"
                f"color:{self._c['readout_val']};font-family:Consolas;")
        self.hint.setStyleSheet(
            f"background:{self._c['plot_bg']};"
            f"color:{self._c['hint']};font-size:11px;padding:4px;")

