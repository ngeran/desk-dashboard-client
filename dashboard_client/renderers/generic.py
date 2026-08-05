"""The generic renderer — labelled rows + nested sections for any component's data.

It's the fallback for components without a bespoke renderer, so a brand-new
component shows up looking sensible with zero client code. Drop a custom Renderer
in this package and register it (see ``renderers.__init__``) for a bespoke panel.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from .formatting import format_value, omit, pretty

_LIST_NAME_KEYS = ["name", "device", "mount", "summary", "uid"]


class GenericRenderer:
    """Renders data into a given layout (called by :class:`ComponentCard`)."""

    def build_body(self, layout: QVBoxLayout, data: object, manifest: dict) -> None:
        self._populate(layout, data, "")

    # ── internal ──────────────────────────────────────────────────────────────
    def _populate(self, layout: QVBoxLayout, value: object, key_prefix: str) -> None:
        if value is None:
            layout.addWidget(self._dim("no data"))
        elif isinstance(value, list):
            self._render_list(layout, value)
        elif isinstance(value, dict):
            if not value:
                layout.addWidget(self._dim("—"))
            for k, v in value.items():
                if isinstance(v, (dict, list)):
                    self._section(layout, k, v)
                else:
                    layout.addLayout(self._row(k, v))
        else:
            layout.addWidget(QLabel(format_value(key_prefix, value)))

    def _section(self, layout: QVBoxLayout, key: str, value: object) -> None:
        label = QLabel(pretty(key))
        label.setObjectName("section-label")
        layout.addWidget(label)
        inner = QVBoxLayout()
        inner.setContentsMargins(10, 0, 0, 0)
        inner.setSpacing(2)
        self._populate(inner, value, key + ".")
        layout.addLayout(inner)

    def _render_list(self, layout: QVBoxLayout, items: list) -> None:
        if not items:
            layout.addWidget(self._dim("—"))
            return
        if all(not isinstance(i, (dict, list)) for i in items):
            layout.addWidget(QLabel(", ".join(format_value("", i) for i in items)))
            return
        for item in items:
            if isinstance(item, dict):
                name = next((item[k] for k in _LIST_NAME_KEYS if item.get(k)), None)
                if name:
                    sub = QLabel(str(name))
                    sub.setObjectName("k")
                    layout.addWidget(sub)
                inner = QVBoxLayout()
                inner.setContentsMargins(10, 0, 0, 0)
                inner.setSpacing(2)
                self._populate(inner, omit(item, _LIST_NAME_KEYS), "")
                layout.addLayout(inner)
            else:
                layout.addWidget(QLabel(format_value("", item)))

    def _row(self, key: str, value: object) -> QHBoxLayout:
        row = QHBoxLayout()
        k = QLabel(pretty(key))
        k.setObjectName("k")
        v = QLabel(format_value(key, value))
        v.setObjectName("v")
        v.setAlignment(Qt.AlignRight)
        row.addWidget(k)
        row.addWidget(v)
        return row

    def _dim(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("k")
        return label
