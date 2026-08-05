"""Renderer registry — the display-side analog of the backend component SDK.

``renderer_for(component_id)`` selects a renderer by id (bespoke), then falls back
to the :class:`GenericRenderer`. Register a custom renderer under an id to give
one component a bespoke panel; everything else (and any new component) uses the
generic one with no client edit.
"""
from __future__ import annotations

_renderers: dict[str, object] = {}
_fallback: object | None = None  # lazily built so importing this package needs no Qt


def register(component_id: str, renderer: object) -> None:
    """Register a bespoke renderer for a component id (call at import time)."""
    _renderers[component_id] = renderer


def renderer_for(component_id: str) -> object:
    global _fallback
    bespoke = _renderers.get(component_id)
    if bespoke is not None:
        return bespoke
    if _fallback is None:  # imported lazily — keeps the package Qt-free until a render
        from .generic import GenericRenderer

        _fallback = GenericRenderer()
    return _fallback
