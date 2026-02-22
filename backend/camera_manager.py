#!/usr/bin/env python3
"""
CameraManager — owns the single cv2.VideoCapture instance and fans frames
out to any number of registered subscriber callbacks.

Usage
-----
    manager = CameraManager(camera_index=0)
    manager.register(my_callback)          # callback(frame: np.ndarray, ts_ms: int)
    manager.start()                        # blocks; call stop() from another thread
                                           # or send KeyboardInterrupt
    manager.stop()
"""

import time
import threading
from typing import Callable

import cv2
import numpy as np

# Type alias for a frame callback: receives (frame, timestamp_ms)
FrameCallback = Callable[[np.ndarray, int], None]


class CameraManager:
    """
    Owns one cv2.VideoCapture and delivers frames to all registered callbacks.

    Each callback is called synchronously in the capture loop thread, so
    callbacks should be fast (or hand work off to their own threads).

    Parameters
    ----------
    camera_index : int
        Index passed to cv2.VideoCapture (default 0).
    target_fps : int
        Target capture / delivery rate.  The loop sleeps to approximate this
        rate; it does *not* guarantee exact timing.
    flip_horizontal : bool
        Mirror the frame before delivery (mirrors like a webcam — default True).
    """

    def __init__(
        self,
        camera_index: int = 0,
        target_fps: int = 30,
        flip_horizontal: bool = True,
    ):
        self._camera_index = camera_index
        self._target_fps = target_fps
        self._flip = flip_horizontal

        self._callbacks: list[FrameCallback] = []
        self._lock = threading.Lock()

        self._cap: cv2.VideoCapture | None = None
        self._running = False
        self._frame_count = 0

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, callback: FrameCallback) -> None:
        """Add a frame callback.  May be called before or after start()."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister(self, callback: FrameCallback) -> None:
        """Remove a previously registered callback."""
        with self._lock:
            self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Open the camera and enter the capture loop (blocking).

        Returns when stop() is called or the camera stops producing frames.
        """
        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"CameraManager: could not open camera index {self._camera_index}"
            )

        print(f"📷 Camera {self._camera_index} opened ({self._target_fps} fps target)")
        self._running = True
        self._frame_count = 0
        frame_interval = 1.0 / self._target_fps

        try:
            while self._running:
                t0 = time.time()

                ret, frame = self._cap.read()
                if not ret:
                    print("⚠️  CameraManager: failed to read frame — stopping.")
                    break

                if self._flip:
                    frame = cv2.flip(frame, 1)

                ts_ms = int(self._frame_count * (1000 / self._target_fps))
                self._frame_count += 1

                # Deliver to all callbacks (snapshot the list under lock)
                with self._lock:
                    callbacks = list(self._callbacks)

                for cb in callbacks:
                    try:
                        cb(frame, ts_ms)
                    except Exception as exc:  # noqa: BLE001
                        print(f"⚠️  CameraManager: callback {cb} raised {exc}")

                # Throttle to target FPS
                elapsed = time.time() - t0
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def stop(self) -> None:
        """Signal the capture loop to stop (thread-safe)."""
        self._running = False

    def _cleanup(self) -> None:
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        print("📷 Camera released.")

    # ── Context manager support ───────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()
        if self._cap is not None:
            self._cleanup()
