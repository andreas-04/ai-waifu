"""
WsNotifier — broadcasts JSON events to WebSocket and HTTP SSE clients.

Server runs on a single hardcoded port (8765):
  ws://localhost:8765/ws       — raw WebSocket  (any WS client)
  http://localhost:8765/events — Server-Sent Events stream (HTTP clients)

JSON message shape
------------------
  {
    "module":    "posture" | "hydration" | "focus",
    "level":     "info" | "warning" | "alert",
    "simple":    "Bad posture",
    "detail":    "⚠️  Bad posture for 5s: Head forward, Shoulders rounded",
    "timestamp": 1740192000.123
  }
"""

import asyncio
import json
import time
import threading
import logging
from typing import Optional

try:
    from aiohttp import web
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False
    web = None  # type: ignore

WS_PORT = 8765

_log = logging.getLogger(__name__)


class WsNotifier:
    """
    Thread-safe event broadcaster.

    start()  — launches a daemon background thread with an aiohttp server.
    notify() — thread-safe; call from any thread or frame callback.
    stop()   — shuts down the server gracefully.

    Usage
    -----
        notifier = WsNotifier()
        notifier.start()
        notifier.notify("posture", "warning", "Bad posture", "⚠️  Bad posture for 5s: …")
        notifier.stop()
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        # Both collections are only ever touched from within self._loop:
        self._ws_clients: set = set()
        self._sse_queues: list = []

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the server in a daemon background thread (non-blocking)."""
        if not _AIOHTTP_AVAILABLE:
            print("⚠️  WsNotifier: aiohttp not installed — WebSocket notifications disabled.")
            print("   Install with: pip install aiohttp")
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="WsNotifier"
        )
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            print("⚠️  WsNotifier: server did not start within 5 s.")

    def stop(self) -> None:
        """Ask the background event loop to stop."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def notify(self, module: str, level: str, simple: str, detail: str) -> None:
        """
        Broadcast a notification to all connected clients.

        Parameters
        ----------
        module : str   "posture" | "hydration" | "focus"
        level  : str   "info" | "warning" | "alert"
        simple : str   Short human-readable label, e.g. "Bad posture"
        detail : str   Full detail matching the console log message
        """
        if self._loop is None or not self._loop.is_running():
            return
        payload = json.dumps({
            "module":    module,
            "level":     level,
            "simple":    simple,
            "detail":    detail,
            "timestamp": time.time(),
        })
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    def notify_scores(
        self,
        posture:   int | None,
        hydration: int | None,
        focus:     int | None,
    ) -> None:
        """
        Broadcast a periodic score snapshot to all connected clients.

        JSON shape
        ----------
        {
          "type":      "score",
          "posture":   85,
          "hydration": 60,
          "focus":     70,
          "timestamp": 1740192000.123
        }
        """
        if self._loop is None or not self._loop.is_running():
            return
        payload = json.dumps({
            "type":      "score",
            "posture":   posture,
            "hydration": hydration,
            "focus":     focus,
            "timestamp": time.time(),
        })
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    # ── Async internals (run inside the background event loop) ───────────────

    async def _broadcast(self, payload: str) -> None:
        """Push *payload* to every live WebSocket and SSE client."""
        dead_ws: set = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead_ws.add(ws)
        self._ws_clients -= dead_ws

        dead_q: list = []
        for q in self._sse_queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead_q.append(q)
        for q in dead_q:
            try:
                self._sse_queues.remove(q)
            except ValueError:
                pass

    async def _ws_handler(self, request: "web.Request") -> "web.WebSocketResponse":
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        _log.debug("WS client connected: %s", request.remote)
        try:
            async for _ in ws:
                pass  # server-push only — discard any inbound frames
        finally:
            self._ws_clients.discard(ws)
            _log.debug("WS client disconnected: %s", request.remote)
        return ws

    async def _sse_handler(self, request: "web.Request") -> "web.StreamResponse":
        response = web.StreamResponse()
        response.headers.update({
            "Content-Type":                "text/event-stream; charset=utf-8",
            "Cache-Control":               "no-cache",
            "Connection":                  "keep-alive",
            "Access-Control-Allow-Origin": "*",
        })
        await response.prepare(request)
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._sse_queues.append(q)
        _log.debug("SSE client connected: %s", request.remote)
        try:
            while True:
                payload = await q.get()
                await response.write(f"data: {payload}\n\n".encode("utf-8"))
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            try:
                self._sse_queues.remove(q)
            except ValueError:
                pass
            _log.debug("SSE client disconnected: %s", request.remote)
        return response

    @staticmethod
    async def _cors_preflight(request: "web.Request") -> "web.Response":
        return web.Response(headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        })

    def _run(self) -> None:
        """Entry point for the background daemon thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        app = web.Application()
        app.router.add_get("/ws",     self._ws_handler)
        app.router.add_get("/events", self._sse_handler)
        app.router.add_route("OPTIONS", "/events", self._cors_preflight)

        runner = web.AppRunner(app, access_log=None)
        self._loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "0.0.0.0", WS_PORT)
        self._loop.run_until_complete(site.start())

        print(f"🌐 WebSocket server  : ws://localhost:{WS_PORT}/ws")
        print(f"🌐 SSE events stream : http://localhost:{WS_PORT}/events")
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.run_until_complete(runner.cleanup())
