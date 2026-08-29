"""设置持久化接口：串口 / 窗口 / 六路 VESC 目标与启用。

统一保存到项目根目录的 settings.json（见 app_settings.py）。
"""
from __future__ import annotations

from .app_settings import app_settings


def get_last_port() -> str:
    return str(app_settings.get("serial", "last_port", ""))


def set_last_port(port: str) -> None:
    if port:
        app_settings.set("serial", "last_port", port)


def get_baud() -> int:
    return int(app_settings.get("serial", "baud", 115200))


def set_baud(baud: int) -> None:
    app_settings.set("serial", "baud", baud)


def get_period() -> int:
    """持续发送周期（ms）。"""
    return int(app_settings.get("control", "period", 200))


def set_period(ms: int) -> None:
    app_settings.set("control", "period", ms)


def get_targets() -> list[float]:
    """六路目标 erpm（原始 spinbox 值）。"""
    return [float(x) for x in app_settings.get("vesc", "targets", [0.0] * 6)]


def set_targets(values: list[float]) -> None:
    app_settings.set_no_save("vesc", "targets", [float(x) for x in values])


def get_enabled() -> list[bool]:
    """六路启用状态。"""
    return [bool(x) for x in app_settings.get("vesc", "enabled", [True] * 6)]


def set_enabled(values: list[bool]) -> None:
    app_settings.set_no_save("vesc", "enabled", [bool(x) for x in values])


def get_max_points() -> int:
    """数据监测曲线内存点数（每通道保留的最大采样数，超出自动 GC）。"""
    return int(app_settings.get("plot", "max_points", 100000))


def set_max_points(n: int) -> None:
    app_settings.set("plot", "max_points", int(n))


def get_send_interval_ms() -> int:
    """MCU 信息（状态帧）发送周期，单位 ms；决定 X 轴每采样点对应时间。"""
    return int(app_settings.get("plot", "send_interval_ms", 100))


def set_send_interval_ms(ms: int) -> None:
    app_settings.set("plot", "send_interval_ms", int(ms))


def get_show_x_axis() -> bool:
    """是否在曲线底部显示 X 轴（相对时间刻度与竖向网格）。"""
    return bool(app_settings.get("plot", "show_x_axis", True))


def set_show_x_axis(on: bool) -> None:
    app_settings.set("plot", "show_x_axis", bool(on))


def save() -> None:
    app_settings.save()
