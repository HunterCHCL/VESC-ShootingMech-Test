"""帧解析器回归测试：验证"能发送但收不到帧"这一类故障已被修复。

重点覆盖曾经导致解析永久卡死的场景：
  - 打开串口瞬间的残留半截帧（驱动缓冲未清理）
  - 线路噪声导致的随机位翻转
  - 帧头残留在缓冲区却始终校验不过

运行：python -m pytest tests/ -v
或：  python tests/test_protocol.py
"""
from __future__ import annotations

import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_control import protocol as P


def mcu_frame(values) -> bytes:
    """按固件 UARTDebug_SendFrame 规则构造状态帧：FA AF + 24B 数据 + 1B 校验。"""
    body = b"".join(struct.pack("<f", v) for v in values)
    frame = bytes([P.HEAD1, P.HEAD2]) + body
    return frame + bytes([P.checksum(frame)])


def feed_all(parser, stream: bytes, chunk: int = 64) -> int:
    """按 chunk 分批喂入（模拟 read(256) 分片），返回解析出的帧数。"""
    got = 0
    for i in range(0, len(stream), chunk):
        got += len(parser.feed(stream[i:i + chunk]))
    return got


class TestFrameBasics(unittest.TestCase):
    """基本编解码正确性（防止修复引入回归）。"""

    def test_frame_length_and_checksum(self):
        f = mcu_frame([1.0, 2, 3, 4, 5, 6])
        self.assertEqual(len(f), 27)
        self.assertEqual(P.checksum(f[:-1]), f[-1])

    def test_clean_stream(self):
        stream = b"".join(mcu_frame([float(i)] * 6) for i in range(1, 100))
        p = P.FrameParser()
        self.assertEqual(feed_all(p, stream), 99)
        self.assertLessEqual(len(p._buf), P.FRAME_MAX_LEN)

    def test_values_round_trip(self):
        vals = [1000.5, -2000.25, 0.0, 12345.678, -0.5, 99999.0]
        p = P.FrameParser()
        frames = p.feed(mcu_frame(vals))
        self.assertEqual(len(frames), 1)
        for got, want in zip(frames[0]["erpm"], vals):
            self.assertAlmostEqual(got, want, places=3)

    def test_byte_by_byte_delivery(self):
        """最恶劣的分片：一次只喂 1 字节，也必须能拼出完整帧。"""
        f = mcu_frame([1.0, 2, 3, 4, 5, 6])
        p = P.FrameParser()
        got = sum(len(p.feed(bytes([b]))) for b in f)
        self.assertEqual(got, 1)


class TestResyncAfterCorruption(unittest.TestCase):
    """核心回归：坏数据之后必须能重新同步，绝不永久卡死。"""

    def _stream(self, n=99):
        return b"".join(mcu_frame([float(i)] * 6) for i in range(1, n + 1))

    def test_stale_partial_frame_at_open(self):
        """开串口瞬间驱动缓冲里的残留半截帧（真实故障场景）。

        修复前：解析 0 帧且永久卡死。
        """
        stale = bytes([P.HEAD1, P.HEAD2, 0x01, 0x02, 0x03, 0x04, 0x05])
        p = P.FrameParser()
        got = feed_all(p, stale + self._stream())
        self.assertEqual(got, 99, "残留半截帧导致后续帧全部无法解析")
        self.assertLessEqual(len(p._buf), P.FRAME_MAX_LEN)

    def test_false_header_never_sticks(self):
        """伪帧头 + 后续全是合法帧：必须恢复。"""
        p = P.FrameParser()
        got = feed_all(p, bytes([P.HEAD1, P.HEAD2, 0xDE, 0xAD]) + self._stream())
        self.assertEqual(got, 99)

    def test_random_garbage_prefix_and_suffix(self):
        random.seed(7)
        junk = bytes(random.randrange(256) for _ in range(50))
        p = P.FrameParser()
        self.assertEqual(feed_all(p, junk + self._stream() + junk), 99)

    def test_bit_flips_do_not_kill_parser(self):
        """1~6 bit 随机翻转后，绝大部分帧仍应被正确解析。"""
        random.seed(42)
        stream = self._stream()
        ok = 0
        trials = 100
        for _ in range(trials):
            s = bytearray(stream)
            for _ in range(random.randint(1, 6)):
                s[random.randrange(len(s))] ^= 1 << random.randrange(8)
            p = P.FrameParser()
            if feed_all(p, bytes(s)) >= 80:
                ok += 1
        # 修复前该指标约 5%；修复后应接近 100%
        self.assertGreater(ok, trials * 0.9,
                           f"仅 {ok}/{trials} 次恢复，解析器仍不够健壮")

    def test_buffer_does_not_grow_without_bound(self):
        """长时间运行不得内存泄漏。"""
        p = P.FrameParser()
        feed_all(p, bytes([P.HEAD1, P.HEAD2, 0x01]))
        for _ in range(2000):
            feed_all(p, mcu_frame([1.0, 2, 3, 4, 5, 6]), chunk=27)
        self.assertLessEqual(len(p._buf), P.FrameParser._MAX_BUF)

    def test_buffer_cap_kicks_in(self):
        """同步完全失效（持续垃圾流）时，上限兜底生效。"""
        p = P.FrameParser()
        p.feed(b"\x00" * (P.FrameParser._MAX_BUF * 2))
        self.assertLessEqual(len(p._buf), P.FrameParser._MAX_BUF)


class TestLongRun(unittest.TestCase):
    """模拟长时间连续接收，确认不会逐渐失效。"""

    def test_one_hour_of_frames(self):
        p = P.FrameParser()
        total = 0
        for _ in range(3600):        # 36000 帧 ≈ 1 小时 @100ms
            total += len(p.feed(mcu_frame([100.0, 200, 300, 400, 500, 600])))
        self.assertEqual(total, 3600)
        self.assertLessEqual(len(p._buf), P.FrameParser._MAX_BUF)


if __name__ == "__main__":
    unittest.main(verbosity=2)
