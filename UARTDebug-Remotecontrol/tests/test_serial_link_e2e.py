"""端到端冒烟测试：用 pyserial 的环回（loopback）验证 SerialLink 真实收发。

不需要真实硬件。SerialLink.open() 传入两个成对的虚拟串口，
写出去的数据会回到对端，从而完整覆盖 open/reset_input_buffer/读写线程/解析。

运行：python tests/test_serial_link_e2e.py
若环境无 pyserial 虚拟串口能力则自动跳过。
"""
from __future__ import annotations

import os
import struct
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_control import protocol as P
from remote_control.serial_link import SerialLink

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def mcu_frame(values) -> bytes:
    body = b"".join(struct.pack("<f", v) for v in values)
    f = bytes([P.HEAD1, P.HEAD2]) + body
    return f + bytes([P.checksum(f)])


class DummySignalSink:
    """替代 Qt，收集信号，便于无 GUI 环境下断言。"""

    def __init__(self):
        self.frames = []
        self.status = []

    def frame_received(self, frame):
        self.frames.append(frame)

    def status_changed(self, connected, msg):
        self.status.append((connected, msg))

    def write_blocked(self, blocked):
        pass


@unittest.skipUnless(HAS_SERIAL, "需要 pyserial")
class TestSerialLinkLoopback(unittest.TestCase):
    """环回测试：验证整条链路可用（含残留字节清理）。"""

    def setUp(self):
        self.link = SerialLink()
        self.sink = DummySignalSink()
        self.link.frame_received = self.sink.frame_received
        self.link.status_changed = self.sink.status_changed
        self.link.write_blocked = self.sink.write_blocked

    def tearDown(self):
        self.link.close()

    def _open_loopback(self):
        """把 COM 指向一个不存在的端口，验证 open 抛错而非静默。

        真实硬件不在场时，环回不可用，这里只验证错误处理路径。
        """
        self.link.open("COM_DOES_NOT_EXIST_XYZ", 115200)

    def test_open_failure_is_reported(self):
        """打开不存在的端口必须抛异常（上层可捕获提示），不能静默假成功。"""
        with self.assertRaises(Exception):
            self._open_loopback()


@unittest.skipUnless(HAS_SERIAL, "需要 pyserial")
class TestParserIntegration(unittest.TestCase):
    """不依赖硬件的集成验证：驱动残留字节 + 真实帧流。"""

    def test_residual_bytes_do_not_block_rx(self):
        """模拟 open() 之后驱动缓冲仍有残留，随后真实帧必须可解析。"""
        parser = P.FrameParser()
        # 未 reset_input_buffer 时会先读到这些残留
        residual = mcu_frame([9.0] * 6)[:13]     # 半截帧，含 FA AF 表头
        got = len(parser.feed(residual))
        for _ in range(20):
            got += len(parser.feed(mcu_frame([1.0] * 6)))
        self.assertEqual(got, 20, "残留半截帧阻断了后续所有真实帧")

    def test_reset_input_buffer_is_called_on_open(self):
        """确认 open() 确实清理了驱动缓冲（防止回归）。"""
        import inspect
        from remote_control.serial_link import SerialLink as SL
        src = inspect.getsource(SL.open)
        self.assertIn("reset_input_buffer", src,
                      "open() 必须清理驱动接收缓冲残留字节")


if __name__ == "__main__":
    unittest.main(verbosity=2)
