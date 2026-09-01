"""集中设置持久化：统一保存到项目根目录的 settings.json。

所有应用设置都存进这一个 JSON 文件（脚本运行时在项目根目录，打包 exe 后在
exe 同级目录），用户可直接查看 / 手动修改 / 备份 / 迁移。

文件结构（可扩展：未来新增设置只需在 DEFAULTS 里加键，无需改存储逻辑）：

    {
      "window":  { "x", "y", "w", "h", "maximized" },  # 主窗口位置/大小/最大化
      "serial":  { "last_port", "baud" },               # 遥控串口
      "control": { "period", "wheel_step[2]", "forward_only[2]", "sync[2]" },
      "vesc":    { "targets": [6], "enabled": [6] },    # 六路目标 erpm 与启用
      "plot":    { "max_points", "send_interval_ms", "show_x_axis",
                    "top_splitter_sizes", "main_splitter_sizes" }
    }
"""
from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any


def default_file() -> str:
    """settings.json 路径：脚本运行时 = 项目根目录；打包 exe 时 = exe 同级目录。"""
    if getattr(sys, "frozen", False):  # PyInstaller 单文件打包
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "settings.json")


# 默认设置（与各面板初始值保持一致）
DEFAULTS: dict[str, dict] = {
    "window": {"x": None, "y": None, "w": 980, "h": 760, "maximized": False},
    "serial": {"last_port": "", "baud": 115200},
    "appearance": {"theme": "system"},  # 界面主题：白天/黑夜/跟随系统
    "control": {"period": 200,
                "wheel_step": [500, 500],
                "forward_only": [True, True],
                "sync": [True, True]},
    "vesc": {"targets": [0.0] * 6, "enabled": [True] * 6},
    "plot": {"max_points": 100000, "send_interval_ms": 100,
             "show_x_axis": True,
             "top_splitter_sizes": [210, 700],
             "main_splitter_sizes": [420, 200]},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并：override 里的字典与 base 同名字典逐键合并，其它直接覆盖。"""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class AppSettings:
    """内存中维护一份设置，读写根目录 settings.json。

    set() 更新内存并立即落盘（文件很小，代价可忽略）；set_no_save() 只更新内存
    不落盘（用于拖动过程中频繁变化的数值，如目标 erpm），由调用方择机 save()。
    写盘采用「临时文件 + 原子替换」，避免中途异常导致文件损坏。
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path or default_file()
        self._data: dict = {}
        self._lock = threading.Lock()
        self.load()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> None:
        """从磁盘读取；文件不存在 / 损坏时回退到默认值。"""
        loaded: dict = {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, ValueError):
            loaded = {}
        if not isinstance(loaded, dict):
            loaded = {}
        with self._lock:
            self._data = _deep_merge(DEFAULTS, loaded)

    def save(self) -> None:
        """把当前内存设置写盘（原子替换）。"""
        with self._lock:
            data = dict(self._data)
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    # ---------- 通用取值/设值 ----------
    def get(self, section: str, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """更新某段某键并立即落盘（值未变则跳过）。"""
        with self._lock:
            cur = self._data.setdefault(section, {})
            if cur.get(key) == value:
                return
            cur[key] = value
        self.save()

    def set_no_save(self, section: str, key: str, value: Any) -> None:
        """只更新内存不落盘，由调用方后续统一 save()。"""
        with self._lock:
            self._data.setdefault(section, {})[key] = value

    def section(self, section: str) -> dict:
        """返回某段的浅拷贝（用于读取整段，如窗口几何）。"""
        with self._lock:
            return dict(self._data.get(section, {}))


# 模块级单例：config.py / 各面板共用这一份内存数据。
app_settings = AppSettings()
