#!/usr/bin/env python3
"""
AI-Waifu backend — combined runner.

Shares a single cv2.VideoCapture (via CameraManager) between:
  • PostureMonitor   — bad-posture detection & desktop notifications
  • HydrationTracker — sip detection & desktop notifications
  • FocusTracker     — head pose, gaze direction & face-presence monitoring

Run:
    python main.py [--debug] [--camera N]
    python main.py --posture-only [--debug]
    python main.py --hydration-only [--debug]
    python main.py --focus-only [--debug]
"""

import argparse
import sys
import os
import threading

# Allow sibling-package imports (posture/, hydration/)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from camera_manager import CameraManager

sys.path.insert(0, os.path.join(_HERE, "posture"))
sys.path.insert(0, os.path.join(_HERE, "hydration"))
sys.path.insert(0, os.path.join(_HERE, "focus"))

from posture_monitor import PostureMonitor          # noqa: E402
from hydration_tracker import HydrationTracker      # noqa: E402
from focus_tracker import FocusTracker              # noqa: E402
from ws_notifier import WsNotifier                  # noqa: E402


def _score_reporter(
    posture_mod, hydration_mod, focus_mod,
    notifier, interval: int, stop_evt: threading.Event,
) -> None:
    """Broadcast a score snapshot every *interval* seconds until stopped."""
    while not stop_evt.wait(interval):
        p = posture_mod.get_score()   if posture_mod   else None
        h = hydration_mod.get_score() if hydration_mod else None
        f = focus_mod.get_score()     if focus_mod     else None
        notifier.notify_scores(p, h, f)


def main(
    debug: bool = False,
    camera_index: int = 0,
    enable_posture: bool = True,
    enable_hydration: bool = True,
    enable_focus: bool = True,
) -> None:
    modules: list = []

    # ── Start WebSocket / SSE notification server ─────────────────────────────
    notifier = WsNotifier()
    notifier.start()

    # ── Instantiate and open modules ─────────────────────────────────────────
    posture = hydration = focus = None

    if enable_posture:
        posture = PostureMonitor(debug=debug, notifier=notifier)
        posture.open()
        modules.append(posture)

    if enable_hydration:
        hydration = HydrationTracker(debug=debug, notifier=notifier)
        hydration.open()
        modules.append(hydration)

    if enable_focus:
        focus = FocusTracker(debug=debug, notifier=notifier)
        focus.open()
        modules.append(focus)

    if not modules:
        print("⚠️  No modules enabled — exiting.")
        notifier.stop()
        return

    # ── Single shared camera ──────────────────────────────────────────────────
    cam = CameraManager(camera_index=camera_index)
    for mod in modules:
        cam.register(mod.on_frame)

    print(f"\n🚀 Running {len(modules)} module(s) on camera {camera_index}…")
    print("   Press Ctrl+C to stop.\n")

    _stop_scores = threading.Event()
    threading.Thread(
        target=_score_reporter,
        args=(posture, hydration, focus, notifier, 1, _stop_scores),
        daemon=True, name="ScoreReporter",
    ).start()

    # Send an immediate snapshot so clients don't wait 10 s for the first update
    notifier.notify_scores(
        posture.get_score()   if posture   else None,
        hydration.get_score() if hydration else None,
        focus.get_score()     if focus     else None,
    )

    try:
        cam.start()   # blocks until stop() or KeyboardInterrupt
    except KeyboardInterrupt:
        print("\n\n⏸️  Stopping…")
    finally:
        cam.stop()
        for mod in modules:
            mod.close()
        _stop_scores.set()
        notifier.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI-Waifu backend — posture + hydration on one camera"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Keep video windows open after calibration",
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index (default: 0)",
    )
    parser.add_argument(
        "--posture-only", action="store_true",
        help="Run only the posture monitor",
    )
    parser.add_argument(
        "--hydration-only", action="store_true",
        help="Run only the hydration tracker",
    )
    parser.add_argument(
        "--focus-only", action="store_true",
        help="Run only the focus tracker",
    )
    parser.add_argument(
        "--no-focus", action="store_true",
        help="Disable the focus tracker",
    )
    parser.add_argument(
        "--no-posture", action="store_true",
        help="Disable the posture monitor",
    )
    parser.add_argument(
        "--no-hydration", action="store_true",
        help="Disable the hydration tracker",
    )
    args = parser.parse_args()

    enable_posture   = not args.no_posture   and not args.hydration_only and not args.focus_only
    enable_hydration = not args.no_hydration and not args.posture_only   and not args.focus_only
    enable_focus     = not args.no_focus     and not args.posture_only   and not args.hydration_only

    try:
        main(
            debug=args.debug,
            camera_index=args.camera,
            enable_posture=enable_posture,
            enable_hydration=enable_hydration,
            enable_focus=enable_focus,
        )
    except KeyboardInterrupt:
        print("\n\n👋 Bye!")
