"""Entry point: ``uv run dashboard-client`` (or ``uv run python -m dashboard_client``).

Env vars (see config.py): SHELL_URL (the shell on the LAN), LATITUDE/LONGITUDE
(the always-on local weather station), LOG_LEVEL/LOG_JSON.

Ctrl-C (SIGINT) and SIGTERM quit cleanly — Qt otherwise swallows SIGINT.
"""
from __future__ import annotations

import logging
import os
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .log import configure_logging
from .theme import QSS
from .ui import MainWindow


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = QApplication(sys.argv)
    app.setApplicationName("desk-dashboard")
    app.setStyleSheet(QSS)

    # Let SIGINT/SIGTERM quit the Qt event loop (it blocks Python signal handlers,
    # so a 250ms no-op timer gives the interpreter a chance to run them).
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    wakeup = QTimer(app)
    wakeup.timeout.connect(lambda: None)
    wakeup.start(250)

    win = MainWindow()
    win.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
