"""Qt stylesheet (QSS) built from the QD-OLED palette.

Pure-black surfaces, hairline borders, dim labels, vivid colour only on content.
Selectors target objectNames (QSS supports ``#name``), set in the widget code.
"""
from __future__ import annotations

from .config import PALETTE as P

QSS = f"""
* {{ color: {P["text"]}; }}
QMainWindow, QWidget {{ background: {P["black"]}; }}
QLabel {{ background: transparent; }}

#clock {{ font-size: 104px; font-weight: 200; }}
#date   {{ font-size: 22px; color: {P["dim"]}; }}
#conn   {{ font-size: 13px; }}

#card       {{ border: 1px solid {P["border"]}; border-radius: 14px; }}
#cardTitle  {{ font-size: 15px; font-weight: 600; }}
#cardCat    {{ font-size: 11px; }}
#k          {{ color: {P["dim"]}; font-size: 13px; }}
#v          {{ color: {P["text"]}; font-size: 14px; }}
#section-label {{ font-size: 12px; color: {P["text"]}; }}

#stationTemp    {{ font-size: 84px; font-weight: 200; }}
#stationSummary {{ font-size: 20px; }}
#stationMeta    {{ color: {P["dim"]}; font-size: 14px; }}

QScrollArea {{ border: none; }}
QScrollBar {{ background: {P["black"]}; }}
"""
