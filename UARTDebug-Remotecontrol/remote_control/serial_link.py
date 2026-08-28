"""串口链路：打开/关闭/枚举/重连 + 后台读线程 + 帧解析 + 后台写线程。

- 读：后台读线程，帧解析后发 frame_received 信号。
- 写：后台写线程 + 合并队列。相同 cmd 的旧帧只保留最新一帧（遥控/定时重复
  发送时丢弃过期数据，对方收到的永远是最新值）；不同 cmd 的帧按序保留。
  写超时（设备未及时读取）不报错断开，只发 write_blocked 提示并继续重试。
  GUI 线程永不参与串口 I/O，因此永不阻塞。

信号均可从读/写线程中触发（PySide6 信号线程安全）。
"""
from __future__ import annotations

import threading

import serial
from serial.tools import list_ports
from PySide6.QtCore import QObject, Signal

from . import protocol


def available_ports() -> list[str]:
    return [p.device for p in list_ports.comports()]


class SerialLink(QObject):
    """封装 pyserial：串口帧流 <-> Qt 信号。"""

    frame_received = Signal(dict)      # 解析出的帧（见 protocol.parse_status）
    status_changed = Signal(bool, str)  # 连接状态, 说明
    write_blocked = Signal(bool)       # True=写入受阻(设备未读取), False=恢复

    _WRITE_TIMEOUT = 0.5        # 单次写超时上限（秒），防止后台线程卡死
    _WRITE_MAX_QUEUE = 128      # 发送队列上限，防止异常堆积

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ser: serial.Serial | None = None
        self._read_thread: threading.Thread | None = None
        self._write_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._parser = protocol.FrameParser()
        self._queue: list[bytes] = []
        self._qcv = threading.Condition()   # 保护 _queue
        self._write_fails = 0
        self._blocked_emitted = False

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def open(self, port: str, baud: int) -> None:
        self.close()
        self._parser = protocol.FrameParser()
        self._stop.clear()
        self._write_fails = 0
        self._blocked_emitted = False
        # write_timeout 必须有：否则设备不读取时写会一直阻塞。阻塞发生在
        # 后台写线程，GUI 永不卡死。
        self._ser = serial.Serial(port=port, baudrate=baud,
                                  timeout=0.2, write_timeout=self._WRITE_TIMEOUT)
        rt = threading.Thread(target=self._read_loop, daemon=True)
        wt = threading.Thread(target=self._write_loop, daemon=True)
        self._read_thread = rt
        self._write_thread = wt
        rt.start()
        wt.start()
        # 若开串口瞬间读线程已报错并 close 过，则不重复上报"已连接"
        if not self._stop.is_set():
            self.status_changed.emit(True, f"已连接 {port} @ {baud}")

    def close(self, reason: str = "已断开") -> None:
        """关闭串口；仅当确实曾打开时才发断开信号，避免重复/误报。"""
        self._stop.set()
        with self._qcv:
            self._qcv.notify_all()
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        cur = threading.current_thread()
        for t in (self._read_thread, self._write_thread):
            if t is not None and t is not cur:
                try:
                    t.join(timeout=1.0)
                except RuntimeError:
                    pass  # 线程尚未 start()（读线程先行报错的并发竞态）
        self._read_thread = None
        self._write_thread = None
        if ser is not None:
            self.status_changed.emit(False, reason)

    # ---------------- 发送（入队，绝不阻塞 GUI）----------------
    def send(self, frame: bytes) -> bool:
        with self._qcv:
            if self._ser is None or not self._ser.is_open:
                return False
            try:
                cmd = frame[2]  # 本协议 cmd 字节在索引 2
            except IndexError:
                cmd = None
            # 同 cmd 只留最新（定时重复发送）；不同 cmd 按序排队
            if self._queue and self._queue[-1][2] == cmd:
                self._queue[-1] = frame
            else:
                self._queue.append(frame)
                if len(self._queue) > self._WRITE_MAX_QUEUE:
                    self._queue.pop(0)
            self._qcv.notify()
        return True

    def _write_loop(self) -> None:
        ser = self._ser
        while not self._stop.is_set() and ser is not None:
            with self._qcv:
                while not self._queue and not self._stop.is_set():
                    self._qcv.wait()
                if self._stop.is_set():
                    break
                frame = self._queue.pop(0)
                congested = self._write_fails > 0
            try:
                if congested:
                    # 之前有超时积压：先清空旧帧，保证最新帧尽快上
                    try:
                        ser.reset_output_buffer()
                    except Exception:
                        pass
                ser.write(frame)
                self._on_write_ok()
            except serial.SerialTimeoutException:
                # 设备未及时读取：不报错断开，只提示，并用最新数据持续重试
                self._on_write_timeout()
            except Exception as exc:
                if not self._stop.is_set():
                    self._on_lost(str(exc))
                return

    def _on_write_ok(self) -> None:
        self._write_fails = 0
        if self._blocked_emitted:
            self._blocked_emitted = False
            self.write_blocked.emit(False)

    def _on_write_timeout(self) -> None:
        self._write_fails += 1
        if not self._blocked_emitted:
            self._blocked_emitted = True
            self.write_blocked.emit(True)

    def _read_loop(self) -> None:
        ser = self._ser
        while not self._stop.is_set() and ser is not None:
            try:
                data = ser.read(256)
            except Exception as exc:  # 拔出/占用等
                if not self._stop.is_set():
                    self._on_lost(str(exc))
                return
            if not data:
                continue
            for frame in self._parser.feed(data):
                self.frame_received.emit(frame)

    def _on_lost(self, reason: str) -> None:
        self.close(reason=f"已断开：{reason}")
