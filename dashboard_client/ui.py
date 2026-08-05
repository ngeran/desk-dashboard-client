"""The Qt interface: an always-on clock + weather station, plus a dynamic grid of
component cards rendered through the modular registry.

Thread model: the Qt event loop runs on the main thread; a background asyncio
thread fetches weather (direct) and consumes the shell's WS stream, pushing
results into the UI via Qt signals (thread-safe, queued to the main thread).
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import shell_client, weather
from .config import (
    CATEGORY_COLORS,
    CLOCK_FORMAT,
    DATE_FORMAT,
    LATITUDE,
    LONGITUDE,
    PALETTE,
    SHELL_URL,
    WEATHER_REFRESH_SECONDS,
)
from .renderers import renderer_for

GRID_COLS = 2


def _clear(layout: QVBoxLayout) -> None:
    """Delete every child widget/layout of ``layout`` (for flicker-free repopulation)."""
    while layout.count():
        item = layout.takeAt(0)
        child = item.widget() or item.layout()
        if child is None:
            continue
        if isinstance(child, QVBoxLayout):
            _clear(child)
        else:
            child.deleteLater()


class Bridge(QObject):
    """Carries data from the background asyncio thread to the Qt main thread."""

    frame = Signal(object)        # a merged snapshot frame
    components = Signal(object)   # a manifest list
    station = Signal(object)      # weather-station data
    status = Signal(str, str)     # (text, class: live|degraded|disconnected)


class ComponentCard(QWidget):
    """One component's card. Chrome is stable; the body is repopulated each frame."""

    def __init__(self, accent: str) -> None:
        super().__init__()
        self.setObjectName("card")
        self._accent = accent
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(8)

        self.bar = QFrame()
        self.bar.setFixedHeight(3)
        self.bar.setStyleSheet("border:none;")
        outer.addWidget(self.bar)

        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("cardTitle")
        self.cat = QLabel("")
        self.cat.setObjectName("cardCat")
        self.cat.setStyleSheet(f"color:{accent};")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.cat)
        outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 4, 0, 0)
        self.body.setSpacing(2)
        outer.addLayout(self.body)

    def update(self, envelope: dict, manifest: dict) -> None:
        self.title.setText(manifest.get("display_name") or envelope.get("component_id", ""))
        self.cat.setText((manifest.get("category") or "").upper())
        status = envelope.get("status")
        bar_color = {
            "ok": self._accent,
            "degraded": PALETTE["yellow"],
            "unreachable": PALETTE["orange"],
        }.get(status, self._accent)
        self.bar.setStyleSheet(f"background:{bar_color}; border:none;")
        _clear(self.body)
        renderer_for(envelope.get("component_id", "")).build_body(self.body, envelope.get("data"), manifest)
        self.setVisible(True)


class WeatherStation(QWidget):
    """The always-on local weather panel (fetched directly; survives backend outages)."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.temp = QLabel("—")
        self.temp.setObjectName("stationTemp")
        self.summary = QLabel("")
        self.summary.setObjectName("stationSummary")
        self.meta = QLabel("")
        self.meta.setObjectName("stationMeta")
        layout.addWidget(self.temp)
        layout.addWidget(self.summary)
        layout.addWidget(self.meta)
        layout.addStretch()

    def update(self, data: dict) -> None:
        from .renderers.formatting import weather_text

        temp = data.get("temperature")
        self.temp.setText(f"{temp:.0f}°" if temp is not None else "—")
        label, glyph = weather_text(data.get("code"))
        self.summary.setText(f"{glyph}  {label}")
        parts = []
        if data.get("apparent") is not None:
            parts.append(f"feels {data['apparent']:.0f}°")
        if data.get("humidity") is not None:
            parts.append(f"{data['humidity']:.0f}% hum")
        if data.get("wind_speed") is not None:
            parts.append(f"{data['wind_speed']:.0f} km/h")
        self.meta.setText("   ".join(parts))


class BackgroundRunner(threading.Thread):
    """Runs weather + shell consumption on a background asyncio loop."""

    def __init__(self, bridge: Bridge) -> None:
        super().__init__(daemon=True)
        self.bridge = bridge
        self._stop: asyncio.Event | None = None

    def run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception:  # noqa: BLE001 — never crash the UI thread's sibling
            pass

    async def _main(self) -> None:
        self._stop = asyncio.Event()
        await asyncio.gather(self._weather(), self._shell())

    async def _weather(self) -> None:
        assert self._stop is not None
        while not self._stop.is_set():
            try:
                data = await weather.fetch(LATITUDE, LONGITUDE, WEATHER_REFRESH_SECONDS)
                self.bridge.station.emit(data)
            except Exception:  # noqa: BLE001 — keep the last station reading on failure
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
            if cls == "live":
                asyncio.create_task(self._components())  # noqa: RUF006

        await shell_client.stream(SHELL_URL, on_frame, on_status, self._stop)

    async def _components(self) -> None:
        try:
            comps = await shell_client.fetch_components(SHELL_URL)
            self.bridge.components.emit(comps)
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("desk-dashboard")
        self._manifests: dict[str, dict] = {}
        self._cards: dict[str, ComponentCard] = {}
        self._order: list[str] = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(28)

        # ── left column: clock + weather station + connection status ─────────
        left = QVBoxLayout()
        left.setSpacing(18)
        self.clock = QLabel("")
        self.clock.setObjectName("clock")
        self.date = QLabel("")
        self.date.setObjectName("date")
        left.addWidget(self.clock)
        left.addWidget(self.date)
        left.addSpacing(28)
        self.station = WeatherStation()
        left.addWidget(self.station)
        left.addStretch()
        self.conn = QLabel("starting…")
        self.conn.setObjectName("conn")
        left.addWidget(self.conn)
        left_wrap = QWidget()
        left_wrap.setLayout(left)
        left_wrap.setFixedWidth(360)
        root.addWidget(left_wrap)

        # ── right: the dynamic component grid ─────────────────────────────────
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_host)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll, 1)

        # clock tick (pure main thread)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        # background data
        self.bridge = Bridge()
        self.bridge.frame.connect(self._on_frame)
        self.bridge.components.connect(self._on_components)
        self.bridge.station.connect(self._on_station)
        self.bridge.status.connect(self._on_status)
        self.runner = BackgroundRunner(self.bridge)
        self.runner.start()

    # ── slots (run on the main thread) ─────────────────────────────────────────
    def _tick(self) -> None:
        now = datetime.now()
        self.clock.setText(now.strftime(CLOCK_FORMAT))
        self.date.setText(now.strftime(DATE_FORMAT))

    def _on_station(self, data: dict) -> None:
        self.station.update(data)

    def _on_status(self, text: str, cls: str) -> None:
        self.conn.setText(text)
        color = {
            "live": PALETTE["green"],
            "degraded": PALETTE["yellow"],
            "disconnected": PALETTE["orange"],
        }.get(cls, PALETTE["dim"])
        self.conn.setStyleSheet(f"color:{color};")

    def _on_components(self, comps: list[dict]) -> None:
        self._manifests = {c["id"]: c for c in comps}
        changed = False
        for cid in [c["id"] for c in comps]:
            if cid not in self._cards:
                self._add_card(cid)
                changed = True
        if changed:
            self._reflow()

    def _on_frame(self, frame: dict) -> None:
        comps = frame.get("components", {})
        ids = list(comps.keys())
        changed = False
        for cid in ids:
            if cid not in self._cards:
                self._add_card(cid)
                changed = True
        for cid in [c for c in list(self._cards) if c not in ids]:
            self._remove_card(cid)
            changed = True
        for cid, env in comps.items():
            self._cards[cid].update(env, self._manifests.get(cid, {"id": cid}))
        if changed:
            self._reflow()

    # ── card grid management ───────────────────────────────────────────────────
    def _add_card(self, cid: str) -> None:
        manifest = self._manifests.get(cid, {})
        accent = CATEGORY_COLORS.get(manifest.get("category"), PALETTE["blue"])
        self._cards[cid] = ComponentCard(accent)
        self._order.append(cid)

    def _remove_card(self, cid: str) -> None:
        card = self._cards.pop(cid, None)
        if card is not None:
            self.grid.removeWidget(card)
            card.deleteLater()
        if cid in self._order:
            self._order.remove(cid)

    def _reflow(self) -> None:
        for card in self._cards.values():
            self.grid.removeWidget(card)
        for i, cid in enumerate(self._order):
            if cid in self._cards:
                self.grid.addWidget(self._cards[cid], i // GRID_COLS, i % GRID_COLS)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.runner.stop()
        super().closeEvent(event)
