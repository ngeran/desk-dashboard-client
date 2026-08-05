"""desk-dashboard Pi display client (native Python/Qt).

Offline-first display: a local clock + weather station (the Pi fetches Open-Meteo
directly) always render, so the screen is never blank. When the shell is
reachable, backend components merge in and render through swappable per-component
renderer modules (a generic fallback handles anything new with no client edit).
"""
