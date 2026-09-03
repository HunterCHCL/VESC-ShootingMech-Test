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


# ---- 显示单位（ERPM / RPM）：7 ERPM = 1 RPM ----
# 仅影响 UI 显示；发送与接收的数据始终为 ERPM（通信协议不变）。
ERPM_PER_RPM = 7


def get_unit() -> str:
    """当前显示单位：'erpm' 或 'rpm'。"""
    u = str(app_settings.get("display", "unit", "erpm")).lower()
    return "rpm" if u == "rpm" else "erpm"


def set_unit(unit: str) -> None:
    """设置显示单位（只接受 'erpm' / 'rpm'，其它回退 erpm）。"""
    unit = "rpm" if str(unit).lower() == "rpm" else "erpm"
    app_settings.set("display", "unit", unit)


def is_rpm_display() -> bool:
    """当前是否以 RPM 显示。"""
    return get_unit() == "rpm"


def to_display(erpm: float, unit: str | None = None) -> float:
    """ERPM → 显示单位：RPM 模式下除以 ERPM_PER_RPM，否则原值返回。

    unit 缺省时读当前设置；传参时按给定单位换算（用于单位切换过程）。
    """
    if (unit or get_unit()) == "rpm":
        return erpm / ERPM_PER_RPM
    return erpm


def from_display(value: float, unit: str | None = None) -> float:
    """显示单位 → ERPM：RPM 模式下乘以 ERPM_PER_RPM，否则原值返回。"""
    if (unit or get_unit()) == "rpm":
        return value * ERPM_PER_RPM
    return value


def get_period() -> int:
    """持续发送周期（ms）。"""
    return int(app_settings.get("control", "period", 200))


def set_period(ms: int) -> None:
    app_settings.set("control", "period", ms)


# ---- 控制页分组设置（滚轮步进 / 仅限正向 / 3轮同步） ----
def get_group_wheel_steps() -> list[int]:
    """各组滚轮步进值（QSpinBox）。"""
    return [int(x) for x in app_settings.get("control", "wheel_step", [500, 500])]


def set_group_wheel_steps(values: list[int]) -> None:
    app_settings.set("control", "wheel_step", [int(x) for x in values])


def get_group_forward_only() -> list[bool]:
    """各组「仅限正向」勾选状态。"""
    return [bool(x) for x in app_settings.get("control", "forward_only", [True, True])]


def set_group_forward_only(values: list[bool]) -> None:
    app_settings.set("control", "forward_only", [bool(x) for x in values])


def get_group_sync() -> list[bool]:
    """各组「3轮同步」勾选状态。"""
    return [bool(x) for x in app_settings.get("control", "sync", [True, True])]


def set_group_sync(values: list[bool]) -> None:
    app_settings.set("control", "sync", [bool(x) for x in values])


# ---- 数据监听页布局（分隔条尺寸；拖动中只写内存，关闭时统一落盘） ----
def get_top_splitter_sizes() -> list[int]:
    return [int(x) for x in app_settings.get("plot", "top_splitter_sizes", [210, 700])]


def set_top_splitter_sizes(values: list[int]) -> None:
    app_settings.set_no_save("plot", "top_splitter_sizes", [int(x) for x in values])


def get_main_splitter_sizes() -> list[int]:
    return [int(x) for x in app_settings.get("plot", "main_splitter_sizes", [420, 200])]


def set_main_splitter_sizes(values: list[int]) -> None:
    app_settings.set_no_save("plot", "main_splitter_sizes", [int(x) for x in values])


def get_targets() -> list[float]:
    """六路目标 erpm（规范存储单位，与当前显示单位无关）。"""
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
