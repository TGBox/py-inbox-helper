"""py-inbox-helper entry point."""
from __future__ import annotations

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from py_inbox_helper.ui.main_window import MainWindow


def main() -> None:
    """Launches the PyInboxHelper GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("py-inbox-helper")
    app.setOrganizationName("py-inbox-helper")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
