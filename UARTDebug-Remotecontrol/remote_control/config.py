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


def save() -> None:
    app_settings.save()
