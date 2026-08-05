"""Qt stylesheet (QSS) — fastfetch-style modular panels on pure black.

Pure-black surfaces, hairline borders, vivid colour only on content/accents.
Font sizes for the hero numbers are set per-screen in ui.py (_apply_sizes); the
mono label/value base sizes + families live here and are deliberately larger and
higher-contrast than before so FEELS/WIND/HUMIDITY are easy to read.
"""
from __future__ import annotations

from .config import PALETTE as P

QSS = f"""
QMainWindow, QWidget {{ background: {P["black"]}; }}
QLabel {{ background: transparent; color: {P["text"]}; }}

#panel       {{ border: 1px solid {P["border"]}; border-radius: 14px; }}
#panelTitle  {{ font-size: 13px; font-weight: 700; letter-spacing: 2px; color: {P["text"]}; }}
#panelBadge  {{ font-size: 11px; font-weight: 700; letter-spacing: 1px; }}

#k          {{ color: #a8aeb8; font-family: "DejaVu Sans Mono","Liberation Mono",monospace; font-size: 16px; }}
#v          {{ color: {P["text"]}; font-family: "DejaVu Sans Mono","Liberation Mono",monospace; font-size: 18px; }}
#clockBig   {{ color: {P["text"]}; font-family: "DejaVu Sans","Liberation Sans",sans-serif; font-weight: 200; }}
#weatherIcon{{ color: {P["text"]}; }}
#date       {{ color: {P["dim"]}; font-family: "DejaVu Sans","Liberation Sans",sans-serif; font-size: 20px; letter-spacing: 1px; }}

#conn       {{ color: {P["dim"]}; font-size: 12px; font-family: "DejaVu Sans Mono",monospace; letter-spacing: 1px; }}

QProgressBar {{ background: #161616; border: none; border-radius: 2px; max-height: 4px; }}
QScrollArea, QScrollBar {{ border: none; background: transparent; }}
"""
