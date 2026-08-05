"""The Qt interface — three fastfetch-style panels across the strip.

Weather (left), Clock (center), Calendar (right). Clock + Weather + Calendar are
all local, so the screen is never blank. The clock font is selectable via the
CLOCK_FONT env var (any bundled under assets/fonts/). Layout is one row of three
equal panels sized for a wide strip (e.g. 1920×480); hero fonts scale to the
screen, and the calendar grid expands to fill its panel.

Thread model: Qt loop on the main thread; a background asyncio thread fetches
weather and consumes the shell's WS stream (kept for the connection indicator +
future panels), pushing data via Qt signals.
"""
from __future__ import annotations

import asyncio
import calendar
import os
import threading
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import shell_client, weather
from .config import CLOCK_FONT, LATITUDE, LONGITUDE, PALETTE, SHELL_URL, WEATHER_REFRESH_SECONDS
from .renderers.formatting import weather_text

_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")


def _clear(layout: QVBoxLayout) -> None:
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
    """A month grid with today highlighted. Expands to fill the panel; purely local."""

    def __init__(self) -> None:
        super().__init__("CALENDAR", PALETTE["purple"])
        self.set_live(True)
        self._rendered: tuple | None = None
        self._day_font = 24
        self._head_font = 13
        self._build()

    def configure(self, day_font: int, head_font: int) -> None:
        if day_font != self._day_font or head_font != self._head_font:
            self._day_font = day_font
            self._head_font = head_font
            self._rendered = None
            self._build()

    def tick(self) -> None:
        now = datetime.now()
        key = (now.year, now.month, now.day)
        if key != self._rendered:
            self._rendered = key
            self._build()

    def _mkfont(self, px: int) -> QFont:
        font = QFont("DejaVu Sans Mono")
        font.setPixelSize(px)
        return font

    def _build(self) -> None:
        _clear(self.body)
        now = datetime.now()

        title = QLabel(now.strftime("%B %Y").upper())  # e.g. "AUGUST 2026"
        title.setObjectName("panelTitle")
        title.setStyleSheet(f"color:{PALETTE['purple']};")
        title.setAlignment(Qt.AlignCenter)
        self.body.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 8, 0, 0)
        for col, letter in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            grid.setColumnStretch(col, 1)
            head = QLabel(letter)
            head.setObjectName("k")
            head.setAlignment(Qt.AlignCenter)
            head.setFont(self._mkfont(self._head_font))
            grid.addWidget(head, 0, col)

        first_weekday = datetime(now.year, now.month, 1).weekday()  # Monday = 0
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        for day in range(1, days_in_month + 1):
            index = first_weekday + day - 1
            r, c = index // 7 + 1, index % 7
            grid.setRowStretch(r, 1)
            cell = QLabel(str(day))
            cell.setAlignment(Qt.AlignCenter)
            cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            cell.setFont(self._mkfont(self._day_font))
            if day == now.day:
                cell.setStyleSheet(
                    f"background:{PALETTE['purple']};color:#000;border-radius:10px;font-weight:700;"
                )
            else:
                cell.setStyleSheet(f"color:{PALETTE['text']};")
            grid.addWidget(cell, r, c)

        wrap = QWidget()
        wrap.setLayout(grid)
        wrap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.body.addWidget(wrap, 1)  # stretch → the grid fills the panel


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
        self._clock_family = self._load_clock_font()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 14, 20, 8)
        outer.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.weather_panel = WeatherPanel()
        self.clock_panel = ClockPanel()
        self.calendar_panel = CalendarPanel()
        row.addWidget(self.weather_panel, 1)
        row.addWidget(self.clock_panel, 1)
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
    def _load_clock_font() -> str:
        """Load every bundled font; return the family matching CLOCK_FONT (or the first)."""
        families: list[str] = []
        for name in sorted(os.listdir(_FONT_DIR)):
            if not name.lower().endswith(".ttf"):
                continue
            font_id = QFontDatabase.addApplicationFont(os.path.join(_FONT_DIR, name))
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
        wanted = CLOCK_FONT.lower()
        for fam in families:
            if wanted in fam.lower():
                return fam
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

        scale(self.clock_panel.time, 0.42, 80, 230, family=self._clock_family)
        scale(self.clock_panel.date, 0.06, 12, 22)
        scale(self.clock_panel.day_label, 0.045, 11, 16, family=self._clock_family)
        scale(self.weather_panel.temp, 0.26, 56, 140)
        scale(self.weather_panel.icon, 0.22, 50, 130)
        scale(self.weather_panel.cond, 0.055, 12, 24)
        # calendar fills its panel; scale its day + header fonts to the screen
        self.calendar_panel.configure(
            day_font=max(18, min(int(height * 0.05), 40)),
            head_font=max(11, min(int(height * 0.03), 18)),
        )

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
        """Shell stream frame — unused for now (all three panels are local)."""

    def closeEvent(self, event) -> None:  # noqa: N802
        self.runner.stop()
        super().closeEvent(event)
