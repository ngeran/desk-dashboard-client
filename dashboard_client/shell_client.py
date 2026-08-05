"""Consumes the shell: GET /components + WS /stream, with reconnect.

Pure async, no Qt. The UI runs this in a background thread and receives frames /
status via plain (thread-safe) callbacks — the UI side emits Qt signals.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import websockets


async def fetch_components(shell_url: str) -> list[dict]:
    """One-shot fetch of the merged manifest list (titles/categories/schemas)."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{shell_url}/components")
        resp.raise_for_status()
        return resp.json().get("components", [])


async def stream(
    shell_url: str,
    on_frame: Callable[[dict], None],
    on_status: Callable[[str, str], None],
    stop: asyncio.Event,
) -> None:
    """Subscribe to the shell's merged stream until ``stop`` is set.

    Reconnects automatically (2s backoff) so the Pi rides out shell restarts and
    network blips without exiting.
    """
    ws_url = shell_url.replace("http://", "ws://").replace("https://", "wss://") + "/stream"
    while not stop.is_set():
        try:
            on_status("connecting", "disconnected")
            async with websockets.connect(ws_url) as ws:
                on_status("live", "live")
                async for message in ws:
                    if stop.is_set():
                        return
                    on_frame(json.loads(message))
        except Exception as exc:  # noqa: BLE001 — boundary: reconnect, don't die
            on_status(f"disconnected · {exc}", "disconnected")
            try:
                await asyncio.wait_for(asyncio.shield(stop.wait()), timeout=2.0)
                return
            except asyncio.TimeoutError:
                continue
