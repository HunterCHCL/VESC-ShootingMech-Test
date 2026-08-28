"""数据监听页：六路实时 erpm 大字 + 实时曲线 + 滚动日志。

数据来源：MCU 每 100ms 回传的状态帧（6 × float32 erpm）。
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QVBoxLayout,
)

from .live_plot import COLORS, LivePlot

VESC_NAMES = ["V1/L1", "V2/R1", "V3/L2", "V4/R2", "V5/L3", "V6/R3"]


def _fmt(v, decimals: int = 0) -> str:
    """格式化数值；None / 非有限值显示「—」。"""
    if v is None or not math.isfinite(v):
        return "—"
    return f"{v:.{decimals}f}"


class MonitorPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        # 六路大字
        cell = QGridLayout()
        cell.setHorizontalSpacing(20)
        self._labels: list[QLabel] = []
        for i in range(6):
            name = QLabel(VESC_NAMES[i])
            name.setAlignment(Qt.AlignCenter)
            name.setStyleSheet(
                f"font-weight:bold;font-size:15px;color:{COLORS[i]};")
            val = QLabel("—")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet(
                "font-size:28px;font-weight:bold;color:#ecf0f1;"
                "font-family:Consolas;")
            val.setMinimumHeight(56)
            col = i % 3
            row = (i // 3) * 2
            cell.addWidget(name, row, col)
            cell.addWidget(val, row + 1, col)
            self._labels.append(val)
        for i in range(3):
            cell.setColumnStretch(i, 1)

        # 实时曲线
        self.plot = LivePlot(6, VESC_NAMES)

        # 滚动日志
        self.btn_clear = QPushButton("清空")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setStyleSheet("font-family:Consolas;font-size:12px;")
        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("最近接收 (erpm×6):"))
        log_row.addStretch(1)
        log_row.addWidget(self.btn_clear)

        lay = QVBoxLayout(self)
        lay.addLayout(cell)
        lay.addWidget(self.plot, 1)
        lay.addLayout(log_row)
        lay.addWidget(self.log, 1)

        self.btn_clear.clicked.connect(self.clear)

    def update_erpm(self, erpm: list) -> None:
        """刷新大字 + 追加曲线与日志。"""
        for lbl, v in zip(self._labels, erpm):
            lbl.setText(_fmt(v))
        self.plot.push(erpm)
        self.log.appendPlainText(",".join(_fmt(v) for v in erpm))

    def clear(self) -> None:
        self.plot.clear()
        self.log.clear()
        for lbl in self._labels:
            lbl.setText("—")
