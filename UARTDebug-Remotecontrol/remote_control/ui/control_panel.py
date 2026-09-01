"""控制面板：六路 VESC 目标 erpm 设置 + 发送控制（持续发送 / 单次发送 / 急停）。

布局按 2 组 × 3 轮分组：
    每组三行电机，每行 = 启用勾选 + 名称 + 目标 erpm + 实测 erpm；
    每组尾部有「3轮同步」勾选框（默认勾选，整组目标保持一致）。

发送语义：
    - targets() 对「未启用」的电机返回 0（不转），已启用的返回 spinbox 值。
    - 持续发送周期可调；MCU 看门狗 1s，不持续发送则目标 1s 后自动清零。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)

from .. import config, theme

VESC_NAMES = ["V1/R1", "V2/R2", "V3/R3", "V4/F1", "V5/F2", "V6/F3"]
GROUP_INFO = [  # (组内电机下标, 组名)
    ((0, 1, 2), "第 1 组 (V1/R1 · V2/R2 · V3/R3)"),
    ((3, 4, 5), "第 2 组 (V4/F1 · V5/F2 · V6/F3)"),
]

ERPM_MIN = -200000
ERPM_MAX = 200000


class ControlPanel(QFrame):
    emergency_stop = Signal()          # 全部急停
    send_once_requested = Signal()     # 发送一次
    continuous_toggled = Signal(bool)  # 持续发送开/关

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        # ---------------- 发送控制条 ----------------
        self.chk_continuous = QCheckBox("持续发送")
        self.chk_continuous.setToolTip(
            "按设定周期持续发送目标 erpm。MCU 看门狗 1s：不持续发送则\n"
            "目标 1s 后自动清零，电机停转。")
        self.spin_period = QSpinBox()
        self.spin_period.setRange(50, 1000)
        self.spin_period.setSingleStep(50)
        self.spin_period.setSuffix(" ms")
        self.spin_period.setValue(config.get_period())
        self.btn_send_once = QPushButton("发送一次")
        self.btn_estop = QPushButton("全部急停")
        self.btn_estop.setStyleSheet(
            "QPushButton{background:#c0392b;color:white;font-weight:bold;"
            "min-height:28px;} QPushButton:pressed{background:#922b21;}")

        ctrl = QHBoxLayout()
        ctrl.addWidget(self.chk_continuous)
        ctrl.addWidget(QLabel("周期:"))
        ctrl.addWidget(self.spin_period)
        ctrl.addWidget(self.btn_send_once)
        ctrl.addStretch(1)
        ctrl.addWidget(self.btn_estop)

        # ---------------- 六路目标 ----------------
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(6)

        self._head_label = QLabel("启用")
        self._head_label.setStyleSheet(
            f"color:{theme.colors()['text_secondary']};")
        grid.addWidget(self._head_label, 0, 0)
        grid.addWidget(QLabel("电机"), 0, 1)
        grid.addWidget(QLabel("目标 erpm"), 0, 2)
        grid.addWidget(QLabel("实测 erpm"), 0, 3)

        self._targets: list[QDoubleSpinBox] = []
        self._enabled: list[QCheckBox] = []
        self._readouts: list[QLabel] = []
        self._group_sync_chk: list[QCheckBox] = []
        self._forward_only: list[QCheckBox] = []
        self._wheel_steps: list[QSpinBox] = []
        self._group_titles: list[QLabel] = []

        defaults_en = config.get_enabled()
        defaults_tg = config.get_targets()

        # 分组设置（滚轮步进 / 仅限正向 / 3轮同步）——持久化恢复
        _wheel_cfg = list(config.get_group_wheel_steps())
        _fwd_cfg = list(config.get_group_forward_only())
        _sync_cfg = list(config.get_group_sync())
        _n_groups = len(GROUP_INFO)
        while len(_wheel_cfg) < _n_groups:
            _wheel_cfg.append(500)
        while len(_fwd_cfg) < _n_groups:
            _fwd_cfg.append(True)
        while len(_sync_cfg) < _n_groups:
            _sync_cfg.append(True)
        self._loading = True  # 构造期间不触发持久化保存

        row = 1
        for group_idx, (indices, group_name) in enumerate(GROUP_INFO):
            ttl = QLabel(group_name)
            ttl.setStyleSheet(
                "font-weight:bold;"
                f"color:{theme.colors()['text_secondary']};")
            grid.addWidget(ttl, row, 0, 1, 4)
            self._group_titles.append(ttl)
            row += 1

            for idx in indices:
                chk = QCheckBox()
                chk.setChecked(defaults_en[idx])
                chk.setToolTip(
                    f"是否把 VESC{idx + 1} 目标包含在发送帧中；\n"
                    "未启用时该电机按 0 发送（不转）")
                spin = QDoubleSpinBox()
                spin.setRange(ERPM_MIN, ERPM_MAX)
                spin.setDecimals(0)
                spin.setSingleStep(500)
                spin.setValue(defaults_tg[idx])
                spin.setMinimumWidth(130)
                spin.valueChanged.connect(
                    lambda _v, g=group_idx, i=idx:
                    self._on_motor_changed(g, i))
                rd = QLabel("—")
                rd.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                rd.setMinimumWidth(100)
                rd.setStyleSheet("font-weight:bold;font-family:Consolas;")
                grid.addWidget(chk, row, 0)
                grid.addWidget(QLabel(VESC_NAMES[idx]), row, 1)
                grid.addWidget(spin, row, 2)
                grid.addWidget(rd, row, 3)
                self._enabled.append(chk)
                self._targets.append(spin)
                self._readouts.append(rd)
                row += 1

            # 滚轮步进 + 仅限正向 + 3轮同步（前两者位于 3轮同步 左侧）
            wstep = QSpinBox()
            wstep.setRange(1, 100000)
            wstep.setValue(_wheel_cfg[group_idx])
            wstep.setSuffix(" rpm")
            wstep.setToolTip("滚轮每格调整的目标 erpm 步进值。")
            wstep.valueChanged.connect(
                lambda v, g=group_idx: self._on_wheel_step_changed(v, g))
            # 恢复持久化的滚轮步进：立即应用到该组目标 spinbox 的单步值，
            # 否则打开软件后未调整滚轮步进时，滚轮仍按硬编码 500 步进。
            for idx in GROUP_INFO[group_idx][0]:
                self._targets[idx].setSingleStep(wstep.value())

            fwd = QCheckBox("仅限正向")
            fwd.setToolTip(
                "勾选后滚轮（及手动输入）不会把目标调成负数，最低为 0；\n"
                "取消勾选后允许负值。")
            fwd.toggled.connect(
                lambda on, g=group_idx: self._on_forward_only_toggled(on, g))
            fwd.setChecked(_fwd_cfg[group_idx])  # -> 触发 toggled，按配置钳下限

            # 3 轮同步勾选（默认勾选）：改任意一路，整组跟随
            sync = QCheckBox("3轮同步")
            sync.setToolTip(
                "勾选后同组 3 路目标保持一致：改任意一路，其余两路自动跟随；\n"
                "取消勾选后各轮可独立调节。")
            sync.toggled.connect(
                lambda on, g=group_idx, m=indices[0]:
                self._on_group_sync_toggled(on, g, m))
            sync.setChecked(_sync_cfg[group_idx])  # -> 触发 toggled，整组对齐首轮值
            sync_row = QHBoxLayout()
            sync_row.addWidget(QLabel("滚轮步进:"))
            sync_row.addWidget(wstep)
            sync_row.addWidget(fwd)
            sync_row.addStretch(1)
            sync_row.addWidget(sync)
            grid.addLayout(sync_row, row, 0, 1, 4)
            self._group_sync_chk.append(sync)
            self._forward_only.append(fwd)
            self._wheel_steps.append(wstep)
            row += 1

        # 便捷按钮
        self.btn_all_on = QPushButton("全部启用")
        self.btn_all_off = QPushButton("全部禁用")
        self.btn_all_zero = QPushButton("全部归零")
        self.btn_all_zero.setToolTip("把所有目标 erpm 置 0（不自动发送）")
        quick = QHBoxLayout()
        quick.addWidget(self.btn_all_on)
        quick.addWidget(self.btn_all_off)
        quick.addWidget(self.btn_all_zero)
        quick.addStretch(1)

        self._note_label = QLabel(
            "提示：MCU 看门狗 1s，未持续发送时目标 1s 后自动清零；"
            "「全部急停」会清空目标并发送全 0。")
        self._note_label.setStyleSheet(
            f"color:{theme.colors()['hint']};")
        self._note_label.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(ctrl)
        lay.addLayout(grid)
        lay.addLayout(quick)
        lay.addStretch(1)
        lay.addWidget(self._note_label)

        # ---------------- 信号 ----------------
        self.chk_continuous.toggled.connect(self.continuous_toggled)
        self.btn_send_once.clicked.connect(self.send_once_requested)
        self.btn_estop.clicked.connect(self.emergency_stop)
        self.btn_all_on.clicked.connect(lambda: self._set_all_enabled(True))
        self.btn_all_off.clicked.connect(lambda: self._set_all_enabled(False))
        self.btn_all_zero.clicked.connect(self._set_all_zero)
        self.spin_period.valueChanged.connect(config.set_period)

        self._loading = False  # 构造完成，后续改动会持久化
        theme.on_change(self._apply_theme)

    # ---------------- 内部操作 ----------------
    def _on_motor_changed(self, group_idx: int, changed_idx: int) -> None:
        """任一路目标变化：若该组「3轮同步」勾选则整组跟随该路。"""
        if self._group_sync_chk[group_idx].isChecked():
            self._apply_group_sync(group_idx, changed_idx)

    def _on_group_sync_toggled(self, on: bool, group_idx: int, master_idx: int) -> None:
        """勾选「3轮同步」时立即按组首轮对齐整组。"""
        if on:
            self._apply_group_sync(group_idx, master_idx)
        if not self._loading:
            self._save_group_settings()

    def _apply_group_sync(self, group_idx: int, master_idx: int) -> None:
        v = self._targets[master_idx].value()
        for idx in GROUP_INFO[group_idx][0]:
            if idx != master_idx:
                self._targets[idx].setValue(v)

    def _on_forward_only_toggled(self, on: bool, group_idx: int) -> None:
        """仅限正向：勾选时该组 spinbox 下限钳到 0，滚轮/输入不可为负。"""
        for idx in GROUP_INFO[group_idx][0]:
            self._targets[idx].setMinimum(0 if on else ERPM_MIN)
        if not self._loading:
            self._save_group_settings()

    def _on_wheel_step_changed(self, step: int, group_idx: int) -> None:
        """滚轮步进：更新该组 spinbox 的滚轮单步值。"""
        for idx in GROUP_INFO[group_idx][0]:
            self._targets[idx].setSingleStep(step)
        if not self._loading:
            self._save_group_settings()

    def _save_group_settings(self) -> None:
        """把各组滚轮步进 / 仅限正向 / 3轮同步写入 settings.json。"""
        config.set_group_wheel_steps([s.value() for s in self._wheel_steps])
        config.set_group_forward_only(
            [c.isChecked() for c in self._forward_only])
        config.set_group_sync([c.isChecked() for c in self._group_sync_chk])

    def _apply_theme(self) -> None:
        """主题切换：刷新表头 / 组标题 / 提示文字配色。"""
        c = theme.colors()
        self._head_label.setStyleSheet(f"color:{c['text_secondary']};")
        for ttl in self._group_titles:
            ttl.setStyleSheet(
                "font-weight:bold;"
                f"color:{c['text_secondary']};")
        self._note_label.setStyleSheet(f"color:{c['hint']};")

    def _set_all_enabled(self, on: bool) -> None:
        for chk in self._enabled:
            chk.setChecked(on)

    def _set_all_zero(self) -> None:
        for spin in self._targets:
            spin.setValue(0.0)

    # ---------------- 取值 ----------------
    def targets(self) -> list[float]:
        """实际要发送的目标：未启用的电机按 0 发送。"""
        return [s.value() if c.isChecked() else 0.0
                for s, c in zip(self._targets, self._enabled)]

    def raw_targets(self) -> list[float]:
        """spinbox 原始值（不管是否启用），用于保存/恢复。"""
        return [s.value() for s in self._targets]

    def enabled(self) -> list[bool]:
        return [c.isChecked() for c in self._enabled]

    def period(self) -> int:
        return self.spin_period.value()

    def continuous(self) -> bool:
        return self.chk_continuous.isChecked()

    def set_continuous(self, on: bool) -> None:
        self.chk_continuous.setChecked(on)

    def reset_targets(self) -> None:
        """全部目标置 0（不自动发送）。"""
        self._set_all_zero()

    def set_readouts(self, erpm: list) -> None:
        """刷新 6 路实测 erpm 显示；None 显示「—」（当前固件第 6 路可能损坏）。"""
        for lbl, v in zip(self._readouts, erpm):
            if v is None:
                lbl.setText("—")
                lbl.setStyleSheet(
                    "font-weight:bold;font-family:Consolas;color:#e74c3c;")
            else:
                lbl.setText(f"{v:.0f}")
                lbl.setStyleSheet(
                    "font-weight:bold;font-family:Consolas;color:#2ecc71;")
