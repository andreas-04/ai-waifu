#!/usr/bin/env python3
"""
Hydration Tracker — multi-signal sip detection via webcam.

Tech stack: OpenCV · MediaPipe Hands · MediaPipe Face Mesh · Ultralytics YOLO · NumPy
Run:  python hydration_tracker.py [--debug] [--no-yolo]

Signals (≥2 must co-fire within a ~2 s gesture window to confirm a sip):
  1. Wrist Visible             — MediaPipe Hands detects a wrist in the frame
  2. Object Near Mouth          — YOLOv8n bottle/cup detection (or contour fallback)
  3. Head Tilt (backward)       — Face Mesh nose-chin pitch estimation
"""

import time
import math
import os
import sys
import subprocess
import platform
import argparse
import urllib.request
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import mediapipe as mp

# ── Optional YOLO import ─────────────────────
try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
CALIBRATION_DURATION_S = 3.0          # seconds to average neutral head-tilt ratio
HEAD_TILT_THRESHOLD_DEG = 10.0        # backward tilt from baseline to fire signal
SIP_GESTURE_WINDOW_S = 2.0           # signals must co-occur within this window
SIP_COOLDOWN_S = 10.0                # minimum seconds between counted sips
SIGNAL_REQUIRED_COUNT = 3            # minimum signals for sip confirmation

# YOLO
YOLO_CONFIDENCE = 0.40
YOLO_CLASSES = {39: "bottle", 41: "cup"}   # COCO class IDs
MOUTH_ROI_EXPAND_PX = 100                  # expand mouth bbox for proximity check

# Contour-based fallback (Signal 2 without YOLO)
CONTOUR_MIN_AREA = 500
CONTOUR_MAX_AREA = 50_000

# Face Mesh landmark indices
FM_UPPER_LIP = 13
FM_LOWER_LIP = 14
FM_NOSE_TIP = 1
FM_CHIN = 152
FM_FOREHEAD = 10

# Hand landmark indices
HAND_WRIST = 0


# ──────────────────────────────────────────────
# Signal state tracker
# ──────────────────────────────────────────────
class SignalState:
    """Track the three binary signals and the timestamps they last fired."""

    def __init__(self):
        self.wrist_visible = False
        self.object_near_mouth = False
        self.head_tilted = False
        self.wrist_visible_time = 0.0
        self.object_near_mouth_time = 0.0
        self.head_tilted_time = 0.0

    # ── helpers ──
    def _is_active(self, flag: bool, ts: float, now: float) -> bool:
        return flag and (now - ts) < SIP_GESTURE_WINDOW_S

    def active_count(self, now: float) -> int:
        return sum([
            self._is_active(self.wrist_visible, self.wrist_visible_time, now),
            self._is_active(self.object_near_mouth, self.object_near_mouth_time, now),
            self._is_active(self.head_tilted, self.head_tilted_time, now),
        ])

    def active_labels(self, now: float) -> list[str]:
        labels: list[str] = []
        if self._is_active(self.wrist_visible, self.wrist_visible_time, now):
            labels.append("Wrist Visible")
        if self._is_active(self.object_near_mouth, self.object_near_mouth_time, now):
            labels.append("Object Near Mouth")
        if self._is_active(self.head_tilted, self.head_tilted_time, now):
            labels.append("Head Tilted")
        return labels

    def reset(self):
        """Clear all signals so every heuristic must re-trigger from scratch."""
        self.wrist_visible = False
        self.object_near_mouth = False
        self.head_tilted = False
        self.wrist_visible_time = 0.0
        self.object_near_mouth_time = 0.0
        self.head_tilted_time = 0.0


# ──────────────────────────────────────────────
# Signal 1 — Wrist Visible
# ──────────────────────────────────────────────
def check_wrist_visible(hand_landmarks_list: list) -> bool:
    """Return True when at least one hand (and therefore a wrist) is detected."""
    return len(hand_landmarks_list) > 0


# ──────────────────────────────────────────────
# Signal 2a — Object Near Mouth (YOLO)
# ──────────────────────────────────────────────
def check_object_near_mouth_yolo(
    yolo_model, frame: np.ndarray, face_landmarks,
    frame_w: int, frame_h: int,
) -> bool:
    """Run YOLOv8n and check for bottle/cup overlapping the mouth ROI."""
    if yolo_model is None or face_landmarks is None:
        return False

    upper_lip = face_landmarks[FM_UPPER_LIP]
    lower_lip = face_landmarks[FM_LOWER_LIP]
    mouth_cx = int((upper_lip.x + lower_lip.x) / 2.0 * frame_w)
    mouth_cy = int((upper_lip.y + lower_lip.y) / 2.0 * frame_h)

    roi_x1 = max(0, mouth_cx - MOUTH_ROI_EXPAND_PX)
    roi_y1 = max(0, mouth_cy - MOUTH_ROI_EXPAND_PX)
    roi_x2 = min(frame_w, mouth_cx + MOUTH_ROI_EXPAND_PX)
    roi_y2 = min(frame_h, mouth_cy + MOUTH_ROI_EXPAND_PX)

    results = yolo_model(frame, conf=YOLO_CONFIDENCE, verbose=False)
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id not in YOLO_CLASSES:
                continue
            bx1, by1, bx2, by2 = box.xyxy[0].cpu().numpy().astype(int)
            # Check rectangle overlap
            if bx1 < roi_x2 and bx2 > roi_x1 and by1 < roi_y2 and by2 > roi_y1:
                return True
    return False


# ──────────────────────────────────────────────
# Signal 2b — Object Near Mouth (contour fallback)
# ──────────────────────────────────────────────
def check_object_near_mouth_contour(
    frame: np.ndarray, face_landmarks, frame_w: int, frame_h: int,
) -> bool:
    """Contour-based heuristic: look for a sizeable object near the mouth."""
    if face_landmarks is None:
        return False

    upper_lip = face_landmarks[FM_UPPER_LIP]
    lower_lip = face_landmarks[FM_LOWER_LIP]
    mouth_cx = int((upper_lip.x + lower_lip.x) / 2.0 * frame_w)
    mouth_cy = int((upper_lip.y + lower_lip.y) / 2.0 * frame_h)

    roi_x1 = max(0, mouth_cx - MOUTH_ROI_EXPAND_PX)
    roi_y1 = max(0, mouth_cy - 30)
    roi_x2 = min(frame_w, mouth_cx + MOUTH_ROI_EXPAND_PX)
    roi_y2 = min(frame_h, mouth_cy + MOUTH_ROI_EXPAND_PX * 2)

    roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
    if roi.size == 0:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if CONTOUR_MIN_AREA < area < CONTOUR_MAX_AREA:
            return True
    return False


# ──────────────────────────────────────────────
# Signal 3 — Head Tilt (backward pitch)
# ──────────────────────────────────────────────
def compute_nose_ratio(face_landmarks) -> float:
    """
    Return the vertical position of the nose tip expressed as a ratio
    within the forehead→chin span.  Decreases when the head tilts back.
    """
    forehead = face_landmarks[FM_FOREHEAD]
    nose = face_landmarks[FM_NOSE_TIP]
    chin = face_landmarks[FM_CHIN]

    face_height = chin.y - forehead.y
    if abs(face_height) < 1e-6:
        return 0.0
    return (nose.y - forehead.y) / face_height


def check_head_tilt(face_landmarks, baseline_ratio: float) -> tuple[bool, float]:
    """
    Return (is_tilted, approx_tilt_degrees).

    Empirical mapping: a 0.02 change in nose-ratio ≈ 5° of pitch.
    """
    if face_landmarks is None:
        return False, 0.0

    current_ratio = compute_nose_ratio(face_landmarks)
    ratio_delta = baseline_ratio - current_ratio        # positive when tilting back
    approx_deg = ratio_delta * 250.0                    # rough linear mapping
    return approx_deg > HEAD_TILT_THRESHOLD_DEG, approx_deg


# ──────────────────────────────────────────────
# Notification helper
# ──────────────────────────────────────────────
def send_notification(title: str, message: str):
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


# ──────────────────────────────────────────────
# HUD overlay
# ──────────────────────────────────────────────
def draw_overlay(
    frame: np.ndarray,
    signals: SignalState,
    sip_count: int,
    calibrated: bool,
    calibrating: bool,
    cal_progress: float,
    tilt_deg: float,
    now: float,
):
    h, w = frame.shape[:2]

    # ── calibration bar ──
    if calibrating:
        bar_w, bar_h = 300, 30
        x0 = (w - bar_w) // 2
        y0 = h - 80
        cv2.rectangle(frame, (x0, y0), (x0 + bar_w, y0 + bar_h), (255, 255, 255), 2)
        fill = int(bar_w * cal_progress)
        cv2.rectangle(frame, (x0, y0), (x0 + fill, y0 + bar_h), (0, 200, 255), -1)
        cv2.putText(
            frame, "Calibrating... look straight ahead",
            (x0 - 50, y0 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2,
        )
        return

    if not calibrated:
        cv2.putText(
            frame, "Look straight ahead — calibrating shortly...",
            (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2,
        )
        return

    # ── sip counter badge ──
    cv2.rectangle(frame, (10, 10), (260, 70), (40, 40, 40), -1)
    cv2.rectangle(frame, (10, 10), (260, 70), (200, 200, 200), 2)
    cv2.putText(
        frame, f"Sips: {sip_count}",
        (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 220, 255), 3,
    )

    # ── signal indicators ──
    panel_y = 80
    cv2.rectangle(frame, (10, panel_y), (290, panel_y + 110), (30, 30, 30), -1)
    cv2.rectangle(frame, (10, panel_y), (290, panel_y + 110), (100, 100, 100), 1)

    defs = [
        ("Wrist Visible", signals._is_active(signals.wrist_visible, signals.wrist_visible_time, now)),
        ("Object Near Mouth", signals._is_active(signals.object_near_mouth, signals.object_near_mouth_time, now)),
        (f"Head Tilt ({tilt_deg:+.1f} deg)", signals._is_active(signals.head_tilted, signals.head_tilted_time, now)),
    ]
    for i, (label, active) in enumerate(defs):
        colour = (0, 255, 0) if active else (80, 80, 80)
        marker = "[*]" if active else "[ ]"
        cv2.putText(
            frame, f"{marker} {label}",
            (20, panel_y + 30 + i * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2,
        )

    # ── flash SIP DETECTED ──
    if signals.active_count(now) >= SIGNAL_REQUIRED_COUNT:
        cv2.putText(
            frame, "SIP DETECTED!",
            (w // 2 - 130, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3,
        )


# ──────────────────────────────────────────────
# Report generator
# ──────────────────────────────────────────────
def generate_hydration_report(sip_log: list, session_start):
    """Generate a visual hydration report (total sips + sips-per-hour)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.dates import DateFormatter
    except ImportError:
        print("\n⚠️  matplotlib not installed. Skipping hydration report.")
        print("   Install with: pip install matplotlib")
        return

    now = datetime.now()
    total_duration_min = (now - session_start).total_seconds() / 60.0
    total_sips = len(sip_log)
    rate_per_hour = (total_sips / total_duration_min * 60.0) if total_duration_min > 0 else 0.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(
        f'Hydration Session — {session_start.strftime("%Y-%m-%d %H:%M")}',
        fontsize=14, fontweight='bold',
    )

    if sip_log:
        sip_times = [entry['time'] for entry in sip_log]
        cumulative = list(range(1, len(sip_times) + 1))

        # ── Top: cumulative sip count step chart ─────────────────────────────
        plot_times  = [session_start] + sip_times + [now]
        plot_counts = [0] + cumulative + [total_sips]
        ax1.step(plot_times, plot_counts, where='post',
                 color='#2196F3', linewidth=2, label='Cumulative sips')
        ax1.scatter(sip_times, cumulative,
                    color='#2196F3', s=60, zorder=5, label='Sip events')
        ax1.set_ylabel('Cumulative Sips', fontsize=11)
        ax1.set_ylim(bottom=0)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')
        ax1.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # ── Bottom: sips per time bucket (auto-sized) ─────────────────────────
        if   total_duration_min <=  30: bucket_min = 5
        elif total_duration_min <= 120: bucket_min = 15
        elif total_duration_min <= 480: bucket_min = 30
        else:                           bucket_min = 60

        bucket_sec = bucket_min * 60
        session_ts = session_start.timestamp()
        n_buckets  = max(1, math.ceil(total_duration_min * 60 / bucket_sec))

        bucket_counts = [0] * n_buckets
        for entry in sip_log:
            offset = entry['time'].timestamp() - session_ts
            idx = min(int(offset / bucket_sec), n_buckets - 1)
            bucket_counts[idx] += 1

        # Normalise bucket counts → projected sips per hour
        scale     = 60.0 / bucket_min
        per_hour  = [c * scale for c in bucket_counts]
        labels    = [
            f"{int(i * bucket_min)}–{int((i + 1) * bucket_min)} min"
            for i in range(n_buckets)
        ]

        bars = ax2.bar(range(n_buckets), per_hour,
                       color='#64B5F6', edgecolor='#1565C0')
        ax2.set_xticks(range(n_buckets))
        ax2.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax2.set_ylabel('Projected Sips / Hour', fontsize=11)
        ax2.set_title(f'Sip Rate per {bucket_min}-Minute Window', fontsize=12)
        ax2.grid(True, alpha=0.3, axis='y')
        for bar, val in zip(bars, per_hour):
            if val > 0:
                ax2.text(
                    bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f'{val:.1f}', ha='center', va='bottom', fontsize=9,
                )
    else:
        for ax in (ax1, ax2):
            ax.text(0.5, 0.5, 'No sips recorded this session.',
                    ha='center', va='center', fontsize=14, color='gray',
                    transform=ax.transAxes)
            ax.axis('off')

    stats_text = (
        f"Duration: {total_duration_min:.1f} min  |  "
        f"Total Sips: {total_sips}  |  "
        f"Avg Rate: {rate_per_hour:.1f} sips/hr"
    )
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='#E3F2FD', alpha=0.8))

    plt.tight_layout(rect=[0, 0.05, 1, 0.96])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename   = os.path.join(script_dir, 'hydrationreport.png')
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"\n📊 Hydration report saved: {filename}")
    print(f"   Duration: {total_duration_min:.1f} min  |  "
          f"Total sips: {total_sips}  |  "
          f"Rate: {rate_per_hour:.1f}/hr")


# ──────────────────────────────────────────────
# Model downloader
# ──────────────────────────────────────────────
def ensure_model(url: str, dest: str, label: str):
    if not os.path.exists(dest):
        print(f"Downloading {label} (one-time setup)…")
        urllib.request.urlretrieve(url, dest)
        print(f"  ✅ {label} → {dest}")


# ──────────────────────────────────────────────
# HydrationTracker — stateful processor
# ──────────────────────────────────────────────
class HydrationTracker:
    """
    Stateful sip-detection processor that accepts frames via on_frame().

    Lifecycle
    ---------
        tracker = HydrationTracker(debug=True, use_yolo=True)
        tracker.open()                      # load MediaPipe + YOLO models
        camera_manager.register(tracker.on_frame)
        # ... run camera loop ...
        tracker.close()                     # release MediaPipe + print summary
    """

    def __init__(self, debug: bool = False, use_yolo: bool = True):
        self.debug = debug
        self.use_yolo = use_yolo

        self._hand_detector = None
        self._face_detector = None
        self._yolo_model = None

        # calibration
        self._calibrated = False
        self._calibrating = True
        self._cal_start = time.time()
        self._cal_samples: list[float] = []
        self._baseline_tilt_ratio = 0.0

        self._first_frame = True   # reset cal timer on first frame, not __init__

        # signals
        self._signals = SignalState()
        self._sip_count = 0
        self._last_sip_time = 0.0
        self._sip_log: list[dict] = []
        self._session_start = datetime.now()
        self._tilt_deg = 0.0

        self._window_visible = True

    # ── Setup / teardown ──────────────────────────────────────────────────────

    def open(self) -> None:
        """Load MediaPipe and (optionally) YOLO models.  Call once before
        registering on_frame."""
        script_dir = os.path.dirname(os.path.abspath(__file__))

        hand_model = os.path.join(script_dir, "hand_landmarker.task")
        face_model = os.path.join(script_dir, "face_landmarker.task")

        ensure_model(
            "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
            "hand_landmarker/float16/latest/hand_landmarker.task",
            hand_model, "Hand Landmarker",
        )
        ensure_model(
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/latest/face_landmarker.task",
            face_model, "Face Landmarker",
        )

        self._hand_detector = mp.tasks.vision.HandLandmarker.create_from_options(
            mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=hand_model),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._face_detector = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=face_model),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )

        if self.use_yolo and YOLO_AVAILABLE:
            try:
                self._yolo_model = YOLO("yolov8n.pt")
                print("✅ YOLOv8n loaded for bottle/cup detection")
            except Exception as exc:
                print(f"⚠️  YOLO failed to load ({exc}); falling back to contour detection")
        elif self.use_yolo and not YOLO_AVAILABLE:
            print("⚠️  ultralytics not installed — using contour fallback for Signal 2")
            print("   Install with: pip install ultralytics")

        print("╔══════════════════════════════════════════╗")
        print("║    Hydration Tracker — Sip Detection     ║")
        print("╠══════════════════════════════════════════╣")
        if self.debug:
            print("║  DEBUG MODE — window stays open          ║")
            print("║  c = recalibrate | r = reset | q = quit  ║")
        else:
            print("║  Calibrating… look straight ahead!       ║")
            print("║  Window closes after calibration         ║")
            print("║  Press Ctrl+C in terminal to stop        ║")
        print("╚══════════════════════════════════════════╝")

    def close(self) -> None:
        """Release MediaPipe detectors, print summary and save report."""
        if self._hand_detector:
            self._hand_detector.close()
        if self._face_detector:
            self._face_detector.close()
        cv2.destroyWindow("Hydration Tracker")
        self._print_summary()
        if self._sip_log:
            generate_hydration_report(self._sip_log, self._session_start)

    # ── Frame callback ────────────────────────────────────────────────────────

    def on_frame(self, frame: np.ndarray, ts_ms: int) -> None:
        """
        Called by CameraManager for every captured frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR frame, already flipped by CameraManager.
        ts_ms : int
            Monotonic timestamp in milliseconds (used by MediaPipe VIDEO mode).
        """
        if self._hand_detector is None or self._face_detector is None:
            return

        if self._first_frame:
            self._cal_start = time.time()
            self._session_start = datetime.now()
            self._first_frame = False

        # Work on a local copy so other callbacks see the unmodified frame
        frame = frame.copy()
        frame_h, frame_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        hand_result = self._hand_detector.detect_for_video(mp_image, ts_ms)
        face_result = self._face_detector.detect_for_video(mp_image, ts_ms)

        hands = hand_result.hand_landmarks if hand_result.hand_landmarks else []
        face = face_result.face_landmarks[0] if face_result.face_landmarks else None

        now = time.time()

        # ── Visualise key landmarks ───────────────────────────────────────────
        if face:
            for idx in (FM_UPPER_LIP, FM_LOWER_LIP, FM_NOSE_TIP, FM_CHIN, FM_FOREHEAD):
                lm = face[idx]
                cv2.circle(frame, (int(lm.x * frame_w), int(lm.y * frame_h)), 5, (255, 0, 255), -1)

        for hand_lms in hands:
            for lm in hand_lms:
                cv2.circle(frame, (int(lm.x * frame_w), int(lm.y * frame_h)), 3, (0, 255, 0), -1)
            wrist = hand_lms[HAND_WRIST]
            cv2.circle(frame, (int(wrist.x * frame_w), int(wrist.y * frame_h)), 8, (0, 255, 255), -1)

        # ══════════════════════════════════
        #  CALIBRATION
        # ══════════════════════════════════
        if self._calibrating:
            if face:
                self._cal_samples.append(compute_nose_ratio(face))

            elapsed = time.time() - self._cal_start
            progress = min(elapsed / CALIBRATION_DURATION_S, 1.0)
            draw_overlay(frame, self._signals, self._sip_count, False, True, progress, 0.0, now)

            if elapsed >= CALIBRATION_DURATION_S:
                if self._cal_samples:
                    self._baseline_tilt_ratio = float(np.mean(self._cal_samples))
                    self._calibrated = True
                    self._calibrating = False
                    print(f"\n✅ Hydration calibration complete ({len(self._cal_samples)} samples)")
                    print(f"   Baseline nose-ratio: {self._baseline_tilt_ratio:.4f}")
                    if not self.debug:
                        print("\n🎯 Tracking hydration in background…")
                        self._window_visible = False
                        cv2.destroyWindow("Hydration Tracker")
                        cv2.waitKey(1)
                    else:
                        print("\n🐛 Debug mode — window staying open\n")
                else:
                    print("⚠️  No face detected during calibration — retrying…")
                    self._cal_start = time.time()
                    self._cal_samples.clear()

        # ══════════════════════════════════
        #  LIVE SIP DETECTION
        # ══════════════════════════════════
        elif self._calibrated:
            # Signal 1 — wrist visible
            if check_wrist_visible(hands):
                self._signals.wrist_visible = True
                self._signals.wrist_visible_time = now
            elif now - self._signals.wrist_visible_time > SIP_GESTURE_WINDOW_S:
                self._signals.wrist_visible = False

            # Signal 2 — object near mouth
            if self._yolo_model is not None:
                obj = check_object_near_mouth_yolo(
                    self._yolo_model, frame, face, frame_w, frame_h
                )
            else:
                obj = check_object_near_mouth_contour(frame, face, frame_w, frame_h)
            if obj:
                self._signals.object_near_mouth = True
                self._signals.object_near_mouth_time = now
            elif now - self._signals.object_near_mouth_time > SIP_GESTURE_WINDOW_S:
                self._signals.object_near_mouth = False

            # Signal 3 — head tilt
            tilted, self._tilt_deg = check_head_tilt(face, self._baseline_tilt_ratio)
            if tilted:
                self._signals.head_tilted = True
                self._signals.head_tilted_time = now
            elif now - self._signals.head_tilted_time > SIP_GESTURE_WINDOW_S:
                self._signals.head_tilted = False

            # ── Sip confirmation ──────────────────────────────────────────────
            if (
                self._signals.active_count(now) >= SIGNAL_REQUIRED_COUNT
                and (now - self._last_sip_time) > SIP_COOLDOWN_S
            ):
                self._sip_count += 1
                self._last_sip_time = now
                active = self._signals.active_labels(now)
                self._signals.reset()
                print(f"💧 Sip #{self._sip_count} detected!  Signals: {', '.join(active)}")
                self._sip_log.append({"time": datetime.now(), "signals": list(active)})
                send_notification(
                    "Hydration Tracker 💧", f"Sip #{self._sip_count} recorded!"
                )

            draw_overlay(
                frame, self._signals, self._sip_count,
                True, False, 0, self._tilt_deg, now,
            )

        if self._window_visible:
            cv2.imshow("Hydration Tracker", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                raise KeyboardInterrupt
            elif self.debug and key == ord("r"):
                self._sip_count = 0
                self._sip_log.clear()
                print("🔄 Sip count reset")
            elif self.debug and key == ord("c"):
                self._calibrating = True
                self._calibrated = False
                self._cal_start = time.time()
                self._cal_samples.clear()
                self._signals = SignalState()
                self._window_visible = True
                print("📐 Recalibrating — look straight ahead…")

    # ── Summary helper ────────────────────────────────────────────────────────

    def _print_summary(self) -> None:
        duration_min = (datetime.now() - self._session_start).total_seconds() / 60.0
        print(f"\n{'=' * 44}")
        print("  Hydration Session Summary")
        print(f"{'=' * 44}")
        print(f"  Total sips : {self._sip_count}")
        print(f"  Duration   : {duration_min:.1f} min")
        if self._sip_count > 0 and duration_min > 0:
            print(f"  Rate       : {self._sip_count / (duration_min / 60):.1f} sips/hour")
        if self._sip_log:
            print("\n  Sip Timeline:")
            for entry in self._sip_log:
                t = entry["time"].strftime("%H:%M:%S")
                sigs = ", ".join(entry["signals"])
                print(f"    {t}  — {sigs}")
        print(f"{'=' * 44}")
        print("👋 Bye!")


# ──────────────────────────────────────────────
# Standalone entry point
# ──────────────────────────────────────────────
def main(debug: bool = False, camera_index: int = 0, use_yolo: bool = True) -> None:
    """Run HydrationTracker standalone (owns its own CameraManager)."""
    _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from camera_manager import CameraManager

    tracker = HydrationTracker(debug=debug, use_yolo=use_yolo)
    tracker.open()

    cam = CameraManager(camera_index=camera_index)
    cam.register(tracker.on_frame)
    try:
        cam.start()
    except KeyboardInterrupt:
        print("\n\n⏸️  Stopping hydration tracker…")
    finally:
        cam.stop()
        tracker.close()


# ──────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hydration Tracker — Sip Detection")
    parser.add_argument(
        "--debug", action="store_true",
        help="Keep video window open for debugging (default: closes after calibration)",
    )
    parser.add_argument(
        "--camera", type=int, default=0,
        help="Camera index (default: 0)",
    )
    parser.add_argument(
        "--no-yolo", action="store_true",
        help="Disable YOLO object detection; use contour fallback for Signal 2",
    )
    args = parser.parse_args()

    try:
        main(debug=args.debug, camera_index=args.camera, use_yolo=not args.no_yolo)
    except KeyboardInterrupt:
        print("\n\n👋 Hydration tracker stopped.")

