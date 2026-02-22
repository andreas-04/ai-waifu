#!/usr/bin/env python3
"""
Focus Tracker — head pose, gaze direction, and face-presence monitoring.

Tech stack: OpenCV · MediaPipe FaceLandmarker (tasks API, VIDEO mode) · NumPy

Signals
-------
  Face Presence   : Is someone at the desk at all?
  Head Pose       : Yaw / pitch / roll extracted from the facial transformation
                    matrix provided by FaceLandmarker.  Flags "looking away"
                    when yaw or pitch exceed configurable degree thresholds.
  Gaze Direction  : Left/right and up/down gaze computed from FaceLandmarker
                    blendshapes (eyeLookIn/Out/Up/Down for both eyes).
                    Flags off-screen gaze when the combined score exceeds
                    configurable thresholds.

FocusState (updated every frame)
---------------------------------
  face_present   bool    – True when a face is detected
  head_yaw       float   – degrees, +right / −left (from viewer's perspective)
  head_pitch     float   – degrees, +down  / −up
  head_roll      float   – degrees, +clockwise tilt
  gaze_h         float   – −1 = far left, +1 = far right
  gaze_v         float   – −1 = far up,   +1 = far down
  looking_away   bool    – True when any signal fires
  away_reason    str     – human-readable description of what triggered the flag

Notifications
-------------
  Person absent for > ABSENT_NOTIFY_S  → "Are you still there?"
  Looking away   for > AWAY_NOTIFY_S   → "Focus up!"

Run standalone:
    python focus_tracker.py [--debug] [--camera N]
"""

import os
import sys
import time
import math
import platform
import subprocess
import argparse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import mediapipe as mp

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Head-pose thresholds (degrees).
# Increase to make the detector less sensitive.
HEAD_YAW_THRESHOLD   = 25.0   # horizontal turn left/right
HEAD_PITCH_THRESHOLD = 20.0   # nodding up/down

# Gaze thresholds (blendshape score 0–1).
# Each score is the average of both eyes' corresponding blendshape.
GAZE_SIDE_THRESHOLD = 0.80    # eyeLookIn / eyeLookOut
GAZE_VERT_THRESHOLD = 0.85    # eyeLookUp / eyeLookDown

# Duration (seconds) a condition must persist before a notification fires.
ABSENT_NOTIFY_S        = 15.0
AWAY_NOTIFY_S          = 20.0
NOTIFICATION_COOLDOWN_S = 30.0  # min gap between notifications of the same kind

# Model download URL
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)


# ──────────────────────────────────────────────────────────────────────────────
# Data class
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FocusState:
    """Snapshot of the current focus status, updated on every frame."""

    face_present: bool  = False
    head_yaw:     float = 0.0   # degrees: +right / −left (viewer's POV)
    head_pitch:   float = 0.0   # degrees: +down  / −up
    head_roll:    float = 0.0   # degrees: +clockwise tilt
    gaze_h:       float = 0.0   # −1 = far left,  +1 = far right
    gaze_v:       float = 0.0   # −1 = far up,    +1 = far down
    looking_away: bool  = False
    away_reason:  str   = ""


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _rotation_matrix_to_euler(R: np.ndarray) -> tuple[float, float, float]:
    """
    Decompose a 3×3 rotation matrix into (yaw, pitch, roll) in degrees.

    Convention: XYZ extrinsic (Rx · Ry · Rz).
      yaw   – rotation around Y (left/right head turn)
      pitch – rotation around X (up/down head nod)
      roll  – rotation around Z (head tilt / shoulder dip)

    Based on the standard Tait–Bryan XYZ decomposition used by OpenCV.
    """
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = math.atan2( R[2, 1], R[2, 2])  # Rx
        yaw   = math.atan2(-R[2, 0], sy)        # Ry
        roll  = math.atan2( R[1, 0], R[0, 0])  # Rz
    else:
        pitch = math.atan2(-R[1, 2], R[1, 1])
        yaw   = math.atan2(-R[2, 0], sy)
        roll  = 0.0

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def _blendshape_score(blendshapes, name: str) -> float:
    """Return the score of a named blendshape, 0.0 if not found."""
    for bs in blendshapes:
        if bs.category_name == name:
            return float(bs.score)
    return 0.0


def _compute_gaze(blendshapes) -> tuple[float, float]:
    """
    Compute normalised gaze direction (h, v) in [−1, +1] from blendshapes.

    Horizontal (h):
      +1 = looking to viewer's right   −1 = looking to viewer's left
      With the frame already mirrored by CameraManager, MediaPipe's
      "right" eye corresponds to the viewer's right side of the image.
      A rightward gaze means: right eye looks *inward* (toward nose) and
      left eye looks *outward* (away from nose).

    Vertical (v):
      +1 = looking down   −1 = looking up
    """
    look_right = (
        _blendshape_score(blendshapes, "eyeLookInRight") +
        _blendshape_score(blendshapes, "eyeLookOutLeft")
    ) / 2.0

    look_left = (
        _blendshape_score(blendshapes, "eyeLookOutRight") +
        _blendshape_score(blendshapes, "eyeLookInLeft")
    ) / 2.0

    look_down = (
        _blendshape_score(blendshapes, "eyeLookDownRight") +
        _blendshape_score(blendshapes, "eyeLookDownLeft")
    ) / 2.0

    look_up = (
        _blendshape_score(blendshapes, "eyeLookUpRight") +
        _blendshape_score(blendshapes, "eyeLookUpLeft")
    ) / 2.0

    return (look_right - look_left), (look_down - look_up)


def _draw_overlay(frame: np.ndarray, state: FocusState) -> None:
    """Render the focus-state HUD onto *frame* (in-place)."""
    h, w = frame.shape[:2]
    pad = 14

    # ── Face presence badge ───────────────────────────────────────────────────
    if state.face_present:
        face_color, face_label = (0, 210, 0), "● Face: Present"
    else:
        face_color, face_label = (0, 60, 220), "● Face: Absent"

    cv2.putText(frame, face_label,
                (pad, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, face_color, 2)

    if not state.face_present:
        return

    # ── Head pose row ─────────────────────────────────────────────────────────
    yaw_col   = (0, 60, 220) if abs(state.head_yaw)   > HEAD_YAW_THRESHOLD   else (180, 180, 180)
    pitch_col = (0, 60, 220) if abs(state.head_pitch) > HEAD_PITCH_THRESHOLD else (180, 180, 180)

    pose_text = (
        f"Head — Yaw: {state.head_yaw:+.1f}°  "
        f"Pitch: {state.head_pitch:+.1f}°  "
        f"Roll: {state.head_roll:+.1f}°"
    )
    cv2.putText(frame, pose_text,
                (pad, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)

    # Colour-coded Yaw / Pitch indicator boxes
    yaw_str   = f"Yaw {state.head_yaw:+.0f}°"
    pitch_str = f"Pitch {state.head_pitch:+.0f}°"
    cv2.putText(frame, yaw_str,   (pad,       86), cv2.FONT_HERSHEY_SIMPLEX, 0.52, yaw_col,   2)
    cv2.putText(frame, pitch_str, (pad + 120, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.52, pitch_col, 2)

    # ── Gaze row ──────────────────────────────────────────────────────────────
    gh_col = (0, 60, 220) if abs(state.gaze_h) > GAZE_SIDE_THRESHOLD else (180, 180, 180)
    gv_col = (0, 60, 220) if abs(state.gaze_v) > GAZE_VERT_THRESHOLD else (180, 180, 180)

    cv2.putText(frame, f"Gaze H: {state.gaze_h:+.2f}",
                (pad,       110), cv2.FONT_HERSHEY_SIMPLEX, 0.52, gh_col, 2)
    cv2.putText(frame, f"Gaze V: {state.gaze_v:+.2f}",
                (pad + 160, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.52, gv_col, 2)

    # ── Gaze compass (mini visualisation) ────────────────────────────────────
    cx, cy, radius = w - 55, 55, 40
    cv2.circle(frame, (cx, cy), radius, (80, 80, 80), 1)
    cv2.line(frame, (cx - radius, cy), (cx + radius, cy), (60, 60, 60), 1)
    cv2.line(frame, (cx, cy - radius), (cx, cy + radius), (60, 60, 60), 1)
    dot_x = cx + int(state.gaze_h * radius * 0.85)
    dot_y = cy + int(state.gaze_v * radius * 0.85)
    dot_color = (0, 60, 220) if state.looking_away else (0, 210, 0)
    cv2.circle(frame, (dot_x, dot_y), 7, dot_color, -1)
    cv2.putText(frame, "gaze", (cx - 14, cy + radius + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 120, 120), 1)

    # ── Attention status banner ───────────────────────────────────────────────
    if state.looking_away:
        banner_color = (0, 60, 220)
        banner_text  = f"DISTRACTED — {state.away_reason}"
    else:
        banner_color = (0, 210, 0)
        banner_text  = "Focused"

    cv2.putText(frame, banner_text,
                (pad, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.8, banner_color, 2)


def _send_notification(title: str, message: str) -> None:
    """Send a desktop notification (macOS · Linux · Windows)."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"',
            ])
        elif system == "Linux":
            subprocess.Popen(["notify-send", title, message])
        elif system == "Windows":
            print(f"[NOTIFICATION] {title}: {message}")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────# Report generator
# ───────────────────────────────────────────────────────────────────────────────

def generate_focus_report(focus_log: list, session_start) -> None:
    """Generate a visual report of focus / distraction data."""
    if len(focus_log) < 2:
        print("Not enough focus data to generate report.")
        return

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.dates import DateFormatter
    except ImportError:
        print("\n⚠️  matplotlib not installed. Skipping focus report.")
        print("   Install with: pip install matplotlib")
        return

    timestamps     = [e['time']       for e in focus_log]
    focus_scores   = [1 if e['is_focused'] else 0 for e in focus_log]
    reasons        = [e['reason']     for e in focus_log]

    total_time_min = (timestamps[-1] - timestamps[0]).total_seconds() / 60.0
    focused_pct    = sum(focus_scores) / len(focus_scores) * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(
        f'Focus Session — {session_start.strftime("%Y-%m-%d %H:%M")}',
        fontsize=14, fontweight='bold',
    )

    # ── Top: focused / distracted timeline ────────────────────────────────
    dot_colors = ['#44bb44' if s else '#ff4444' for s in focus_scores]
    ax1.scatter(timestamps, focus_scores, c=dot_colors, s=8, alpha=0.5)
    ax1.fill_between(timestamps, 0, focus_scores,
                     alpha=0.25, color='#44bb44', label='Focused')
    ax1.fill_between(timestamps, focus_scores, 1,
                     alpha=0.25, color='#ff4444', label='Distracted')
    ax1.set_ylabel('Focus Status', fontsize=11)
    ax1.set_yticks([0, 1])
    ax1.set_yticklabels(['Distracted', 'Focused'])
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    ax1.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

    # ── Bottom: distraction-reason frequency ─────────────────────────────
    # Split compound reasons (semicolon-delimited) into individual signals
    reason_counts: dict[str, int] = {}
    for score, reason in zip(focus_scores, reasons):
        if score == 0 and reason:
            for part in reason.split(';'):
                part = part.strip()
                # Normalise to signal category (strip the numeric suffix)
                if 'Head turned' in part:  cat = 'Head turned'
                elif 'Head tilted' in part: cat = 'Head tilted'
                elif 'Eyes right' in part or 'Eyes left' in part: cat = 'Eyes side'
                elif 'Eyes down' in part:  cat = 'Eyes down'
                elif 'Eyes up' in part:    cat = 'Eyes up'
                else:                      cat = part
                reason_counts[cat] = reason_counts.get(cat, 0) + 1

    if reason_counts:
        cats   = list(reason_counts.keys())
        counts = list(reason_counts.values())
        bars   = ax2.barh(cats, counts, color='#ff6b6b')
        ax2.set_xlabel('Number of Frames', fontsize=11)
        ax2.set_ylabel('Distraction Signal', fontsize=11)
        ax2.set_title('Distraction Breakdown', fontsize=12)
        ax2.grid(True, alpha=0.3, axis='x')
        for bar in bars:
            w = bar.get_width()
            ax2.text(w, bar.get_y() + bar.get_height() / 2,
                     f'{int(w):,}', ha='left', va='center', fontsize=9)
    else:
        ax2.text(0.5, 0.5, 'No distractions detected!\n✓ Perfect session',
                 ha='center', va='center', fontsize=14, color='green',
                 transform=ax2.transAxes)
        ax2.axis('off')

    stats_text = (
        f"Session Duration: {total_time_min:.1f} min  |  "
        f"Focused: {focused_pct:.1f}%  |  "
        f"Samples: {len(focus_log):,}"
    )
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename   = os.path.join(script_dir, 'focusreport.png')
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n📊 Focus report saved: {filename}")
    print(f"   Duration: {total_time_min:.1f} min  |  Focused: {focused_pct:.1f}%  |  Samples: {len(focus_log):,}")
    if reason_counts:
        top = max(reason_counts, key=reason_counts.get)
        print(f"   Most common distraction: {top}")


# ───────────────────────────────────────────────────────────────────────────────# FocusTracker
# ──────────────────────────────────────────────────────────────────────────────

class FocusTracker:
    """
    Stateful focus tracker that processes frames delivered via on_frame().

    Lifecycle
    ---------
        tracker = FocusTracker(debug=True)
        tracker.open()                         # load MediaPipe model
        camera_manager.register(tracker.on_frame)
        # ... run camera loop ...
        tracker.close()                        # release resources

    State
    -----
        Read tracker.state (FocusState) at any time for the latest snapshot.
    """

    def __init__(self, debug: bool = False, notifier=None):
        self.debug = debug
        self._notifier = notifier
        self._detector = None
        self._state = FocusState()
        self._window_visible = debug

        # Session logging
        self._session_start = datetime.now()
        self._focus_log: list[dict] = []   # {time, is_focused, reason}

        # Notification timers
        self._face_absent_since:  Optional[float] = None
        self._looking_away_since: Optional[float] = None
        self._last_absent_notification  = 0.0
        self._last_away_notification    = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> FocusState:
        """Most recent FocusState snapshot (thread-safe read)."""
        return self._state

    def open(self) -> None:
        """Download (if needed) and load the MediaPipe FaceLandmarker model."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, "face_landmarker.task")

        if not os.path.exists(model_path):
            print("📥 Downloading face-landmarker model (one-time setup)…")
            urllib.request.urlretrieve(_MODEL_URL, model_path)
            print(f"   Saved → {model_path}")

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._detector = mp.tasks.vision.FaceLandmarker.create_from_options(options)

        print("╔══════════════════════════════════════════╗")
        print("║        Focus Tracker — Active            ║")
        print("╠══════════════════════════════════════════╣")
        print("║  Signals: Face · Head Pose · Gaze        ║")
        if self.debug:
            print("║  DEBUG: window open  |  q = quit         ║")
        else:
            print("║  Running silently in background          ║")
        print("╚══════════════════════════════════════════╝")

    def close(self) -> None:
        """Release the MediaPipe detector, any open windows, and save report."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        try:
            cv2.destroyWindow("Focus Tracker")
        except Exception:
            pass
        if self._focus_log:
            generate_focus_report(self._focus_log, self._session_start)
        print("\n👋 FocusTracker closed.")

    # ── Score ─────────────────────────────────────────────────────────────────

    def get_score(self) -> int:
        """
        Return a 0-100 focus score over the full session lifetime.

        = (focused frames / total frames) × 100.
        Returns 100 (neutral) when there is no data yet.
        """
        if not self._focus_log:
            return 100
        focused = sum(1 for e in self._focus_log if e["is_focused"])
        return int(focused / len(self._focus_log) * 100)

    # ── Frame callback ────────────────────────────────────────────────────────

    def on_frame(self, frame: np.ndarray, ts_ms: int) -> None:
        """
        Called by CameraManager for every captured frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR frame, already horizontally flipped by CameraManager.
        ts_ms : int
            Monotonic timestamp in milliseconds (required by VIDEO mode).
        """
        if self._detector is None:
            return

        display = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self._detector.detect_for_video(mp_image, ts_ms)

        state = FocusState()
        now   = time.time()

        if results.face_landmarks:
            # ── Face present ─────────────────────────────────────────────────
            state.face_present   = True
            self._face_absent_since = None  # reset absence timer

            # ── Head pose from 4×4 facial transformation matrix ──────────────
            if results.facial_transformation_matrixes:
                mat = np.array(
                    results.facial_transformation_matrixes[0]
                ).reshape(4, 4)
                R = mat[:3, :3]
                yaw, pitch, roll = _rotation_matrix_to_euler(R)
                state.head_yaw   = yaw
                state.head_pitch = pitch
                state.head_roll  = roll

            # ── Gaze direction from blendshapes ──────────────────────────────
            if results.face_blendshapes:
                state.gaze_h, state.gaze_v = _compute_gaze(
                    results.face_blendshapes[0]
                )

            # ── Evaluate "looking away" signals ──────────────────────────────
            reasons: list[str] = []

            if abs(state.head_yaw) > HEAD_YAW_THRESHOLD:
                direction = "right" if state.head_yaw > 0 else "left"
                reasons.append(f"Head turned {direction} ({state.head_yaw:+.0f}°)")

            if abs(state.head_pitch) > HEAD_PITCH_THRESHOLD:
                direction = "down" if state.head_pitch > 0 else "up"
                reasons.append(f"Head tilted {direction} ({state.head_pitch:+.0f}°)")

            if abs(state.gaze_h) > GAZE_SIDE_THRESHOLD:
                direction = "right" if state.gaze_h > 0 else "left"
                reasons.append(f"Eyes {direction} ({state.gaze_h:+.2f})")

            if state.gaze_v > GAZE_VERT_THRESHOLD:
                reasons.append(f"Eyes down ({state.gaze_v:+.2f})")
            elif state.gaze_v < -GAZE_VERT_THRESHOLD:
                reasons.append(f"Eyes up ({state.gaze_v:+.2f})")

            if reasons:
                state.looking_away = True
                state.away_reason  = "; ".join(reasons)

                if self._looking_away_since is None:
                    self._looking_away_since = now
                elif (
                    now - self._looking_away_since    >= AWAY_NOTIFY_S
                    and now - self._last_away_notification >= NOTIFICATION_COOLDOWN_S
                ):
                    detail = f"👀 Distracted for {AWAY_NOTIFY_S:.0f}s: {state.away_reason}"
                    print(detail)
                    _send_notification(
                        "Focus Alert 👀",
                        f"You've been distracted! ({state.away_reason})",
                    )
                    if self._notifier:
                        self._notifier.notify(
                            "focus", "warning", "Bad focus", detail
                        )
                    self._last_away_notification = now
                    self._looking_away_since     = now  # reset so cooldown applies
            else:
                state.looking_away      = False
                self._looking_away_since = None

        else:
            # ── No face detected ─────────────────────────────────────────────
            state.face_present      = False
            self._looking_away_since = None

            if self._face_absent_since is None:
                self._face_absent_since = now
            elif (
                now - self._face_absent_since          >= ABSENT_NOTIFY_S
                and now - self._last_absent_notification >= NOTIFICATION_COOLDOWN_S
            ):
                elapsed = now - self._face_absent_since
                detail = f"🚶 Face absent for {elapsed:.0f}s"
                print(detail)
                _send_notification(
                    "Focus Alert 🚶",
                    "Are you still there? Come back!",
                )
                if self._notifier:
                    self._notifier.notify(
                        "focus", "warning", "Face absent", detail
                    )
                self._last_absent_notification = now
                self._face_absent_since        = now  # reset so cooldown applies

        self._state = state

        # Log every frame for end-of-session report
        if state.face_present:
            self._focus_log.append({
                "time":       datetime.now(),
                "is_focused": not state.looking_away,
                "reason":     state.away_reason,
            })

        # ── Debug window ─────────────────────────────────────────────────────
        if self._window_visible:
            _draw_overlay(display, state)
            cv2.imshow("Focus Tracker", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                raise KeyboardInterrupt


# ──────────────────────────────────────────────────────────────────────────────
# Standalone entry point
# ──────────────────────────────────────────────────────────────────────────────

def main(debug: bool = False, camera_index: int = 0) -> None:
    """Run FocusTracker standalone (owns its own CameraManager)."""
    _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from camera_manager import CameraManager

    tracker = FocusTracker(debug=debug)
    tracker.open()

    cam = CameraManager(camera_index=camera_index)
    cam.register(tracker.on_frame)

    try:
        cam.start()
    except KeyboardInterrupt:
        print("\n\n⏸️  Stopping focus tracker…")
    finally:
        cam.stop()
        tracker.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Focus Tracker — head pose, gaze direction, face presence"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Keep video window open for debugging",
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index (default: 0)",
    )
    args = parser.parse_args()
    try:
        main(debug=args.debug, camera_index=args.camera)
    except KeyboardInterrupt:
        print("\n\n👋 Focus tracker stopped.")
