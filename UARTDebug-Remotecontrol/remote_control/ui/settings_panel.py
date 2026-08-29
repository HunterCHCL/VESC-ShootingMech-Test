"""设置页：集中管理上位机可调参数。

当前包含「数据监测」分组：
    - 曲线内存点数：数据监听页曲线每通道保留的最大采样数，
      曲线左右拖动可查看的历史范围不超过该值，超出自动丢弃（GC）。
    - 信息发送周期：MCU 状态帧发送周期（ms），决定 X 轴每采样点对应时间。
    - 显示 X 轴：是否显示曲线底部的相对时间轴刻度与竖向网格。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout,
)

from .. import config


class SettingsPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

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

        tip = QLabel(
            "数据监听页曲线操作：左键拖动左右平移时间轴、上下平移数值，\n"
            "滚轮缩放 Y 轴，Ctrl+滚轮缩放 X 轴，双击复位并跟随最新数据。")
        tip.setStyleSheet("color:#888;")
        tip.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addWidget(box)
        lay.addWidget(tip)
        lay.addStretch(1)

        self.spin_max_points.valueChanged.connect(config.set_max_points)
        self.spin_send_interval.valueChanged.connect(config.set_send_interval_ms)
        self.chk_show_x_axis.toggled.connect(config.set_show_x_axis)
