"""VESC 射击机构 UART 遥控器（Python / PySide6）。"""
# 把主题管理器单例实例绑定为包属性：`from remote_control import theme`
# 得到的是 ThemeManager 实例（而非子模块），可直接 theme.attach(...)。
from .theme import theme
