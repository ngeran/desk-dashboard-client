"""The Qt interface — three fastfetch-style panels across the strip.

Clock (local, dot-matrix font), Weather (local Open-Meteo) and Calendar (a local
month grid with today highlighted) — all three render with no backend, so the
screen is never blank.

Layout = one row of three equal panels, sized for a wide strip (e.g. 1920×480);
hero fonts scale to the screen. Thread model: Qt loop on the main thread; a
background asyncio thread fetches weather and consumes the shell's WS stream,
pushing data in via Qt signals (thread-safe, queued to the main thread).
"""
from __future__ import annotations

import asyncio
import calendar
import os
import threading
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from . import shell_client, weather
from .config import LATITUDE, LONGITUDE, PALETTE, SHELL_URL, WEATHER_REFRESH_SECONDS
from .renderers.formatting import weather_text

_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")


def _clear(layout: QVBoxLayout) -> None:
    """Delete every child widget/layout of ``layout`` (for repopulation)."""
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget() or item.layout()
        if child is None:
            continue
        if isinstance(child, QVBoxLayout):
            _clear(child)
        else:
            child.deleteLater()


def _bar(accent: str, width: int | None = None) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setTextVisible(False)
    bar.setFixedHeight(4)
    bar.setStyleSheet(
        f"QProgressBar{{background:#161616;border:none;border-radius:2px}}"
        f"QProgressBar::chunk{{background:{accent};border-radius:2px}}"
    )
    if width is not None:
        bar.setFixedWidth(width)
    return bar


class Panel(QFrame):
    """Bordered card: header (accent square + title + LIVE/OFFLINE badge) + body."""

    def __init__(self, title: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("panel")
        self._accent = accent
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(9)
        square = QFrame()
        square.setFixedSize(12, 12)
        square.setStyleSheet(f"background:{accent};border-radius:2px;")
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        header.addWidget(square)
        header.addWidget(title_label)
        header.addStretch()
        self.badge = QLabel("")
        self.badge.setObjectName("panelBadge")
        header.addWidget(self.badge)
        self.set_live(False)
        outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 6, 0, 0)
        self.body.setSpacing(6)
        outer.addLayout(self.body)

    def set_live(self, live: bool) -> None:
        self.badge.setText("● LIVE" if live else "○ OFFLINE")
        self.badge.setStyleSheet(f"color:{self._accent if live else '#5a5f68'};")


class ClockPanel(Panel):
    def __init__(self) -> None:
        super().__init__("CLOCK", PALETTE["blue"])
        self.set_live(True)
        self.time = QLabel("")
        self.time.setObjectName("clockBig")
        self.time.setAlignment(Qt.AlignCenter)
        self.date = QLabel("")
        self.date.setObjectName("date")
        self.date.setAlignment(Qt.AlignCenter)
        self.day_bar = _bar(PALETTE["blue"])
        self.day_label = QLabel("")
        self.day_label.setObjectName("k")
        self.body.addStretch()
        self.body.addWidget(self.time)
        self.body.addWidget(self.date)
        self.body.addStretch()
        day_row = QHBoxLayout()
        day_row.setSpacing(12)
        day_row.addWidget(self.day_label)
        day_row.addWidget(self.day_bar, 1)
        self.body.addLayout(day_row)
        self.tick()

    def tick(self) -> None:
        now = datetime.now()
        self.time.setText(now.strftime("%H:%M"))
        self.date.setText(now.strftime("%A %e %B"))
        secs = now.hour * 3600 + now.minute * 60 + now.second
        pct = int(secs / 86400 * 100)
        self.day_bar.setValue(pct)
        self.day_label.setText(f"DAY {pct}%")


class WeatherPanel(Panel):
    def __init__(self) -> None:
        super().__init__("WEATHER", PALETTE["green"])
        self.temp = QLabel("—")
        self.temp.setObjectName("clockBig")
        self.temp.setAlignment(Qt.AlignCenter)
        self.icon = QLabel("·")
        self.icon.setObjectName("weatherIcon")
        self.icon.setAlignment(Qt.AlignCenter)
        self.cond = QLabel("")
        self.cond.setObjectName("v")
        self.cond.setAlignment(Qt.AlignCenter)
        self.feels_v = QLabel("—")
        self.feels_v.setObjectName("v")
        self.wind_v = QLabel("—")
        self.wind_v.setObjectName("v")
        self.hum_bar = _bar(PALETTE["green"])
        self.hum_label = QLabel("")
        self.hum_label.setObjectName("k")

        # big temp + big icon side by side, condition text beneath
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addStretch()
        top.addWidget(self.temp)
        top.addWidget(self.icon)
        top.addStretch()

        self.body.addStretch()
        self.body.addLayout(top)
        self.body.addWidget(self.cond)
        self.body.addStretch()
        self.body.addLayout(self._row("FEELS", self.feels_v))
        self.body.addLayout(self._row("WIND", self.wind_v))
        hum_row = QHBoxLayout()
        hum_row.setSpacing(12)
        hum_row.addWidget(self.hum_label)
        hum_row.addWidget(self.hum_bar, 1)
        self.body.addLayout(hum_row)

    @staticmethod
    def _row(label: str, value: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        key = QLabel(label)
        key.setObjectName("k")
        value.setAlignment(Qt.AlignRight)
        row.addWidget(key)
        row.addStretch()
        row.addWidget(value)
        return row

    def update(self, data: dict) -> None:
        self.set_live(True)
        temp = data.get("temperature")
        self.temp.setText(f"{temp:.0f}°" if temp is not None else "—")
        label, glyph = weather_text(data.get("code"))
        self.icon.setText(glyph)
        self.cond.setText(label)
        apparent = data.get("apparent")
        self.feels_v.setText(f"{apparent:.0f}°" if apparent is not None else "—")
        wind = data.get("wind_speed")
        self.wind_v.setText(f"{wind:.0f} km/h" if wind is not None else "—")
        humidity = data.get("humidity")
        if humidity is not None:
            self.hum_bar.setValue(int(humidity))
            self.hum_label.setText(f"HUMIDITY {int(humidity)}%")
        else:
            self.hum_bar.setValue(0)
            self.hum_label.setText("HUMIDITY —")


class CalendarPanel(Panel):
    """A month grid with today highlighted. Purely local — no data source."""

    def __init__(self) -> None:
        super().__init__("CALENDAR", PALETTE["purple"])
        self.set_live(True)  # always local
        self._rendered: tuple | None = None
        self._build()

    def tick(self) -> None:
        """Rebuild only when the day/month changes (cheap to check each second)."""
        today = datetime.now()
        key = (today.year, today.month, today.day)
        if key != self._rendered:
            self._rendered = key
            self._build()

    def _build(self) -> None:
        _clear(self.body)
        now = datetime.now()

        title = QLabel(now.strftime("%B %Y").upper())  # e.g. "AUGUST 2026"
        title.setObjectName("panelTitle")
        title.setStyleSheet(f"color:{PALETTE['purple']};")
        title.setAlignment(Qt.AlignCenter)
        self.body.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setContentsMargins(0, 10, 0, 0)
        for col, letter in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            head = QLabel(letter)
            head.setObjectName("k")
            head.setAlignment(Qt.AlignCenter)
            grid.addWidget(head, 0, col)

        first_weekday = datetime(now.year, now.month, 1).weekday()  # Monday = 0
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        for day in range(1, days_in_month + 1):
            index = first_weekday + day - 1
            cell = QLabel(str(day))
            cell.setAlignment(Qt.AlignCenter)
            cell.setMinimumSize(26, 26)
            if day == now.day:
                cell.setStyleSheet(
                    f"background:{PALETTE['purple']};color:#000;border-radius:13px;font-weight:700;"
                )
            else:
                cell.setObjectName("v")
            grid.addWidget(cell, index // 7 + 1, index % 7)

        wrap = QWidget()
        wrap.setLayout(grid)
        self.body.addWidget(wrap, alignment=Qt.AlignCenter)
        self.body.addStretch()


class Bridge(QObject):
    frame = Signal(object)
    station = Signal(object)
    status = Signal(str, str)


class BackgroundRunner(threading.Thread):
    def __init__(self, bridge: Bridge) -> None:
        super().__init__(daemon=True)
        self.bridge = bridge
        self._stop: asyncio.Event | None = None

    def run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception:  # noqa: BLE001
            pass

    async def _main(self) -> None:
        self._stop = asyncio.Event()
        await asyncio.gather(self._weather(), self._shell())

    async def _weather(self) -> None:
        assert self._stop is not None
        while not self._stop.is_set():
            try:
                self.bridge.station.emit(await weather.fetch(LATITUDE, LONGITUDE, WEATHER_REFRESH_SECONDS))
            except Exception:  # noqa: BLE001
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=WEATHER_REFRESH_SECONDS)
                return
            except asyncio.TimeoutError:
                continue

    async def _shell(self) -> None:
        assert self._stop is not None

        def on_frame(frame: dict) -> None:
            self.bridge.frame.emit(frame)

        def on_status(text: str, cls: str) -> None:
            self.bridge.status.emit(text, cls)

        await shell_client.stream(SHELL_URL, on_frame, on_status, self._stop)

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("desk-dashboard")
        self._sized = False
        self._dotted = self._load_dotted_font()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 14, 20, 8)
        outer.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.clock_panel = ClockPanel()
        self.weather_panel = WeatherPanel()
        self.calendar_panel = CalendarPanel()
        row.addWidget(self.clock_panel, 1)
        row.addWidget(self.weather_panel, 1)
        row.addWidget(self.calendar_panel, 1)
        outer.addLayout(row, 1)

        self.conn = QLabel("starting…")
        self.conn.setObjectName("conn")
        outer.addWidget(self.conn)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        self.bridge = Bridge()
        self.bridge.frame.connect(self._on_frame)
        self.bridge.station.connect(self._on_station)
        self.bridge.status.connect(self._on_status)
        self.runner = BackgroundRunner(self.bridge)
        self.runner.start()

    @staticmethod
    def _load_dotted_font() -> str:
        """Load the bundled VT323 dot-matrix font; return its family (fallback VT323)."""
        path = os.path.join(_FONT_DIR, "VT323-Regular.ttf")
        font_id = QFontDatabase.addApplicationFont(path)
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        return families[0] if families else "VT323"

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._sized:
            self._apply_sizes()
            self._sized = True

    def _apply_sizes(self) -> None:
        screen = self.screen()
        height = screen.size().height() if screen else 480

        def scale(label: QLabel, ratio: float, lo: int, hi: int, family: str | None = None) -> None:
            font = label.font()
            font.setPixelSize(max(lo, min(int(height * ratio), hi)))
            if family is not None:
                font.setFamily(family)
            label.setFont(font)

        scale(self.clock_panel.time, 0.42, 80, 230, family=self._dotted)   # dot-matrix clock
        scale(self.clock_panel.date, 0.06, 12, 22)
        scale(self.clock_panel.day_label, 0.045, 11, 16, family=self._dotted)
        scale(self.weather_panel.temp, 0.26, 56, 140)
        scale(self.weather_panel.icon, 0.22, 50, 130)                       # big weather glyph
        scale(self.weather_panel.cond, 0.055, 12, 24)

    def _tick(self) -> None:
        self.clock_panel.tick()
        self.calendar_panel.tick()

    def _on_station(self, data: dict) -> None:
        self.weather_panel.update(data)

    def _on_status(self, text: str, cls: str) -> None:
        self.conn.setText(text)
        color = {
            "live": PALETTE["green"],
            "degraded": PALETTE["yellow"],
            "disconnected": PALETTE["orange"],
        }.get(cls, PALETTE["dim"])
        self.conn.setStyleSheet(f"color:{color};")

    def _on_frame(self, frame: dict) -> None:
        """Shell stream frame — kept for the connection indicator and future panels;
        the calendar is now a local month grid, so this is unused for now."""

    def closeEvent(self, event) -> None:  # noqa: N802
        self.runner.stop()
        super().closeEvent(event)
