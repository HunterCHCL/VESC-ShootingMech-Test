"""通信协议：帧编解码（与固件 UserLib/UARTDebug 的 UARTDebug.c/.h 完全一致）。

帧格式（双向，数值均为 float32 小端）：
    [0xFA][0xAF][cmd][payload...][checksum]
    checksum = (除最后一个字节外所有字节之和) & 0xFF
    （固件用 uint8_t 累加，等价于取低 8 位）

命令码（PC -> MCU）：
    0x01  UARTDEBUG_CMD_VESC_UPDATE
        payload = 6 × float32 = vesc1..vesc6 的目标 erpm
        完整帧：2 头 + 1 cmd + 24 数据 + 1 校验 = 28 字节

MCU -> PC 状态帧（UARTDebug_SendVESCStatus，每 100ms 发送一次）：
    [0xFA][0xAF][6 × float32 erpm][checksum]   —— 注意：不含命令字节

⚠ 固件 off-by-one 说明（仅影响 MCU -> PC 方向）：
    固件 UARTDebug_SendFrame 用 UARTDebug_SendData(frame, len + 2) 发送，
    校验和字节会覆盖最后一个 payload 字节（即第 6 个浮点的最高字节）。
    因此当前固件实际发出的状态帧是 [0xFA][0xAF][23 字节][checksum] = 26 字节，
    其中第 6 路 erpm 数据损坏、不可信。
    本解析器同时支持 26 字节（当前固件）与 27 字节（修复后）两种帧，靠校验和
    自动判别；收到 26 字节帧时第 6 路解析结果为 None（显示「—」）。
    建议固件修复：把发送改为 UARTDebug_SendData(frame, len + 3)，
    并把校验和放在 frame[len + 2] 位置（循环 i < len + 2）。
"""
from __future__ import annotations

import struct

HEAD1 = 0xFA
HEAD2 = 0xAF

CMD_VESC_UPDATE = 0x01

NUM_VESC = 6
FRAME_MAX_LEN = 64  # 与固件 UARTDebug_FRAME_MAX_LEN 一致

# 状态帧候选总长（2 头 + 数据 + 1 校验）：
#   26 = 当前固件（23 数据字节，第 6 路损坏）
#   27 = 修复后固件（24 数据字节，6 路完整）
#   28 = 含命令字节的帧（2 头 + 1 cmd + 24 数据 + 1 校验）
_STATUS_LEN_CURRENT = 26
_STATUS_LEN_FIXED = 27
_CMD_LEN = 28


def checksum(data: bytes) -> int:
    """校验和：所有字节相加，取低 8 位（与固件 uint8_t 累加一致）。"""
    return sum(data) & 0xFF


def pack_vesc_update(targets: list[float]) -> bytes:
    """PC -> MCU：0x01 更新 6 路 VESC 目标 erpm。"""
    assert len(targets) == NUM_VESC, f"需要 {NUM_VESC} 路目标"
    payload = struct.pack(f"<{NUM_VESC}f", *targets)
    body = bytes([CMD_VESC_UPDATE]) + payload
    frame = bytes([HEAD1, HEAD2]) + body
    return frame + bytes([checksum(frame)])


def parse_erpm(payload: bytes) -> list[float | None]:
    """把 payload 按 4 字节一组解析为 float；不足 24 字节时后续为 None。"""
    out: list[float | None] = []
    for i in range(NUM_VESC):
        seg = payload[i * 4 : i * 4 + 4]
        if len(seg) == 4:
            out.append(struct.unpack("<f", seg)[0])
        else:
            out.append(None)
    return out


def parse_status(frame: bytes) -> dict:
    """解析 MCU -> PC 状态帧。

    返回 {'type': 'status', 'erpm': [6 个 float | None]}。
    26 字节帧（当前固件）下第 6 路为 None。
    """
    total = len(frame)
    if total in (_STATUS_LEN_CURRENT, _STATUS_LEN_FIXED):
        payload = frame[2:-1]
    else:  # _CMD_LEN：跳过命令字节
        payload = frame[3:-1]
    return {"type": "status", "erpm": parse_erpm(payload)}


class FrameParser:
    """串口字节流 -> 完整帧。自动查找帧头、校验并丢弃坏帧。"""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        """喂入原始字节，返回解析出的帧列表（可能为空）。"""
        self._buf += data
        frames: list[dict] = []
        while True:
            frame = self._try_extract()
            if frame is None:
                break
            frames.append(frame)
        return frames

    def _try_extract(self) -> dict | None:
        # 找帧头
        while len(self._buf) >= 2:
            if self._buf[0] == HEAD1 and self._buf[1] == HEAD2:
                break
            self._buf.pop(0)
        if len(self._buf) < 3:
            return None
        # 按候选长度逐个校验，选通过的那个（短的先试，兼容当前固件 26 字节帧）
        for total in (_STATUS_LEN_CURRENT, _STATUS_LEN_FIXED, _CMD_LEN):
            if len(self._buf) < total:
                continue
            frame = bytes(self._buf[:total])
            if checksum(frame[:-1]) != frame[-1]:
                continue
            del self._buf[:total]
            return parse_status(frame)
        return None
