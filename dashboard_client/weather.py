"""Direct Open-Meteo fetch for the always-on weather station.

The Pi fetches this itself, so the station keeps working when the shell/backend
are unreachable. It mirrors the backend weather component's *source* but is fully
standalone — the display must never depend on the backend being up.
"""
from __future__ import annotations

import time

import httpx

_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
_CURRENT = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
    "wind_speed_10m,wind_direction_10m,precipitation,cloud_cover"
)
_cache: dict[str, tuple[float, dict]] = {}  # "lat,lon" -> (expires_monotonic, data)


async def fetch(latitude: float, longitude: float, ttl_seconds: int = 600) -> dict:
    """Return current conditions, refreshing from Open-Meteo only when stale."""
    key = f"{round(latitude, 3)},{round(longitude, 3)}"
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    params = {"latitude": latitude, "longitude": longitude, "current": _CURRENT, "timezone": "auto"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(_OPEN_METEO, params=params)
        resp.raise_for_status()
        raw = resp.json()
    current = raw.get("current", {})
    data = {
        "temperature": current.get("temperature_2m"),
        "apparent": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "code": current.get("weather_code"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "precipitation": current.get("precipitation"),
        "cloud_cover": current.get("cloud_cover"),
        "timezone": raw.get("timezone"),
    }
    _cache[key] = (now + ttl_seconds, data)
    return data
