#!/usr/bin/env python3
"""
Test client for the AI-Waifu notification server.

Modes
-----
  ws   — raw WebSocket (shows HTTP 101 upgrade handshake)
  sse  — Server-Sent Events  (http://.../events)
  both — run WS and SSE listeners in parallel

Usage
-----
    python test_ws_client.py [--host HOST] [--port PORT] [--mode ws|sse|both]
"""

import argparse
import asyncio
import json
from datetime import datetime

try:
    from aiohttp import ClientSession, WSMsgType, ClientConnectorError
except ImportError:
    raise SystemExit("aiohttp is required — run: pip install aiohttp")

# ── Colour helpers (no extra deps) ───────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_COLORS = {
    "info":    "\033[36m",   # cyan
    "warning": "\033[33m",   # yellow
    "alert":   "\033[31m",   # red
}
_MODULE_COLORS = {
    "posture":   "\033[35m",  # magenta
    "hydration": "\033[34m",  # blue
    "focus":     "\033[32m",  # green
}
_TRANSPORT_COLORS = {
    "ws":  "\033[32m",   # green
    "sse": "\033[34m",   # blue
}


def _format(msg: dict, transport: str = "ws") -> str:
    level   = msg.get("level", "info")
    module  = msg.get("module", "?")
    simple  = msg.get("simple", "")
    detail  = msg.get("detail", "")
    ts      = msg.get("timestamp", 0)

    time_str   = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
    lvl_color  = _COLORS.get(level, "")
    mod_color  = _MODULE_COLORS.get(module, "")
    t_color    = _TRANSPORT_COLORS.get(transport, "")

    return (
        f"{_BOLD}{time_str}{_RESET}  "
        f"{t_color}[{transport:>3}]{_RESET}  "
        f"{mod_color}[{module:>9}]{_RESET}  "
        f"{lvl_color}{level:<7}{_RESET}  "
        f"{_BOLD}{simple}{_RESET}\n"
        f"           {_DIM}{detail}{_RESET}"
    )


# ── WebSocket listener ────────────────────────────────────────────────────────

async def listen_ws(host: str, port: int) -> None:
    url = f"ws://{host}:{port}/ws"
    http_url = f"http://{host}:{port}/ws"
    print(f"[WS]  Connecting to {url}")
    print(f"      HTTP GET {http_url}  →  expecting 101 Switching Protocols\n")

    async with ClientSession() as session:
        async with session.ws_connect(
            url,
            headers={"User-Agent": "ai-waifu-test-client/1.0"},
        ) as ws:
            resp = ws._response  # the underlying HTTP response
            status  = resp.status   # 101
            headers = resp.headers

            print(f"      HTTP {status} {resp.reason}")
            print(f"      Upgrade:    {headers.get('Upgrade', '—')}")
            print(f"      Connection: {headers.get('Connection', '—')}")
            ws_accept = headers.get('Sec-WebSocket-Accept', '—')
            print(f"      Sec-WebSocket-Accept: {ws_accept}")
            print()
            print("✅ [WS]  Handshake OK — waiting for messages (Ctrl+C to quit)\n")

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        print(_format(data, "ws"))
                        print()
                    except json.JSONDecodeError:
                        print(f"[ws/raw] {msg.data}\n")
                elif msg.type == WSMsgType.ERROR:
                    print(f"⚠️  [WS] error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSED:
                    print("🔌 [WS] connection closed by server.")
                    break


# ── SSE listener ──────────────────────────────────────────────────────────────

async def listen_sse(host: str, port: int) -> None:
    url = f"http://{host}:{port}/events"
    print(f"[SSE] Connecting to {url}\n")

    async with ClientSession() as session:
        async with session.get(url) as resp:
            ct = resp.headers.get("Content-Type", "—")
            print(f"      HTTP {resp.status} {resp.reason}")
            print(f"      Content-Type: {ct}")
            print(f"      Cache-Control: {resp.headers.get('Cache-Control', '—')}")
            print()

            if resp.status != 200:
                print(f"❌ [SSE] unexpected status {resp.status}")
                return

            print("✅ [SSE] Stream open — waiting for events (Ctrl+C to quit)\n")

            buffer = ""
            async for chunk in resp.content.iter_any():
                buffer += chunk.decode("utf-8")
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)
                    for line in event.splitlines():
                        if line.startswith("data:"):
                            payload = line[len("data:"):].strip()
                            try:
                                data = json.loads(payload)
                                print(_format(data, "sse"))
                                print()
                            except json.JSONDecodeError:
                                print(f"[sse/raw] {payload}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

async def run(host: str, port: int, mode: str) -> None:
    try:
        if mode == "ws":
            await listen_ws(host, port)
        elif mode == "sse":
            await listen_sse(host, port)
        else:  # both
            await asyncio.gather(
                listen_ws(host, port),
                listen_sse(host, port),
            )
    except ClientConnectorError as e:
        print(f"\n❌ Could not connect: {e}")
        print(f"   Is the backend running?  .venv/bin/python backend/main.py")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test client for AI-Waifu notifications"
    )
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8765,  help="Server port (default: 8765)")
    parser.add_argument(
        "--mode", choices=["ws", "sse", "both"], default="ws",
        help="Transport to use: ws (WebSocket), sse (HTTP SSE), both (default: ws)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.host, args.port, args.mode))
    except KeyboardInterrupt:
        print("\n👋 Disconnected.")


if __name__ == "__main__":
    main()
