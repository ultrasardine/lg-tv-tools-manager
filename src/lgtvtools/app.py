from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication

from .system.logging_config import setup_logging
from .system.paths import data_dir
from .ui.main_window import MainWindow


def main() -> int:
    setup_logging()
    data_dir().mkdir(parents=True, exist_ok=True)
    logging.getLogger(__name__).info("Starting LG TV Tools")
    app = QApplication(sys.argv)
    window = MainWindow()
    app.aboutToQuit.connect(window.share_server.close)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
