"""GUI 冒烟测试（离屏）：确认新增的无数据自检定时器与端口提示不崩溃。

使用 QT_QPA_PLATFORM=offscreen，无需真实显示器。
运行：python tests/test_main_window_smoke.py
"""
from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "需要 PySide6")
class TestMainWindowSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from remote_control.main_window import MainWindow
        self.win = MainWindow()
        self.win._refresh_ports()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.app.processEvents()

    def test_rx_check_timer_configured(self):
        """无数据自检定时器应已配置且处于停止态。"""
        self.assertIsNotNone(self.win._rx_check)
        self.assertEqual(self.win._rx_check.interval(), 1000)
        self.assertFalse(self.win._rx_check.isActive(),
                         "未打开串口时不应运行自检")

    def test_rx_baseline_initialised(self):
        self.assertEqual(self.win._rx_at_open, self.win._rx)

    def test_check_no_rx_is_safe_when_closed(self):
        """未连接时调用自检不得抛异常。"""
        self.win._check_no_rx()
        self.assertFalse(self.win.link.is_open)

    def test_check_no_rx_prompts_when_stale(self):
        """已连接但无数据时应给出明确提示（这是本次要解决的迷惑点）。"""
        self.win.link._ser = _FakeSerial()   # 假装已连接
        try:
            self.win._rx_at_open = self.win._rx
            self.win._check_no_rx()
            self.assertIn("收不到数据", self.win.lbl_status.text())
        finally:
            self.win.link._ser = None

    def test_check_no_rx_quiet_when_data_flows(self):
        """有数据回传时不得打扰用户。"""
        self.win.link._ser = _FakeSerial()
        try:
            self.win._rx_at_open = 0
            self.win._rx = 5
            self.win._check_no_rx()
            self.assertNotIn("收不到数据", self.win.lbl_status.text())
        finally:
            self.win.link._ser = None

    def test_restore_port_warns_when_missing(self):
        """上次的串口不存在时应提示，而不是静默选中别的设备。"""
        from remote_control import config
        old = config.get_last_port()
        missing = "COM_NOT_PRESENT_ZZZ"
        config.set_last_port(missing)
        try:
            self.win._restore_port()
            # 仅当该端口确实不在本机列表中，才要求出现提示
            if self.win.combo_port.findText(missing) < 0:
                self.assertIn("不存在", self.win.lbl_status.text())
            # 无论是否存在，都不能静默把下拉框切成别的串口
            self.assertNotEqual(self.win.combo_port.currentText(), missing)
        finally:
            config.set_last_port(old)


class _FakeSerial:
    """最小 Serial 替身，仅供 is_open 判定。"""
    is_open = True

    def close(self):
        self.is_open = False


if __name__ == "__main__":
    unittest.main(verbosity=2)
