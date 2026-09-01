"""入口。用法：python main.py"""
import sys

from PySide6.QtWidgets import QApplication

from remote_control import config, theme
from remote_control.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    theme.attach(app)                    # 绑定应用 + 监听系统配色变化
    theme.set_mode(config.get_theme_mode())  # 应用持久化的界面主题
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
