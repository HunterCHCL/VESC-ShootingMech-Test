"""控制面板：六路 VESC 目标 erpm 设置 + 发送控制（持续发送 / 单次发送 / 急停）。

布局按 3 级轮对（L1/R1、L2/R2、L3/R3）分组：
    每级两行电机（L、R），每行 = 启用勾选 + 名称 + 目标 erpm + 实测 erpm；
    每级尾部有「R 反向」「同步 L→R」快速按键。

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

from .. import config

VESC_NAMES = ["V1/L1", "V2/R1", "V3/L2", "V4/R2", "V5/L3", "V6/R3"]
PAIR_INFO = [  # (L 下标, R 下标, 对名)
    (0, 1, "第 1 级 (L1/R1)"),
    (2, 3, "第 2 级 (L2/R2)"),
    (4, 5, "第 3 级 (L3/R3)"),
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

        head = QLabel("启用")
        head.setStyleSheet("color:#bbb;")
        grid.addWidget(head, 0, 0)
        grid.addWidget(QLabel("电机"), 0, 1)
        grid.addWidget(QLabel("目标 erpm"), 0, 2)
        grid.addWidget(QLabel("实测 erpm"), 0, 3)

        self._targets: list[QDoubleSpinBox] = []
        self._enabled: list[QCheckBox] = []
        self._readouts: list[QLabel] = []
        self._rev_chk: list[QCheckBox] = []
        self._sync_chk: list[QCheckBox] = []

        defaults_en = config.get_enabled()
        defaults_tg = config.get_targets()

        row = 1
        for pair_idx, (li, ri, pair_name) in enumerate(PAIR_INFO):
            ttl = QLabel(pair_name)
            ttl.setStyleSheet("font-weight:bold;color:#bbb;")
            grid.addWidget(ttl, row, 0, 1, 4)
            row += 1

            for idx in (li, ri):
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

            # 每级同步勾选：勾选后 R 目标自动跟随 L（配合「R 反向」取反）
            rev = QCheckBox("R 反向")
            sync = QCheckBox("同步 L→R")
            sync.setToolTip(
                "勾选后 R 目标自动跟随 L 电机（改 L 即同步到 R）；\n"
                "勾选「R 反向」则取相反数（适合左右轮对转）。\n"
                "取消勾选后 R 可独立调节。")
            sync.toggled.connect(
                lambda on, a=li, b=ri, p=pair_idx:
                self._on_sync_toggled(on, a, b, p))
            self._targets[li].valueChanged.connect(
                lambda _v, a=li, b=ri, p=pair_idx:
                self._on_l_changed(a, b, p))
            sync_row = QHBoxLayout()
            sync_row.addStretch(1)
            sync_row.addWidget(rev)
            sync_row.addWidget(sync)
            grid.addLayout(sync_row, row, 0, 1, 4)
            self._rev_chk.append(rev)
            self._sync_chk.append(sync)
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

        note = QLabel(
            "提示：MCU 看门狗 1s，未持续发送时目标 1s 后自动清零；"
            "「全部急停」会清空目标并发送全 0。")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(ctrl)
        lay.addLayout(grid)
        lay.addLayout(quick)
        lay.addStretch(1)
        lay.addWidget(note)

        # ---------------- 信号 ----------------
        self.chk_continuous.toggled.connect(self.continuous_toggled)
        self.btn_send_once.clicked.connect(self.send_once_requested)
        self.btn_estop.clicked.connect(self.emergency_stop)
        self.btn_all_on.clicked.connect(lambda: self._set_all_enabled(True))
        self.btn_all_off.clicked.connect(lambda: self._set_all_enabled(False))
        self.btn_all_zero.clicked.connect(self._set_all_zero)
        self.spin_period.valueChanged.connect(config.set_period)

    # ---------------- 内部操作 ----------------
    def _on_sync_toggled(self, on: bool, li: int, ri: int, pair_idx: int) -> None:
        """勾选「同步 L→R」时立即把 R 同步到 L 当前值。"""
        if on:
            self._apply_sync(li, ri, pair_idx)

    def _on_l_changed(self, li: int, ri: int, pair_idx: int) -> None:
        """L 目标变化时，若该对处于同步状态则自动更新 R。"""
        if self._sync_chk[pair_idx].isChecked():
            self._apply_sync(li, ri, pair_idx)

    def _apply_sync(self, li: int, ri: int, pair_idx: int) -> None:
        v = self._targets[li].value()
        if self._rev_chk[pair_idx].isChecked():
            v = -v
        self._targets[ri].setValue(v)

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
