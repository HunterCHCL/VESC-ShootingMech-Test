"""入口。用法：python main.py"""
import sys

from PySide6.QtWidgets import QApplication

from remote_control.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
