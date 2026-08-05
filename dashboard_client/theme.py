"""Qt stylesheet (QSS) built from the QD-OLED palette.

Pure-black surfaces, hairline borders, dim labels, vivid colour only on content.
Selectors target objectNames (QSS supports ``#name``), set in the widget code.
"""
from __future__ import annotations

from .config import PALETTE as P

QSS = f"""
* {{ color: {P["text"]}; font-family: "JetBrains Mono", "JetBrains Mono NL", monospace; }}
QMainWindow, QWidget {{ background: {P["black"]}; }}
QLabel {{ background: transparent; }}

#clock {{ font-size: 104px; font-weight: 200; }}
#date   {{ font-size: 22px; color: {P["dim"]}; font-weight: 400; }}
#conn   {{ font-size: 13px; color: {P["dim"]}; }}

#card {{
    border: 1px solid {P["border"]};
    border-radius: 14px;
    background: {P["panel"]};
}}
#cardTitle  {{ font-size: 15px; font-weight: 600; }}
#cardCat    {{ font-size: 11px; font-weight: 600; }}
#k          {{ color: {P["dim"]}; font-size: 13px; }}
#v          {{ color: {P["text"]}; font-size: 14px; font-weight: 500; }}
#section-label {{ font-size: 12px; color: {P["text"]}; font-weight: 600; }}

#stationTemp    {{ font-size: 84px; font-weight: 200; }}
#stationSummary {{ font-size: 20px; font-weight: 400; }}
#stationMeta    {{ color: {P["dim"]}; font-size: 14px; }}
#stationDelta   {{ font-size: 13px; font-weight: 600; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {P["border"]};
    border-radius: 2px;
    min-height: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
