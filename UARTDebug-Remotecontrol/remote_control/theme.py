"""外观主题：白天 / 黑夜 / 跟随系统。

实现方式：两套主题统一使用 Qt 内置 Fusion 风格，仅通过 QPalette 换色——
Fusion 完全响应调色板，因此白天/黑夜控件几何与布局完全一致，且无需
自定义全局 QSS。应用内用 QPainter / setStyleSheet 自定义绘制的配色
（曲线、图例、读数、标题、提示文字等）由 theme.colors() 提供。

用法：
    from . import theme
    theme.attach(app)                          # 启动时绑定（app 创建后）
    theme.set_mode(config.get_theme_mode())    # 应用持久化的主题
    自定义控件在构造时读取 theme.colors() 配色，并注册
    theme.on_change(self._apply_theme) 以便切换主题时刷新。

注：theme 只依赖 Qt，不依赖本工程其它模块，避免循环导入。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# 设置模式（settings.json 中 appearance.theme 的取值）
MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"
MODES = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)
MODE_LABELS = {MODE_SYSTEM: "跟随系统", MODE_LIGHT: "白天", MODE_DARK: "黑夜"}

# 每套主题的配色：Fusion 风格 + QPalette 的取色来源；
# 自定义绘制键取值与原工程硬编码一致。
_PALETTES: dict[str, dict[str, str]] = {
    # 白天：浅色配色。控件几何与黑夜完全一致（同一 Fusion 风格）。
    MODE_LIGHT: {
        # 调色板基础（浅色）
        "window_bg": "#f0f0f0",
        "panel_bg": "#fafafa",
        "text": "#1f1f1f",
        "text_secondary": "#bbbbbb",     # 表头 / 组标题（原 color:#bbb）
        "text_disabled": "#a0a0a0",
        "border": "#c5c5c5",
        "input_bg": "#ffffff",
        "button_bg": "#e8e8e8",
        "button_hover": "#dcdcdc",
        "button_pressed": "#cfcfcf",
        "button_disabled": "#f0f0f0",
        "accent": "#4a6fa5",             # 高亮 / 分隔条悬停（原 #4a6fa5）
        "splitter": "#c8c8c8",           # 分隔条：白天用略暗的白色，与浅背景区分
        "scrollbar": "#b0b0b0",
        "tooltip_bg": "#ffffe1",
        "tooltip_text": "#1f1f1f",
        # 自定义绘制（曲线 / 图例 / 读数 / 提示，与原硬编码一致）
        "hint": "#888888",
        "readout_val": "#1f1f1f",        # 读数：白天为深色，避免融入浅背景
        "plot_bg": "#1e1e1e",
        "plot_grid": "#2d2d2d",
        "plot_zero": "#4a4a4a",
        "plot_axis": "#8a8a8a",
        "legend_hl_bg": "#233140",
        "legend_hl_border": "#3498db",
        "legend_name": "#dddddd",
        "legend_hidden_name": "#555555",
        "legend_swatch_hidden": "#444444",
    },
    MODE_DARK: {
        "window_bg": "#232323",
        "panel_bg": "#2b2b2b",
        "text": "#e6e6e6",
        "text_secondary": "#c8c8c8",
        "text_disabled": "#6a6a6a",
        "border": "#4a4a4a",
        "input_bg": "#383838",
        "button_bg": "#3c3c3c",
        "button_hover": "#4a4a4a",
        "button_pressed": "#303030",
        "button_disabled": "#2e2e2e",
        "accent": "#3d9be9",
        "splitter": "#3a3a3a",
        "scrollbar": "#555555",
        "tooltip_bg": "#3c3c3c",
        "tooltip_text": "#e6e6e6",
        "plot_bg": "#1e1e1e",
        "plot_grid": "#2d2d2d",
        "plot_zero": "#4a4a4a",
        "plot_axis": "#8a8a8a",
        "legend_hl_bg": "#233140",
        "legend_hl_border": "#3498db",
        "legend_name": "#e0e0e0",
        "legend_hidden_name": "#555555",
        "legend_swatch_hidden": "#444444",
        "readout_val": "#ecf0f1",
        "hint": "#888888",
    },
}


def _build_palette(p: dict) -> QPalette:
    """根据配色构建调色板（Fusion 完全响应 QPalette）。"""
    def c(key: str) -> QColor:
        return QColor(p[key])

    pal = QPalette()
    # 窗口 / 文字
    pal.setColor(QPalette.Window, c("window_bg"))
    pal.setColor(QPalette.WindowText, c("text"))
    pal.setColor(QPalette.Base, c("input_bg"))
    pal.setColor(QPalette.AlternateBase, c("panel_bg"))
    pal.setColor(QPalette.Text, c("text"))
    pal.setColor(QPalette.PlaceholderText, c("text_disabled"))
    # 按钮
    pal.setColor(QPalette.Button, c("button_bg"))
    pal.setColor(QPalette.ButtonText, c("text"))
    # 高亮 / 选中
    pal.setColor(QPalette.Highlight, c("accent"))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    # 边框 / 立体感（Fusion 用 Light/Midlight/Mid/Dark/Shadow）
    pal.setColor(QPalette.Light, c("button_hover"))
    pal.setColor(QPalette.Midlight, c("button_hover"))
    pal.setColor(QPalette.Mid, c("button_pressed"))
    pal.setColor(QPalette.Dark, c("border"))
    pal.setColor(QPalette.Shadow, c("border"))
    # 提示 / 链接（滚动条由 style 用 Button/Window 等角色绘制）
    pal.setColor(QPalette.ToolTipBase, c("tooltip_bg"))
    pal.setColor(QPalette.ToolTipText, c("tooltip_text"))
    pal.setColor(QPalette.Link, c("accent"))
    pal.setColor(QPalette.LinkVisited, c("accent"))
    # 禁用状态
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        pal.setColor(QPalette.Disabled, role, c("text_disabled"))
    pal.setColor(QPalette.Disabled, QPalette.Highlight, c("text_disabled"))
    pal.setColor(QPalette.Disabled, QPalette.HighlightedText, c("text_disabled"))
    return pal


def is_system_dark() -> bool:
    """当前系统是否处于深色外观（跟随系统用）。"""
    try:
        return QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except (AttributeError, TypeError):
        return False


def resolve(mode: str) -> str:
    """把设置模式解析为实际生效主题：system 按系统颜色决定 light/dark。"""
    if mode == MODE_DARK:
        return MODE_DARK
    if mode == MODE_LIGHT:
        return MODE_LIGHT
    return MODE_DARK if is_system_dark() else MODE_LIGHT


class ThemeManager(QObject):
    """全局主题管理器（单例）：Fusion 风格 + QPalette 换色。

    - attach(app)：启动时绑定 QApplication，统一设置 Fusion 风格并监听系统配色变化；
    - set_mode(mode)：切换主题（light/dark/system），立即生效并刷新注册控件；
    - on_change(fn)：注册切换主题时被调用的刷新回调（无参）。
    """

    # 模式常量同时暴露在实例上（`from remote_control import theme` 得到实例）
    MODES = MODES
    MODE_LABELS = MODE_LABELS

    changed = Signal(str)  # 实际生效主题：light / dark

    def __init__(self) -> None:
        super().__init__()
        self._app: QApplication | None = None
        self._mode = MODE_SYSTEM
        self._current = MODE_LIGHT   # 当前实际生效主题（colors() 取值）
        self._applied: str | None = None
        self._callbacks: list[Callable[[], None]] = []

    # ---------- 绑定 ----------
    def attach(self, app: QApplication) -> None:
        """绑定应用实例（幂等）；统一 Fusion 风格 + 注册系统配色变化监听。"""
        if self._app is not None:
            return
        self._app = app
        # 统一使用 Qt 内置 Fusion 风格：完全响应 QPalette，深色主题才能生效，
        # 且白天/黑夜控件几何一致（同一风格）。
        app.setStyle("Fusion")
        try:
            app.styleHints().colorSchemeChanged.connect(self._on_system_changed)
        except (AttributeError, TypeError):
            pass

    # ---------- 查询 ----------
    def mode(self) -> str:
        return self._mode

    def current(self) -> str:
        return self._current

    def colors(self) -> dict:
        """当前实际生效主题的配色表（浅拷贝，供 UI 读取）。"""
        return dict(_PALETTES[self._current])

    # ---------- 切换 ----------
    def set_mode(self, mode: str) -> None:
        mode = mode if mode in MODES else MODE_SYSTEM
        self._mode = mode
        self._apply()

    def _on_system_changed(self, *_args) -> None:
        if self._mode == MODE_SYSTEM:
            self._apply()

    def _apply(self) -> None:
        if self._app is None:
            return
        resolved = resolve(self._mode)
        if resolved == self._applied:
            return
        self._current = resolved
        self._applied = resolved
        # 白天 / 黑夜共用同一 Fusion 风格，仅通过 QPalette 换色，几何完全一致。
        self._app.setPalette(_build_palette(_PALETTES[resolved]))
        for fn in list(self._callbacks):
            try:
                fn()
            except Exception:
                pass
        self.changed.emit(resolved)

    # ---------- 刷新回调 ----------
    def on_change(self, fn: Callable[[], None]) -> None:
        """注册主题切换时的刷新回调（幂等）。"""
        if callable(fn) and fn not in self._callbacks:
            self._callbacks.append(fn)


# 模块级单例：各面板 / 入口共用。
theme = ThemeManager()
