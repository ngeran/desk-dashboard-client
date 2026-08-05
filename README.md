# desk-dashboard-client

Native Python (PySide6/Qt) display client for [desk-dashboard](../desk-dashboard),
built for a Raspberry Pi on a QD-OLED screen. **Offline-first:** a local clock and
a weather station (the Pi fetches Open-Meteo directly) always render, so the
screen is never blank. When the shell is reachable, backend components merge in
and render through swappable per-component renderer modules — a generic fallback
handles anything new with no client code.

## Stack
- **PySide6 (Qt)** — pure-black OLED UI, QSS theming, great fonts, layout engine.
- **httpx + websockets** — direct weather fetch + shell `/stream` (same libs as the backend).
- **structlog** — structured logs, matching the backend.
- A background asyncio thread pushes data to the Qt main thread via signals.

## Run on the Pi (64-bit Raspberry Pi OS)
```bash
sudo apt install -y uv   # or: curl -LsSf https://astral.sh/uv/install.sh | sh
git clone git@github.com:ngeran/desk-dashboard-client.git
cd desk-dashboard-client
uv sync                                   # creates .venv, installs PySide6 etc.
SHELL_URL=http://192.168.1.10:30080 uv run dashboard-client
```
> PySide6 ships aarch64 wheels — `uv sync` should just work on a 64-bit Pi. If your
> Pi is 32-bit, switch to a 64-bit OS (PySide6 has no 32-bit arm wheels).

### Environment
| Var | Default | Purpose |
|---|---|---|
| `SHELL_URL` | `http://localhost:30080` | The shell on the LAN (NodePort 30080 on the k3s host) |
| `LATITUDE` / `LONGITUDE` | `40.4168` / `-3.7038` | The always-on local weather station |
| `WEATHER_REFRESH_SECONDS` | `600` | How often the station refreshes |
| `CLOCK_FORMAT` / `DATE_FORMAT` | `%H:%M` / `%A %e %B` | Clock/date `strftime` formats |

### Fullscreen / autostart
The window opens fullscreen. For kiosk boot, a systemd user unit:
```ini
# ~/.config/systemd/user/desk-dashboard-client.service
[Unit]
Description=desk-dashboard display client
After=graphical-session.target
[Service]
Environment=SHELL_URL=http://192.168.1.10:30080
Environment=LATITUDE=...  LONGITUDE=...
WorkingDirectory=%h/desk-dashboard-client
ExecStart=%h/.local/bin/uv run dashboard-client
Restart=always
[Install]
WantedBy=default.target
```
```bash
systemctl --user daemon-reload && systemctl --user enable --now desk-dashboard-client.service
sudo loginctl enable-user pi   # run the user service without an active login
```

## Develop on a laptop
```bash
uv sync
uv run dashboard-client        # points at localhost:30080 by default
```
Run the backend locally (see desk-dashboard README → Local dev) and the client
shows the same merged stream.

## Add a bespoke renderer (the modular part)
Components render via a registry (`dashboard_client/renderers/`). By default the
generic renderer draws any component's data as labelled rows/sections. To give one
component a custom panel, add a renderer and register it:
```python
# dashboard_client/renderers/host_telemetry.py
from PySide6.QtWidgets import QLabel, QVBoxLayout

class HostTelemetryRenderer:
    def build_body(self, layout: QVBoxLayout, data, manifest) -> None:
        layout.addWidget(QLabel(f"CPU {data['cpu']['total_usage_percent']}%"))
        layout.addWidget(QLabel(f"RAM {data['memory']['usage_percent']}%"))
```
```python
# dashboard_client/ui.py  (after the renderers import)
from .renderers import register
from .renderers.host_telemetry import HostTelemetryRenderer
register("host-telemetry", HostTelemetryRenderer())
```
Unregistered components (and any new one) still render via the generic fallback —
zero client edit required to *see* them.

## OLED care
Pure black background (pixels off), dim static labels, a clock that changes every
second, and no fixed bright chrome — all to minimise uneven pixel wear on a 24/7
QD-OLED. For extra safety, enable your display's pixel-shift / screen-shift in the
Pi's display settings.
