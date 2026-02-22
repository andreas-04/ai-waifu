#!/usr/bin/env python3
"""
Posture Monitor — calibration-based, front-view webcam posture detection.

Tech stack: OpenCV · MediaPipe Pose · NumPy
Run:  python posture_monitor.py [--debug]

Flow:
  1. Registers on_frame() with a CameraManager (or runs standalone).
  2. Auto-starts calibration — sit up straight for 3 seconds.
  3. After calibration, monitors posture on every delivered frame.
  4. Sends desktop notifications when bad posture is detected.
  5. Use --debug flag to keep the video window open for testing.

Standalone:  python posture_monitor.py [--debug] [--camera N]
"""

import os
import sys
import time
import subprocess
import platform
import argparse
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import mediapipe as mp

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
CALIBRATION_DURATION_S = 3.0        # seconds of frames to average during calibration
VISIBILITY_THRESHOLD = 0.5          # ignore landmarks with visibility below this
BAD_POSTURE_NOTIFY_S = 5.0          # seconds of consecutive bad posture before notification
NOTIFICATION_COOLDOWN_S = 30.0      # don't re-notify within this window

# Sensitivity multipliers — how far a metric must deviate from the baseline
# before it's flagged.  Expressed as a fraction of the baseline value.
THRESH_HEAD_TILT = 0.035            # lateral ear-level difference / shoulder width
THRESH_HEAD_FORWARD = 0.25          # ear-to-shoulder vertical shrinkage (fraction)
THRESH_SHOULDER_ASYM = 0.08         # shoulder-level difference / shoulder width
THRESH_SHOULDER_NARROW = 0.12       # shoulder width narrowing (fraction)
THRESH_FACE_SIZE = 0.18             # face scale increase (fraction)


# ──────────────────────────────────────────────
# MediaPipe Pose landmark indices (front-view relevant)
# ──────────────────────────────────────────────
# Full list: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
LM_NOSE = 0
LM_LEFT_EAR = 7
LM_RIGHT_EAR = 8
LM_LEFT_SHOULDER = 11
LM_RIGHT_SHOULDER = 12

REQUIRED_LANDMARKS = [LM_NOSE, LM_LEFT_EAR, LM_RIGHT_EAR,
                      LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def lm_to_array(landmark):
    """Convert a single MediaPipe landmark to a numpy array [x, y]."""
    return np.array([landmark.x, landmark.y])


def landmarks_visible(pose_landmarks):
    """Return True only if every required landmark exceeds the visibility threshold."""
    for idx in REQUIRED_LANDMARKS:
        if pose_landmarks[idx].visibility < VISIBILITY_THRESHOLD:
            return False
    return True


def extract_metrics(pose_landmarks):
    """
    Extract the five posture metrics from a single frame's landmarks.

    All coordinates are in MediaPipe's normalised space (0-1, origin at
    top-left). Using normalised coords keeps us resolution-independent.

    Returns a dict with:
      head_tilt         – signed vertical difference between ears
                          (positive = left ear higher)
      ear_shoulder_dist – average vertical distance from ears down to
                          their respective shoulders (shrinks when head
                          creeps forward because perspective foreshortens)
      shoulder_asym     – signed vertical difference between shoulders
                          (positive = left shoulder higher)
      shoulder_width    – horizontal distance between shoulders
      face_scale        – average horizontal distance from nose to each ear
                          (grows when the user leans toward the screen)
    """
    nose = lm_to_array(pose_landmarks[LM_NOSE])
    l_ear = lm_to_array(pose_landmarks[LM_LEFT_EAR])
    r_ear = lm_to_array(pose_landmarks[LM_RIGHT_EAR])
    l_shoulder = lm_to_array(pose_landmarks[LM_LEFT_SHOULDER])
    r_shoulder = lm_to_array(pose_landmarks[LM_RIGHT_SHOULDER])

    # 1) Head tilt — difference in y between ears (normalised by shoulder width
    #    so it's scale-invariant).
    head_tilt = l_ear[1] - r_ear[1]  # positive → left ear is lower (y goes down)

    # 2) Ear-to-shoulder vertical distance — average of both sides.
    #    In normalised coords, y increases downward, so shoulder_y > ear_y
    #    means the ear is above the shoulder.
    left_ear_shoulder = l_shoulder[1] - l_ear[1]
    right_ear_shoulder = r_shoulder[1] - r_ear[1]
    ear_shoulder_dist = (left_ear_shoulder + right_ear_shoulder) / 2.0

    # 3) Shoulder asymmetry — signed vertical difference.
    shoulder_asym = l_shoulder[1] - r_shoulder[1]

    # 4) Shoulder width — horizontal distance.
    shoulder_width = abs(l_shoulder[0] - r_shoulder[0])

    # 5) Face scale — average distance from nose to each ear.
    face_scale = (np.linalg.norm(nose - l_ear) + np.linalg.norm(nose - r_ear)) / 2.0

    return {
        "head_tilt": head_tilt,
        "ear_shoulder_dist": ear_shoulder_dist,
        "shoulder_asym": shoulder_asym,
        "shoulder_width": shoulder_width,
        "face_scale": face_scale,
    }


def average_metrics(metrics_list):
    """Element-wise average of a list of metric dicts."""
    avg = {}
    for key in metrics_list[0]:
        avg[key] = np.mean([m[key] for m in metrics_list])
    return avg


def check_posture(live, baseline):
    """
    Compare live metrics against calibrated baseline.

    Returns (is_good: bool, issues: list[str]).
    Each check uses the baseline value to set an adaptive threshold.
    """
    issues = []
    sw = baseline["shoulder_width"]  # use as normalisation reference

    # 1) Head tilt — compare absolute deviation from baseline.
    tilt_dev = abs(live["head_tilt"] - baseline["head_tilt"])
    if tilt_dev / max(sw, 1e-6) > THRESH_HEAD_TILT:
        issues.append("Head tilt")

    # 2) Head forward creep — ear-to-shoulder distance should not shrink
    #    significantly compared to baseline.
    es_baseline = baseline["ear_shoulder_dist"]
    es_shrinkage = (es_baseline - live["ear_shoulder_dist"]) / max(abs(es_baseline), 1e-6)
    if es_shrinkage > THRESH_HEAD_FORWARD:
        issues.append("Head forward")

    # 3) Shoulder asymmetry
    asym_dev = abs(live["shoulder_asym"] - baseline["shoulder_asym"])
    if asym_dev / max(sw, 1e-6) > THRESH_SHOULDER_ASYM:
        issues.append("Shoulder uneven")

    # 4) Shoulder width narrowing (proxy for rounding / slouch)
    sw_live = live["shoulder_width"]
    sw_shrinkage = (sw - sw_live) / max(sw, 1e-6)
    if sw_shrinkage > THRESH_SHOULDER_NARROW:
        issues.append("Shoulders rounded")

    # 5) Face getting larger (leaning toward screen)
    fs_baseline = baseline["face_scale"]
    fs_growth = (live["face_scale"] - fs_baseline) / max(fs_baseline, 1e-6)
    if fs_growth > THRESH_FACE_SIZE:
        issues.append("Leaning forward")

    return (len(issues) == 0), issues


def send_notification(title, message):
    """Send a desktop notification (macOS, Linux, Windows)."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ])
        elif system == "Linux":
            subprocess.Popen(["notify-send", title, message])
        elif system == "Windows":
            # Requires win10toast or similar; fall back to a print.
            print(f"[NOTIFICATION] {title}: {message}")
    except Exception:
        pass


def draw_status(frame, is_good, issues, calibrated, calibrating, cal_progress):
    """Draw the posture status overlay on the frame."""
    h, w, _ = frame.shape

    if calibrating:
        # Show calibration progress bar
        bar_w = 300
        bar_h = 30
        x0 = (w - bar_w) // 2
        y0 = h - 80
        cv2.rectangle(frame, (x0, y0), (x0 + bar_w, y0 + bar_h), (255, 255, 255), 2)
        fill = int(bar_w * cal_progress)
        cv2.rectangle(frame, (x0, y0), (x0 + fill, y0 + bar_h), (0, 200, 255), -1)
        cv2.putText(frame, "Calibrating... hold still",
                    (x0, y0 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    elif not calibrated:
        cv2.putText(frame, "Sit up straight, then press 'c' to calibrate",
                    (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    else:
        if is_good:
            color = (0, 200, 0)
            label = "Good Posture"
        else:
            color = (0, 0, 220)
            label = "Fix Posture"

        # Status badge
        cv2.putText(frame, label, (20, h - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

        # List issues
        for i, issue in enumerate(issues):
            cv2.putText(frame, f"- {issue}", (30, h - 20 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def generate_posture_report(posture_log, session_start):
    """Generate a visual report of posture over time."""
    if len(posture_log) < 2:
        print("Not enough data to generate report.")
        return
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        from matplotlib.dates import DateFormatter
        import matplotlib.dates as mdates
    except ImportError:
        print("\n⚠️  matplotlib not installed. Skipping graph generation.")
        print("   Install with: pip install matplotlib")
        return
    
    # Extract data
    timestamps = [entry['time'] for entry in posture_log]
    posture_scores = [1 if entry['is_good'] else 0 for entry in posture_log]
    
    # Calculate statistics
    total_time = (timestamps[-1] - timestamps[0]).total_seconds() / 60  # minutes
    good_count = sum(posture_scores)
    good_percentage = (good_count / len(posture_scores)) * 100
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f'Posture Monitoring Session — {session_start.strftime("%Y-%m-%d %H:%M")}', 
                 fontsize=14, fontweight='bold')
    
    # Top plot: Timeline
    colors = ['#ff4444' if score == 0 else '#44ff44' for score in posture_scores]
    ax1.scatter(timestamps, posture_scores, c=colors, s=10, alpha=0.6)
    ax1.fill_between(timestamps, 0, posture_scores, alpha=0.3, color='green', label='Good Posture')
    ax1.fill_between(timestamps, posture_scores, 1, alpha=0.3, color='red', label='Bad Posture')
    ax1.set_ylabel('Posture Status', fontsize=11)
    ax1.set_yticks([0, 1])
    ax1.set_yticklabels(['Bad', 'Good'])
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    ax1.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Bottom plot: Issue frequency
    issue_counts = {}
    for entry in posture_log:
        for issue in entry.get('issues', []):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    if issue_counts:
        issues = list(issue_counts.keys())
        counts = list(issue_counts.values())
        bars = ax2.barh(issues, counts, color='#ff6b6b')
        ax2.set_xlabel('Number of Detections', fontsize=11)
        ax2.set_ylabel('Posture Issues', fontsize=11)
        ax2.set_title('Most Common Issues', fontsize=12)
        ax2.grid(True, alpha=0.3, axis='x')
        
        # Add value labels on bars
        for bar in bars:
            width = bar.get_width()
            ax2.text(width, bar.get_y() + bar.get_height()/2, 
                    f'{int(width)}', ha='left', va='center', fontsize=9)
    else:
        ax2.text(0.5, 0.5, 'No posture issues detected!\n✓ Perfect session', 
                ha='center', va='center', fontsize=14, color='green',
                transform=ax2.transAxes)
        ax2.axis('off')
    
    # Add statistics text
    stats_text = f"Session Duration: {total_time:.1f} min  |  Good Posture: {good_percentage:.1f}%  |  Samples: {len(posture_log)}"
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    
    # Save to file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(script_dir, "posturereport.png")
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n📊 Posture report saved: {filename}")
    print(f"   Session duration: {total_time:.1f} minutes")
    print(f"   Good posture: {good_percentage:.1f}%")
    if issue_counts:
        print(f"   Most common issue: {max(issue_counts, key=issue_counts.get)}")


# ──────────────────────────────────────────────
# PostureMonitor — stateful processor
# ──────────────────────────────────────────────
class PostureMonitor:
    """
    Stateful posture monitor that processes frames delivered via on_frame().

    Lifecycle
    ---------
        monitor = PostureMonitor(debug=True)
        monitor.open()                      # load MediaPipe model
        camera_manager.register(monitor.on_frame)
        # ... run camera loop ...
        monitor.close()                     # release MediaPipe + print report
    """

    SMOOTHING_WINDOW = 5

    def __init__(self, debug: bool = False):
        self.debug = debug
        self._detector = None

        # calibration
        self._calibrating = True
        self._calibrated = False
        self._cal_start_time = time.time()
        self._cal_samples: list[dict] = []
        self._baseline: dict = {}

        self._first_frame = True   # reset cal timer on first frame, not __init__

        # monitoring
        self._metric_buffer: deque[dict] = deque(maxlen=self.SMOOTHING_WINDOW)
        self._bad_posture_start: float | None = None
        self._last_notification_time = 0.0
        self._window_visible = True

        # reporting
        self._session_start = datetime.now()
        self._posture_log: list[dict] = []

    # ── Setup / teardown ──────────────────────────────────────────────────────

    def open(self) -> None:
        """Load the MediaPipe model.  Call once before registering on_frame."""
        import urllib.request

        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, "pose_landmarker_lite.task")
        if not os.path.exists(model_path):
            print("Downloading pose model (one-time setup)...")
            model_url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "pose_landmarker/pose_landmarker_lite/float16/latest/"
                "pose_landmarker_lite.task"
            )
            urllib.request.urlretrieve(model_url, model_path)
            print(f"Model downloaded to {model_path}")

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = mp.tasks.vision.PoseLandmarker.create_from_options(options)

        print("╔══════════════════════════════════════════╗")
        print("║    Posture Monitor — Background Mode     ║")
        print("╠══════════════════════════════════════════╣")
        if self.debug:
            print("║  DEBUG MODE: Window stays open           ║")
            print("║  c/r = recalibrate  |  q = quit          ║")
        else:
            print("║  Calibrating... sit up straight!         ║")
            print("║  Window will close after calibration     ║")
            print("║  Press Ctrl+C in terminal to quit        ║")
        print("╚══════════════════════════════════════════╝")

    def close(self) -> None:
        """Release the MediaPipe detector and print the session report."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        cv2.destroyWindow("Posture Monitor")
        if self._posture_log:
            generate_posture_report(self._posture_log, self._session_start)
        print("\n👋 PostureMonitor closed.")

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
        if self._detector is None:
            return

        if self._first_frame:
            self._cal_start_time = time.time()
            self._first_frame = False

        # Work on a local copy so other callbacks see the unmodified frame
        frame = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = self._detector.detect_for_video(mp_image, ts_ms)

        pose_landmarks = (
            results.pose_landmarks[0] if results.pose_landmarks else None
        )
        is_good = True
        issues: list[str] = []

        if pose_landmarks:
            h, w, _ = frame.shape
            # Draw landmarks
            for landmark in pose_landmarks:
                if landmark.visibility > VISIBILITY_THRESHOLD:
                    cv2.circle(
                        frame,
                        (int(landmark.x * w), int(landmark.y * h)),
                        4, (0, 255, 0), -1,
                    )
            # Draw key connections
            for start_idx, end_idx in [
                (LM_LEFT_SHOULDER, LM_RIGHT_SHOULDER),
                (LM_LEFT_EAR, LM_LEFT_SHOULDER),
                (LM_RIGHT_EAR, LM_RIGHT_SHOULDER),
            ]:
                s = pose_landmarks[start_idx]
                e = pose_landmarks[end_idx]
                if (
                    s.visibility > VISIBILITY_THRESHOLD
                    and e.visibility > VISIBILITY_THRESHOLD
                ):
                    cv2.line(
                        frame,
                        (int(s.x * w), int(s.y * h)),
                        (int(e.x * w), int(e.y * h)),
                        (0, 255, 0), 2,
                    )

            if landmarks_visible(pose_landmarks):
                metrics = extract_metrics(pose_landmarks)

                if self._calibrating:
                    self._cal_samples.append(metrics)
                    elapsed = time.time() - self._cal_start_time
                    progress = min(elapsed / CALIBRATION_DURATION_S, 1.0)
                    draw_status(frame, True, [], False, True, progress)

                    if elapsed >= CALIBRATION_DURATION_S:
                        self._baseline = average_metrics(self._cal_samples)
                        self._calibrated = True
                        self._calibrating = False
                        self._metric_buffer.clear()
                        print(
                            f"\n✅ Posture calibration complete "
                            f"({len(self._cal_samples)} samples)"
                        )
                        print(
                            f"   Baseline shoulder width : {self._baseline['shoulder_width']:.4f}\n"
                            f"   Baseline ear-shoulder   : {self._baseline['ear_shoulder_dist']:.4f}\n"
                            f"   Baseline face scale     : {self._baseline['face_scale']:.4f}\n"
                            f"   Baseline head tilt      : {self._baseline['head_tilt']:.4f}\n"
                            f"   Baseline shoulder asym  : {self._baseline['shoulder_asym']:.4f}"
                        )
                        if not self.debug:
                            print("\n🎯 Monitoring posture in background…")
                            self._window_visible = False
                            cv2.destroyWindow("Posture Monitor")
                            cv2.waitKey(1)
                        else:
                            print("\n🐛 Debug mode: window staying open\n")

                elif self._calibrated:
                    self._metric_buffer.append(metrics)
                    smoothed = average_metrics(list(self._metric_buffer))
                    is_good, issues = check_posture(smoothed, self._baseline)

                    self._posture_log.append({
                        "time": datetime.now(),
                        "is_good": is_good,
                        "issues": issues.copy(),
                    })

                    if not is_good:
                        now = time.time()
                        if self._bad_posture_start is None:
                            self._bad_posture_start = now
                        elif (
                            now - self._bad_posture_start >= BAD_POSTURE_NOTIFY_S
                            and now - self._last_notification_time >= NOTIFICATION_COOLDOWN_S
                        ):
                            issue_str = ", ".join(issues)
                            print(f"⚠️  Bad posture for {BAD_POSTURE_NOTIFY_S:.0f}s: {issue_str}")
                            send_notification(
                                "Posture Alert 🪑", f"Fix your posture! ({issue_str})"
                            )
                            self._last_notification_time = now
                    else:
                        self._bad_posture_start = None

                    draw_status(frame, is_good, issues, True, False, 0)
                else:
                    draw_status(frame, True, [], False, False, 0)
            else:
                cv2.putText(
                    frame, "Landmarks not visible — face the camera",
                    (20, frame.shape[0] - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 255), 2,
                )
        else:
            cv2.putText(
                frame, "No person detected",
                (20, frame.shape[0] - 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 255), 2,
            )

        if self._window_visible:
            cv2.imshow("Posture Monitor", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                # Signal the camera manager to stop if running standalone
                raise KeyboardInterrupt
            elif self.debug and key in (ord("c"), ord("r")):
                self._calibrating = True
                self._calibrated = False
                self._cal_start_time = time.time()
                self._cal_samples.clear()
                self._metric_buffer.clear()
                self._bad_posture_start = None
                self._window_visible = True
                print("📐 Recalibration started — hold a good posture…")


# ──────────────────────────────────────────────
# Standalone entry point
# ──────────────────────────────────────────────
def main(debug: bool = False, camera_index: int = 0) -> None:
    """Run PostureMonitor standalone (owns its own CameraManager)."""
    # Import here so the module can be used without backend/ on sys.path
    _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from camera_manager import CameraManager

    monitor = PostureMonitor(debug=debug)
    monitor.open()

    cam = CameraManager(camera_index=camera_index)
    cam.register(monitor.on_frame)
    try:
        cam.start()
    except KeyboardInterrupt:
        print("\n\n⏸️  Stopping posture monitor…")
    finally:
        cam.stop()
        monitor.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Posture Monitor — Background Mode")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Keep video window open for debugging",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index (default: 0)",
    )
    args = parser.parse_args()
    try:
        main(debug=args.debug, camera_index=args.camera)
    except KeyboardInterrupt:
        print("\n\n👋 Posture monitor stopped.")
