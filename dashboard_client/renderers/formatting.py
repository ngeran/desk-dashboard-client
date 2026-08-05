"""Value formatting for the generic renderer + weather station (Qt-free).

Kept separate from the Qt widgets so the formatting logic is unit-checkable
without a display. Unit hints are guessed from key names (``_percent``, ``_celsius``,
``_mib``, …) so the generic renderer labels any component's data sensibly.
"""
from __future__ import annotations

UNITS: list[tuple] = [
    (lambda k: "percent" in k or k.endswith("usage"), lambda v: f"{v}%"),
    (lambda k: "celsius" in k or "temp" in k, lambda v: f"{v}°C"),
    (lambda k: k.endswith("_gib"), lambda v: f"{v} GiB"),
    (lambda k: k.endswith("_mib"), lambda v: f"{v / 1024:.1f} GiB" if v >= 1024 else f"{v} MiB"),
    (lambda k: k.endswith("_mhz"), lambda v: f"{v} MHz"),
    (lambda k: "wind_speed" in k or k.endswith("kmh"), lambda v: f"{v} km/h"),
    (lambda k: k.endswith("_per_sec"), lambda v: _rate(v)),
    (lambda k: "humidity" in k, lambda v: f"{v}%"),
]


def format_value(key: str, value) -> str:
    """Format a scalar value, guessing the unit from the key."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        for matches, render in UNITS:
            if matches(key):
                return render(_round(value))
        return str(_round(value))
    if isinstance(value, str) and value[:4].isdigit() and "T" in value[:20]:
        # ISO timestamp → friendly
        try:
            from datetime import datetime
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%a %H:%M")
        except ValueError:
            return value
    return str(value)


def _rate(bytes_per_sec: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    i, v = 0, float(bytes_per_sec)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v if i == 0 else round(v, 1)} {units[i]}"


def _round(v: float) -> float:
    return round(v, 2) if not float(v).is_integer() else int(v)


def pretty(key: str) -> str:
    """``total_usage_percent`` -> ``Total usage percent``."""
    return key.replace("_", " ").strip().capitalize()


def omit(d: dict, keys: list[str]) -> dict:
    return {k: v for k, v in d.items() if k not in keys}


# WMO weather codes -> (label, glyph). Compact; covers the common range.
WMO = {
    0: ("Clear", "☀"), 1: ("Mainly clear", "🌤"), 2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁"), 45: ("Fog", "🌫"), 48: ("Rime fog", "🌫"),
    51: ("Light drizzle", "🌦"), 53: ("Drizzle", "🌦"), 55: ("Heavy drizzle", "🌧"),
    61: ("Light rain", "🌧"), 63: ("Rain", "🌧"), 65: ("Heavy rain", "🌧"),
    71: ("Light snow", "🌨"), 73: ("Snow", "❄"), 75: ("Heavy snow", "❄"),
    80: ("Rain showers", "🌦"), 81: ("Showers", "🌧"), 82: ("Violent showers", "⛈"),
    95: ("Thunderstorm", "⛈"), 96: ("Thunderstorm", "⛈"), 99: ("Hailstorm", "⛈"),
}


def weather_text(code) -> tuple[str, str]:
    return WMO.get(int(code) if code is not None else -1, ("—", "·"))
