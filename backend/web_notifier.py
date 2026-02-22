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

import asyncio
import json
import os
import random
import threading
import urllib.request
from text_to_speech import gen_audio

try:
    from aiohttp import ClientSession, WSMsgType, ClientConnectorError
except ImportError:
    raise SystemExit("aiohttp is required — run: pip install aiohttp")

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC_AUDIO = os.path.normpath(os.path.join(_HERE, "..", "Website", "static", "notification.mp3"))

_notifier = None

def _get_current_voice() -> str:
    """Fetch the currently selected voice from the Flask settings API."""
    try:
        with urllib.request.urlopen("http://localhost:5001/api/settings", timeout=1) as resp:
            data = json.loads(resp.read())
            return data.get("selected_voice", "Jessica")
    except Exception:
        return "Jessica"

def send_notification(message: str) -> None:
    voice = _get_current_voice()
    success = gen_audio(message, voice=voice, output_path=_STATIC_AUDIO)
    if success and _notifier is not None:
        _notifier.notify_audio()

def get_distracted_message():
    messages = [
        "Woah there! Make sure to stay focused and avoid distractions. You've got this!",
        "Time to buckle down and get some work done! Stay focused and keep those distractions at bay.",
        "Focus mode activated! Avoid distractions and keep your eyes on the prize. You can do it!",
        "Distraction alert! Take a deep breath, refocus, and get back to work. Go get 'em!",
        "Stay on track! Avoid distractions and keep pushing forward. You've got the power to succeed!",
        "Focus up! Distractions can wait, but your goals can't. Stay determined and keep moving forward!",
        "Distraction-free zone! Take a moment to refocus and get back to work. You've got this!",
        "Time to get in the zone! Avoid distractions and keep your mind on the task at hand.",
    ]

    return random.choice(messages)

def get_bad_posture_message():
    messages = [
        "Time to check your posture! Sit up straight and align your spine.",
        "Posture check! Adjust your chair and sit tall for better focus.",
        "Don't forget to maintain good posture! Your back will thank you.",
        "Posture reminder! Keep your shoulders relaxed and your back straight.",
        "Sit up straight! Good posture can boost your energy and focus.",
        "Posture check! Make sure you're sitting comfortably and upright.",
        "Remember to maintain good posture for better health and productivity!",
        "Posture alert! Take a moment to adjust your seating position.",
        "Keep that posture in check! A straight back can improve circulation.",
        "Posture reminder! Align your head, neck, and spine for comfort."
    ]

    return random.choice(messages)

def get_drink_water_message():
    messages = [
        "Time to drink some water! Stay hydrated!",
        "Don't forget to take a sip of water! Your body will thank you!",
        "Hydration check! Grab a glass of water and refresh yourself!",
        "Water break! Take a moment to hydrate and boost your focus!",
        "Stay refreshed! Drink some water to keep your mind sharp!",
        "Your body's asking for water! Take a sip now.",
        "Don't forget to drink water — your future self will thank you!",
        "Hydration check! When did you last drink water?",
        "A little water goes a long way. Grab a glass!",
        "Stay refreshed! Have you had some water recently?",
        "Water break! Your body will love you for it.",
        "Keep your energy up — drink some water.",
        "H2O time! Let's keep that hydration up.",
        "Remember, water is essential. Have you had enough today?"
    ]

    return random.choice(messages)

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

                        message = ""
                        if "module" in data:
                            if data["module"] == "posture" and data["level"] == "warning":
                                message = get_bad_posture_message()
                            elif data["module"] == "hydration" and data["level"] == "warning":
                                message = get_drink_water_message()
                            elif data["module"] == "focus" and data["level"] == "warning":
                                message = get_distracted_message()
                        print(data)
                        print()

                        if message:
                            send_notification(message)
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
                                print(data)
                                print()
                            except json.JSONDecodeError:
                                print(f"[sse/raw] {payload}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

async def run(host: str = "localhost", port: int = 8765, mode: str = "ws") -> None:
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

def start(notifier=None) -> None:
    global _notifier
    _notifier = notifier
    threading.Thread(
        target=lambda: asyncio.run(run()),
        daemon=True,
        name="WebNotifier",
    ).start()
