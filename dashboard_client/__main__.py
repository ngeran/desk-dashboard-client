"""Entry point: ``uv run dashboard-client`` (or ``python -m dashboard_client``).

Env vars (see config.py): SHELL_URL (the shell on the LAN), LATITUDE/LONGITUDE
(the always-on local weather station), LOG_JSON.
"""
from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from .log import configure_logging
from .theme import QSS
from .ui import MainWindow


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger("websockets").setLevel(logging.WARNING)
    app = QApplication(sys.argv)
    app.setApplicationName("desk-dashboard")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
