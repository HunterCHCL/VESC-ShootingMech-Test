"""设置页：集中管理上位机可调参数。

当前包含「显示单位」「数据监测」两个分组：
    - 显示单位：ERPM / RPM 开关（7 ERPM = 1 RPM）。仅影响 UI 显示，
      发送与接收的数据始终为 ERPM（通信协议不变）。
    - 数据监测：
      - 曲线内存点数：数据监听页曲线每通道保留的最大采样数，
        曲线左右拖动可查看的历史范围不超过该值，超出自动丢弃（GC）。
      - 信息发送周期：MCU 状态帧发送周期（ms），决定 X 轴每采样点对应时间。
      - 显示 X 轴：是否显示曲线底部的相对时间轴刻度与竖向网格。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QLabel, QSpinBox,
    QVBoxLayout,
)

from .. import config, theme


class SettingsPanel(QFrame):
    unit_changed = Signal(str)  # 显示单位切换：'erpm' / 'rpm'

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

<<<<<<< HEAD
        # ---------------- 显示单位（ERPM / RPM） ----------------
        unit_box = QGroupBox("显示单位")
        unit_form = QGridLayout(unit_box)
        unit_form.setHorizontalSpacing(14)
        unit_form.setVerticalSpacing(8)

        self.combo_unit = QComboBox()
        self.combo_unit.addItem("ERPM", "erpm")
        self.combo_unit.addItem("RPM", "rpm")
        self.combo_unit.setCurrentIndex(1 if config.get_unit() == "rpm" else 0)
        self.combo_unit.setMinimumWidth(120)
        self.combo_unit.setToolTip(
            "UI 显示单位：ERPM 或 RPM。\n"
            "换算关系 7 ERPM = 1 RPM；切换后目标与实测读数、曲线、日志\n"
            "都会按新单位显示。发送与接收的数据始终为 ERPM（协议不变）。")
        unit_form.addWidget(QLabel("单位开关:"), 0, 0)
        unit_form.addWidget(self.combo_unit, 0, 1)
        unit_tip = QLabel(
            "换算关系：7 ERPM = 1 RPM。\n"
            "发送与接收的数据始终为 ERPM，仅显示换算为所选单位。")
        unit_tip.setStyleSheet("color:#888;")
        unit_tip.setWordWrap(True)
        unit_form.addWidget(unit_tip, 1, 0, 1, 2)
=======
        # ---------------- 外观 ----------------
        box_theme = QGroupBox("外观")
        form_theme = QGridLayout(box_theme)
        form_theme.setHorizontalSpacing(14)
        form_theme.setVerticalSpacing(8)

        self.combo_theme = QComboBox()
        self.combo_theme.setMinimumWidth(160)
        self.combo_theme.setToolTip(
            "选择界面外观主题：\n"
            "· 跟随系统：随系统深色/浅色设置自动切换；\n"
            "· 白天 / 黑夜：固定使用浅色 / 深色主题。")
        for mode in theme.MODES:
            self.combo_theme.addItem(theme.MODE_LABELS[mode], mode)
        cur = config.get_theme_mode()
        idx = self.combo_theme.findData(cur)
        self.combo_theme.setCurrentIndex(idx if idx >= 0 else 0)
        form_theme.addWidget(QLabel("界面主题:"), 0, 0)
        form_theme.addWidget(self.combo_theme, 0, 1)
>>>>>>> 1d31a183728543d2b62dfc4f59c31b2af9b6380e

        # ---------------- 数据监测 ----------------
        box = QGroupBox("数据监测")
        form = QGridLayout(box)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.spin_max_points = QSpinBox()
        self.spin_max_points.setRange(100, 2_000_000)
        self.spin_max_points.setSingleStep(1000)
        self.spin_max_points.setSuffix(" 个")
        self.spin_max_points.setValue(config.get_max_points())
        self.spin_max_points.setMinimumWidth(160)
        self.spin_max_points.setToolTip(
            "数据监听页曲线每通道保留的最大采样点数。\n"
            "曲线左右拖动可查看的历史范围不超过该值，\n"
            "超出部分自动丢弃（GC）。")
        form.addWidget(QLabel("曲线内存点数:"), 0, 0)
        form.addWidget(self.spin_max_points, 0, 1)

        self.spin_send_interval = QSpinBox()
        self.spin_send_interval.setRange(10, 10000)
        self.spin_send_interval.setSingleStep(10)
        self.spin_send_interval.setSuffix(" ms")
        self.spin_send_interval.setValue(config.get_send_interval_ms())
        self.spin_send_interval.setMinimumWidth(160)
        self.spin_send_interval.setToolTip(
            "MCU 回传信息（状态帧）的发送周期，单位毫秒。\n"
            "用于把曲线 X 轴的每 1 个采样点换算成真实时间；\n"
            "若 X 轴时间与实际不符，请改成固件的实际发送周期。")
        form.addWidget(QLabel("信息发送周期:"), 1, 0)
        form.addWidget(self.spin_send_interval, 1, 1)

        self.chk_show_x_axis = QCheckBox("显示 X 轴")
        self.chk_show_x_axis.setChecked(config.get_show_x_axis())
        self.chk_show_x_axis.setToolTip(
            "在曲线底部显示 X 轴（相对时间）刻度与竖向网格；\n"
            "取消后隐藏。")
        form.addWidget(self.chk_show_x_axis, 2, 0, 1, 2)

        self.tip = QLabel(
            "数据监听页曲线操作：左键拖动左右平移时间轴、上下平移数值，\n"
            "滚轮缩放 Y 轴，Ctrl+滚轮缩放 X 轴，双击复位并跟随最新数据。")
        self.tip.setStyleSheet(f"color:{theme.colors()['hint']};")
        self.tip.setWordWrap(True)

        lay = QVBoxLayout(self)
<<<<<<< HEAD
        lay.addWidget(unit_box)
=======
        lay.addWidget(box_theme)
>>>>>>> 1d31a183728543d2b62dfc4f59c31b2af9b6380e
        lay.addWidget(box)
        lay.addWidget(self.tip)
        lay.addStretch(1)

        # 信号
        self.combo_unit.currentIndexChanged.connect(self._on_unit_changed)
        self.spin_max_points.valueChanged.connect(config.set_max_points)
        self.spin_send_interval.valueChanged.connect(config.set_send_interval_ms)
        self.chk_show_x_axis.toggled.connect(config.set_show_x_axis)

<<<<<<< HEAD
    def _on_unit_changed(self, index: int) -> None:
        """单位切换：写设置并通知主窗口换算各面板。"""
        unit = self.combo_unit.itemData(index)
        config.set_unit(unit)
        self.unit_changed.emit(unit)
=======
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        theme.on_change(self._apply_theme)

    def _on_theme_changed(self, index: int) -> None:
        """界面主题切换：持久化并立即应用。"""
        mode = self.combo_theme.itemData(index)
        config.set_theme_mode(mode)
        theme.set_mode(mode)

    def _apply_theme(self) -> None:
        """主题切换：刷新本页用到主题配色的控件。"""
        self.tip.setStyleSheet(f"color:{theme.colors()['hint']};")
>>>>>>> 1d31a183728543d2b62dfc4f59c31b2af9b6380e
