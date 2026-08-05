"""Client configuration (env-driven) + the QD-OLED palette.

The palette is deliberately vivid-but-not-pure-primary (no #0000FF/#00FF00):
pure primaries age QD-OLED subpixels unevenly on a 24/7 display, and these
slightly-off shades still pop on pure black while being kinder for burn-in.
"""
from __future__ import annotations

import os


def env(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v if v not in (None, "") else default


def env_float(key: str, default: float) -> float:
    try:
        v = os.environ.get(key)
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def env_int(key: str, default: int) -> int:
    try:
        v = os.environ.get(key)
        return int(v) if v not in (None, "") else default
    except ValueError:
        return default


# The shell's base URL on the LAN (NodePort 30080 on the k3s host).
SHELL_URL = env("SHELL_URL", "http://localhost:30080").rstrip("/")
# Site for the always-on local weather station (the Pi fetches this directly).
LATITUDE = env_float("LATITUDE", 40.4168)
LONGITUDE = env_float("LONGITUDE", -3.7038)
WEATHER_REFRESH_SECONDS = env_int("WEATHER_REFRESH_SECONDS", 600)
CLOCK_FORMAT = env("CLOCK_FORMAT", "%H:%M")     # big clock
DATE_FORMAT = env("DATE_FORMAT", "%A %e %B")    # under the clock

# QD-OLED palette: pure black + vivid accents.
PALETTE = {
    "black": "#000000",
    "panel": "#000000",      # keep panels pure black too — only content pixels emit
    "border": "#1c1c1c",
    "text": "#e8eaed",
    "dim": "#8a8f98",
    "blue": "#4ca6ff",
    "green": "#3dd68c",
    "yellow": "#ffd24a",
    "orange": "#ff8a3d",
    "purple": "#b985ff",
}
# category -> accent colour (used for card side-marks + section labels).
CATEGORY_COLORS = {
    "system": PALETTE["blue"],
    "environment": PALETTE["green"],
    "personal": PALETTE["purple"],
}
