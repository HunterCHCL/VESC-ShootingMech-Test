"""主窗口：串口条 + 控制页 + 监听页，装配所有面板与信号。"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from . import config, protocol
from .app_settings import app_settings
from .serial_link import SerialLink, available_ports
from .ui.control_panel import ControlPanel
from .ui.monitor_panel import MonitorPanel
from .ui.settings_panel import SettingsPanel

BAUDS = ["115200", "9600", "19200", "38400", "57600",
         "230400", "460800", "921600"]
_EDITABLE = (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VESC 射击机构 UART 遥控")
        self.resize(980, 760)
        self._restore_window_geometry()

        # 链路
        self.link = SerialLink(self)
        self._tx = 0
        self._rx = 0
        self._rx_at_open = 0       # 打开串口时的 RX 计数（无数据自检的基准）
        self._conn_msg = "未连接"

        # 持续发送定时器
        self.send_timer = QTimer(self)
        self.send_timer.timeout.connect(self._send_targets)

        # 无数据自检定时器：打开串口后若迟迟收不到任何帧，说明链路实际不通
        # （选错设备 / 波特率不符 / MCU 未上电），主动提示而非静默显示"已连接"
        self._rx_check = QTimer(self)
        self._rx_check.setInterval(1000)
        self._rx_check.timeout.connect(self._check_no_rx)

        # 面板
        self.control = ControlPanel()
        self.monitor = MonitorPanel()
        self.settings = SettingsPanel()
        self._build_serial_bar()

        # 控制页
        control_tab = QWidget()
        cv = QVBoxLayout(control_tab)
        cv.addLayout(self._serial_bar)
        cv.addWidget(self.control, 1)

        # 监听页
        monitor_tab = QWidget()
        mv = QVBoxLayout(monitor_tab)
        mv.addWidget(self.monitor, 1)

        # 设置页
        settings_tab = QWidget()
        sv = QVBoxLayout(settings_tab)
        sv.addWidget(self.settings, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(control_tab, "控制")
        self.tabs.addTab(monitor_tab, "数据监听")
        self.tabs.addTab(settings_tab, "设置")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        # 设置 -> 曲线联动
        self.settings.spin_max_points.valueChanged.connect(
            self.monitor.plot.set_max_points)
        self.settings.spin_send_interval.valueChanged.connect(
            self.monitor.plot.set_sample_interval)
        self.settings.chk_show_x_axis.toggled.connect(
            self.monitor.plot.set_show_x_axis)

        # 信号
        self.link.frame_received.connect(self._on_frame)
        self.link.status_changed.connect(self._on_link_status)
        self.link.write_blocked.connect(self._on_write_blocked)
        self.control.emergency_stop.connect(self._emergency_stop)
        self.control.send_once_requested.connect(self._send_once)
        self.control.continuous_toggled.connect(self._on_continuous)
        QApplication.instance().installEventFilter(self)

        self._restore_port()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    # ---------- 窗口几何（settings.json） ----------
    def _restore_window_geometry(self) -> None:
        win = app_settings.section("window")
        x, y = win.get("x"), win.get("y")
        if x is not None and y is not None:
            self.move(int(x), int(y))
        self.resize(int(win.get("w", 980)), int(win.get("h", 760)))
        if win.get("maximized"):
            self.showMaximized()

    def _save_window_geometry(self) -> None:
        if not self.isMaximized():
            geo = self.geometry()
            app_settings.set("window", "x", geo.x())
            app_settings.set("window", "y", geo.y())
            app_settings.set("window", "w", geo.width())
            app_settings.set("window", "h", geo.height())
        app_settings.set("window", "maximized", self.isMaximized())

    # ---------- 串口条 ----------
    def _build_serial_bar(self) -> None:
        self.combo_port = QComboBox()
        self.combo_port.setMinimumWidth(120)
        self.btn_ports = QPushButton("刷新")
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(BAUDS)
        self.combo_baud.setCurrentText(str(config.get_baud()))
        self.btn_open = QPushButton("打开")
        self.btn_reconnect = QPushButton("重连")
        self.btn_reconnect.setEnabled(False)
        self.lbl_status = QLabel("未连接")
        self.lbl_status.setStyleSheet("color:#e74c3c;font-weight:bold;")
        self.lbl_rxtx = QLabel("TX 0  RX 0")

        self._serial_bar = QHBoxLayout()
        self._serial_bar.addWidget(QLabel("串口:"))
        self._serial_bar.addWidget(self.combo_port)
        self._serial_bar.addWidget(self.btn_ports)
        self._serial_bar.addWidget(QLabel("波特率:"))
        self._serial_bar.addWidget(self.combo_baud)
        self._serial_bar.addWidget(self.btn_open)
        self._serial_bar.addWidget(self.btn_reconnect)
        self._serial_bar.addStretch(1)
        self._serial_bar.addWidget(self.lbl_status)
        self._serial_bar.addWidget(self.lbl_rxtx)

        self.btn_ports.clicked.connect(self._refresh_ports)
        self.btn_open.clicked.connect(self._toggle_open)
        self.btn_reconnect.clicked.connect(self._reconnect)

    def _refresh_ports(self) -> None:
        current = self.combo_port.currentText()
        self.combo_port.clear()
        self.combo_port.addItems(available_ports() or ["(无串口)"])
        if current:
            idx = self.combo_port.findText(current)
            if idx >= 0:
                self.combo_port.setCurrentIndex(idx)

    def _restore_port(self) -> None:
        self._refresh_ports()
        last = config.get_last_port()
        if not last:
            return
        idx = self.combo_port.findText(last)
        if idx >= 0:
            self.combo_port.setCurrentIndex(idx)
        else:
            # 上次的串口在当前机器上不存在：COM 号会随 USB 端口/机器变化。
            # 此处不静默改选其它端口（可能连到别的设备），而是明确提示用户
            # 手动确认，避免"连上了却收发不对"。
            self.lbl_status.setText(
                f"上次使用的 {last} 在本机不存在，请确认串口")
            self.lbl_status.setStyleSheet(
                "color:#e67e22;font-weight:bold;")

    def _port(self) -> str:
        return self.combo_port.currentText()

    def _toggle_open(self) -> None:
        if self.link.is_open:
            self.link.close()
        else:
            self._open(self._port())

    def _reconnect(self) -> None:
        port = config.get_last_port() or self._port()
        self._open(port)

    def _open(self, port: str) -> None:
        if not port or port.startswith("("):
            self.lbl_status.setText("请选择串口")
            return
        self._rx_at_open = self._rx      # 记录打开时的接收计数，作为自检基准
        self._rx_check.start()
        self.link.open(port, int(self.combo_baud.currentText()))
        config.set_last_port(port)
        config.set_baud(int(self.combo_baud.currentText()))

    def _check_no_rx(self) -> None:
        """已连接但长时间收不到任何帧时给出明确提示。

        MCU 每 100ms 回传一帧，正常情况下 1 秒内必有数据。持续无数据说明
        链路实际不通——最常见原因是选错了串口（COM 号因机器而异）或波特率
        不匹配。此时不报错（串口确实打开了），但必须让用户看见。
        """
        if not self.link.is_open:
            return
        if self._rx != self._rx_at_open:
            return                  # 有数据回来，不再需要提示
        self.lbl_status.setText(
            f"⚠ 已打开 {self._port()} 但收不到数据："
            "请确认设备已上电、串口选对、波特率一致")
        self.lbl_status.setStyleSheet("color:#e67e22;font-weight:bold;")

    def _on_link_status(self, connected: bool, msg: str) -> None:
        self._conn_msg = msg
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet(
            "color:#2ecc71;font-weight:bold;" if connected
            else "color:#e74c3c;font-weight:bold;")
        self.btn_open.setText("关闭" if connected else "打开")
        self.btn_reconnect.setEnabled(not connected)
        self._refresh_ports()
        if not connected:
            # 断开：停止持续发送，MCU 看门狗 1s 后自动清零目标
            self.send_timer.stop()
            self._rx_check.stop()
            self.control.set_continuous(False)

    def _on_write_blocked(self, blocked: bool) -> None:
        """发送受阻提示（非致命）：不改变连接/按钮状态，只更新状态栏。"""
        if blocked:
            self.lbl_status.setText(
                "⚠ 发送受阻：设备未及时读取，已改为只发送最新数据")
            self.lbl_status.setStyleSheet("color:#e67e22;font-weight:bold;")
        else:
            self.lbl_status.setText(getattr(self, "_conn_msg", "已连接"))
            self.lbl_status.setStyleSheet("color:#2ecc71;font-weight:bold;")

    # ---------- 发送 ----------
    def _on_continuous(self, on: bool) -> None:
        if on:
            self.send_timer.setInterval(self.control.period())
            self.send_timer.start()
            self._send_targets()  # 立即发一次
        else:
            self.send_timer.stop()

    def _send_targets(self) -> None:
        if not self.link.is_open:
            return
        self._try_send(protocol.pack_vesc_update(self.control.targets()))

    def _send_once(self) -> None:
        if not self.link.is_open:
            self._flash("未连接，无法发送")
            return
        self._send_targets()
        self._flash("已发送一次")

    def _emergency_stop(self) -> None:
        """急停：停止持续发送、清空目标、发送全 0。"""
        self.send_timer.stop()
        self.control.set_continuous(False)
        self.control.reset_targets()
        if self.link.is_open:
            self._try_send(protocol.pack_vesc_update([0.0] * protocol.NUM_VESC))
            self._flash("急停：已发送全 0 目标")
        else:
            self._flash("急停：未连接，MCU 看门狗将自动清零")

    # ---------- 收包 ----------
    def _on_frame(self, frame: dict) -> None:
        self._update_rxtx(tx=False)
        if frame.get("type") == "status":
            erpm = frame.get("erpm") or []
            self.control.set_readouts(erpm)
            self.monitor.update_erpm(erpm)
            # 同步设定转速参考线（虚线）
            self.monitor.set_targets(self.control.raw_targets())

    # ---------- 工具 ----------
    def _try_send(self, frame: bytes) -> None:
        if self.link.send(frame):
            self._update_rxtx(tx=True)

    def _update_rxtx(self, tx: bool) -> None:
        if tx:
            self._tx += 1
        else:
            self._rx += 1
        self.lbl_rxtx.setText(f"TX {self._tx}  RX {self._rx}")

    def _flash(self, msg: str) -> None:
        self.lbl_status.setText(msg)

    # ---------- 键盘（Esc 急停） ----------
    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            if self._esc_active():
                self._emergency_stop()
                return True  # 消费按键，避免误触发其它控件
        return super().eventFilter(obj, event)

    def _esc_active(self) -> bool:
        """仅在「控制」页、且不在输入框内编辑时生效。"""
        if self.tabs.currentIndex() != 0:
            return False
        if isinstance(QApplication.focusWidget(), _EDITABLE):
            return False
        return True

    def _on_tab_changed(self, index: int) -> None:
        pass  # 保留钩子（与参考工程结构一致）

    # ---------- 关闭 ----------
    def _save_state(self) -> None:
        config.set_targets(self.control.raw_targets())
        config.set_enabled(self.control.enabled())
        config.set_period(self.control.period())
        config.save()

    def closeEvent(self, event) -> None:
        self._emergency_stop()
        self.link.close()
        self._save_state()
        self._save_window_geometry()
        super().closeEvent(event)
