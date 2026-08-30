"""曲线图例（独立一行，位于折线图下方）：每路电机一个可点击图例项。

    - 左键点击：开关该电机曲线显示（隐藏时名称变灰、色条变暗）。
    - 右键点击：开关该电机突出显示（渲染置顶）；同一时刻仅一个电机可突出
      显示——右键另一路时自动切换过去，再右键当前高亮项则取消。

点击后通过信号把状态传给 LivePlot（item_visible_changed / item_highlight_changed）。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QWidget,
)

from .live_plot import COLORS

_HL_BG = "#233140"      # 突出显示项的底色
_HL_BORDER = "#3498db"  # 突出显示项的边框色


class _LegendItem(QFrame):
    visible_changed = Signal(int, bool)      # (通道号, 是否显示)
    highlight_changed = Signal(int, bool)    # (通道号, 是否突出显示)

    def __init__(self, index: int, name: str, color: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._color = QColor(color)
        self._visible = True
        self._highlighted = False

        self.swatch = QLabel()
        self.swatch.setFixedSize(20, 4)
        self.name = QLabel(name)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        lay.addWidget(self.swatch)
        lay.addWidget(self.name)

        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(
            f"{name}：左键=显示/隐藏曲线；右键=突出显示（置顶，仅一个）")
        self._refresh()

    # ---- 外部同步状态 ----
    def set_visible(self, on: bool) -> None:
        self._visible = bool(on)
        self._refresh()

    def set_highlighted(self, on: bool) -> None:
        self._highlighted = bool(on)
        self._refresh()

    def _refresh(self) -> None:
        name_color = "#ddd" if self._visible else "#555"
        sw = self._color.name() if self._visible else "#444"
        border = f"border:1px solid {_HL_BORDER};" if self._highlighted else ""
        bg = f"background:{_HL_BG};" if self._highlighted else ""
        bold = "font-weight:bold;" if self._highlighted else ""
        self.name.setStyleSheet(
            f"color:{name_color};font-size:11px;{bold}")
        self.swatch.setStyleSheet(
            f"background:{sw};border-radius:2px;{border}")
        self.setStyleSheet(bg)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._visible = not self._visible
            self._refresh()
            self.visible_changed.emit(self._index, self._visible)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.highlight_changed.emit(self._index, not self._highlighted)
            event.accept()
        else:
            super().mousePressEvent(event)


class PlotLegend(QWidget):
    item_visible_changed = Signal(int, bool)
    item_highlight_changed = Signal(int, bool)

    def __init__(self, names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[_LegendItem] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(8)
        for i, name in enumerate(names):
            item = _LegendItem(i, name, COLORS[i % len(COLORS)])
            item.visible_changed.connect(self._on_item_visible)
            item.highlight_changed.connect(self._on_item_highlight)
            self._items.append(item)
            lay.addWidget(item)
        lay.addStretch(1)

    # ---- 信号转发 ----
    def _on_item_visible(self, index: int, on: bool) -> None:
        self.item_visible_changed.emit(index, on)

    def _on_item_highlight(self, index: int, on: bool) -> None:
        """同一时刻仅一个电机突出显示：开启时清除其它项。"""
        if on:
            for j, it in enumerate(self._items):
                it.set_highlighted(j == index)
        else:
            self._items[index].set_highlighted(False)
        self.item_highlight_changed.emit(index, on)
