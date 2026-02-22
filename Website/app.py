import atexit
import csv
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

import torch
from flask import Flask, jsonify, redirect, render_template, request, url_for, send_file, abort
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
from transformers import pipeline

class Settings:
    system_enabled = False
    camera_enabled = False
    screen_enabled = False

    selected_voice = "Jessica"
    blocklist = ""
    prodlist = ""

    def __init__(
        self,
        system_enabled=True,
        camera_enabled=False,
        screen_enabled=False,
        selected_voice="Jessica",
        blocklist="",
        prodlist=""
    ):
        self.system_enabled = system_enabled
        self.camera_enabled = camera_enabled
        self.screen_enabled = screen_enabled
        self.selected_voice = selected_voice
        self.blocklist = blocklist
        self.prodlist = prodlist

    def print(self):
        print(self.system_enabled)
        print(self.camera_enabled)
        print(self.screen_enabled)

    def to_dict(self):
        return self.__dict__

class Profile:
    user_name = None
    blocklist = ""
    prodlist = ""

    def __init__(self, user_name=None, blocklist="", prodlist=""):
        self.user_name = user_name
        self.blocklist = blocklist
        self.prodlist = prodlist

    def to_dict(self):
        return self.__dict__

class Statistics:
    productivity = 0
    focus = 0
    posture = 0
    hydration = 0

    def __init__(self, prod, foc, pos, hyd):
        self.productivity = prod
        self.focus = foc
        self.posture = pos
        self.hydration = hyd

app = Flask(__name__)

# Absolute path to backend/main.py (one level up from Website/)
_BACKEND_MAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "main.py")
_VITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "websiteV2")
_backend_proc: subprocess.Popen | None = None
_vite_proc:    subprocess.Popen | None = None


def _start_vite():
    """Install deps if needed, then launch the Vite dev server as a child process."""
    global _vite_proc
    npm = shutil.which("npm") or "npm"
    # Install dependencies if node_modules is missing
    if not os.path.isdir(os.path.join(_VITE_DIR, "node_modules")):
        print(" * Running npm install in websiteV2 …")
        subprocess.run([npm, "install"], cwd=_VITE_DIR, check=True)
    _vite_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=_VITE_DIR,
    )
    print(f" * Vite dev server started (pid {_vite_proc.pid}) → http://localhost:5173")


def _stop_vite():
    """Terminate Vite when Flask exits."""
    global _vite_proc
    if _vite_proc and _vite_proc.poll() is None:
        _vite_proc.terminate()
        try:
            _vite_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _vite_proc.kill()
    _vite_proc = None


atexit.register(_stop_vite)

user_settings = Settings(
    False, False, False,
    selected_voice="Jessica",
    blocklist="Youtube, HBO MAX, Netflix",
    prodlist="Work, Coding, Reading, School, Email",
)
user_profile = Profile("John Smith")

# Set by /upload when productivity drops; consumed by the backend via /api/productivity_alert.
_productivity_alert_pending = False
_productivity_alert_last_sent: float = 0.0
PRODUCTIVITY_ALERT_COOLDOWN_S = 300  # 5 minutes

# Tracks the wall-clock start of the current UI session so CSV reads are scoped to it.
_session_start_time: datetime = datetime.min
upload_request_count = 0

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global user_settings, user_profile

    return render_template(
        "settings.html",
        user_settings=user_settings,
        user_profile=user_profile)

# Get the directory where this app.py file is located
app_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(app_dir, "models")
log_file = os.path.join(app_dir, "results_detailed.csv")
# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

# Initialize detailed CSV log file with headers if it doesn't exist
if not os.path.exists(log_file):
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Timestamp', 'SessionId', 'ActivityLabel',
            'ActivityScore', 'ProductivityLabel', 'ProductivityScore', 'TextLength'
        ])

# create an application init to download the classifier
classifier_path = os.path.join(models_dir, "productivity_classifier")
if not os.path.exists(classifier_path):
    print("Model not found. Downloading classifier model.")
    temp_classifier = pipeline(
        task="zero-shot-image-classification",
        model="openai/clip-vit-large-patch14",  # or openai/clip-vit-base-patch32
        device=-1,  # set to -1 for CPU
    )
    temp_classifier.model.save_pretrained(classifier_path)
    image_processor = getattr(temp_classifier, "image_processor", None) or getattr(temp_classifier, "processor", None)
    if image_processor is not None:
        image_processor.save_pretrained(classifier_path)
    print("Model saved locally.")

def get_pipeline_device():
    if torch.cuda.is_available():
        return 0
    return -1

print("Loading classifier model...")
classifier = pipeline(
    task="zero-shot-image-classification",
    model=classifier_path,
    device=get_pipeline_device(),
)

SESSION_WINDOW_MINUTES = 15

def get_session_window(dt, window_minutes=SESSION_WINDOW_MINUTES):
    window_start = dt.replace(second=0, microsecond=0)
    minutes = (window_start.minute // window_minutes) * window_minutes
    window_start = window_start.replace(minute=minutes)
    window_end = window_start + timedelta(minutes=window_minutes)
    session_id = window_start.strftime("%Y%m%d_%H%M")
    return session_id, window_start, window_end

def get_blocklist():
    raw = ",".join(filter(None, [user_settings.blocklist, user_profile.blocklist]))
    return [item.strip() for item in raw.split(",") if item.strip()]

def get_prodlist():
    raw = ",".join(filter(None, [user_settings.prodlist, user_profile.prodlist]))
    return [item.strip() for item in raw.split(",") if item.strip()]

# Short visual phrase expansions so CLIP can match them.
# Raw brand names like "YouTube" have dominant priors in CLIP's embedding space
# and will always win in a multi-class softmax regardless of what's on screen.
# Phrases are kept short so joined labels stay under CLIP's 77-token limit.
_LABEL_EXPANSIONS: dict[str, str] = {
    "youtube":    "YouTube video player with thumbnails",
    "netflix":    "Netflix movie streaming service",
    "reddit":     "Reddit social media feed with posts",
    "twitter":    "Twitter social media with tweets",
    "instagram":  "Instagram photo sharing app",
    "facebook":   "Facebook social media news feed",
    "tiktok":     "TikTok short video app",
    "twitch":     "Twitch live game streaming",
    "discord":    "Discord messaging app with channels",
    "vs code":    "VS Code code editor with syntax highlighting",
    "vscode":     "VS Code code editor with syntax highlighting",
    "coding":     "code editor showing programming code",
    "terminal":   "black terminal with command line text",
    "notion":     "Notion document editor",
    "figma":      "Figma design tool canvas",
    "gmail":      "Gmail email inbox",
    "slack":      "Slack team messaging",
    "zoom":       "Zoom video conference",
    "docs":       "Google Docs word processor",
    "sheets":     "Google Sheets spreadsheet",
    "jira":       "Jira project tracker",
    "github":     "GitHub code repository",
}

_FALLBACK_PRODUCTIVE   = "code editor or productivity document tool"
_FALLBACK_UNPRODUCTIVE = "social media or video entertainment site"

# Max items from each list to include in the combined phrase.
# CLIP's text encoder is capped at 77 tokens; keeping ≤3 items per side
# ensures the joined phrase stays well under that limit.
_MAX_LABELS_PER_SIDE = 3

def _expand_label(label: str) -> str:
    return _LABEL_EXPANSIONS.get(label.lower().strip(), label)

def classify_activity(img):
    """Binary CLIP classification: productive vs unproductive.

    Instead of competing N raw brand names (where YouTube/Reddit always win due
    to strong CLIP priors), we build exactly TWO short aggregated phrases and
    force a binary choice. Capped at _MAX_LABELS_PER_SIDE items per phrase to
    stay under CLIP's 77-token text limit.
    """
    blocklist = get_blocklist()
    prodlist  = get_prodlist()

    if not blocklist and not prodlist:
        return "unknown", 0.0

    # Build the two candidate labels (capped to avoid CLIP's 77-token limit)
    if blocklist:
        block_desc = " or ".join(_expand_label(l) for l in blocklist[:_MAX_LABELS_PER_SIDE])
        unproductive_label = f"screen showing {block_desc}"
    else:
        unproductive_label = _FALLBACK_UNPRODUCTIVE

    if prodlist:
        prod_desc = " or ".join(_expand_label(l) for l in prodlist[:_MAX_LABELS_PER_SIDE])
        productive_label = f"screen showing {prod_desc}"
    else:
        productive_label = _FALLBACK_PRODUCTIVE

    result = classifier(img, candidate_labels=[unproductive_label, productive_label])
    scores = {r["label"]: r["score"] for r in result} if isinstance(result, list) else {result["label"]: result["score"]}

    prod_score   = scores.get(productive_label,   0.0)
    unprod_score = scores.get(unproductive_label, 0.0)

    if prod_score >= unprod_score:
        return "productive", float(prod_score)
    else:
        return "unproductive", float(unprod_score)

def activity_to_productivity(activity_label, activity_score):
    if activity_label == "unproductive":
        return "unproductive"
    return "productive"

# ── In-memory productivity score ──────────────────────────────────────────────
# Avoids reading/writing CSV on every upload. Score = productive / total * 100.
_score_productive = 0
_score_total = 0
_last_activity_label = "unknown"

def _score_reset():
    global _score_productive, _score_total, _last_activity_label
    _score_productive = 0
    _score_total = 0
    _last_activity_label = "unknown"

def _score_record(productive: bool):
    global _score_productive, _score_total
    _score_total += 1
    if productive:
        _score_productive += 1

def _score_get() -> "int | None":
    if _score_total == 0:
        return None  # no data yet
    return round(_score_productive / _score_total * 100)

def _async_log(activity_label, activity_score, productivity_label, session_id):
    """Write a CSV row in a background thread — never blocks the request."""
    import threading
    def _write():
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, session_id, activity_label,
                                  activity_score, productivity_label,
                                  1 if productivity_label == 'productive' else 0, 0])
        except Exception as e:
            print(f"CSV log error: {e}")
    threading.Thread(target=_write, daemon=True).start()

@app.route("/upload", methods=["POST"])
def upload():
    global upload_request_count, _last_activity_label
    upload_request_count += 1

    # Throttle: only classify every 5th frame (~5 s at 1 fps)
    if upload_request_count % 5 != 0:
        return jsonify({
            "status": "skipped",
            "productivity_score": _score_get(),
            "activity_label": _last_activity_label,
        })

    image = request.files["image"]
    frame_path = os.path.join(app_dir, "frame.jpg")
    image.save(frame_path)

    try:
        img = Image.open(frame_path).convert("RGB")
        activity_label, activity_score = classify_activity(img)
    except Exception as e:
        print(f"Classification error: {e}")
        return jsonify({"status": "error", "productivity_score": _score_get()}), 400

    _last_activity_label = activity_label
    productivity_label = activity_to_productivity(activity_label, activity_score)
    # Only record frames that were actually classified; skip "unknown" entirely
    # (returned when no blocklist/prodlist is configured) so they don't inflate
    # the productive count and push the score toward 100.
    if activity_label != "unknown":
        _score_record(productivity_label == "productive")
    productivity_score = _score_get()

    # Alert check (every 5s, after 60s grace)
    if upload_request_count >= 60:
        if _score_total >= 6 and productivity_score is not None and productivity_score < 75:
            global _productivity_alert_pending, _productivity_alert_last_sent
            if time.time() - _productivity_alert_last_sent >= PRODUCTIVITY_ALERT_COOLDOWN_S:
                _productivity_alert_pending = True
                _productivity_alert_last_sent = time.time()

    # Async CSV write for historical records — never blocks the response
    now = datetime.now()
    session_id, _, _ = get_session_window(now)
    _async_log(activity_label, activity_score, productivity_label, session_id)

    print(f"{activity_label} → {productivity_label} ({productivity_score}%)")

    return jsonify({
        "status": "received",
        "activity_label": activity_label,
        "activity_score": float(activity_score),
        "productivity_label": productivity_label,
        "productivity_score": productivity_score,
    })
# Keep the initialized settings/profile above; avoid resetting them later.

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/get_productivity_score', methods=['GET'])
def get_productivity_score():
    return jsonify({"productivity_score": _score_get()})

@app.route('/get_settings', methods=['GET'])
def get_settings():
    return jsonify(user_settings.to_dict())

@app.route('/get_profile', methods=['GET'])
def get_profile():
    return jsonify(user_profile.to_dict())

@app.route('/update_settings', methods=['POST'])
def update_settings():
    data = json.loads(request.data)

    try:
        user_settings.system_enabled = data['system_enabled']
        user_settings.selected_voice = data['voice_selection']
        user_settings.blocklist = data['blocklist']
        user_settings.prodlist = data['prodlist']
        user_settings.camera_enabled = data['camera_enabled']
        user_settings.screen_enabled = data['screen_enabled']

    except:
        return "", 200

    return "", 200


@app.route('/update_profile', methods=['POST'])
def update_profile():
    user_profile.user_name = request.form.get("name")
    user_profile.user_job = request.form.get("job_title")
    user_profile.user_project = request.form.get("project_desc")

    return redirect(url_for("settings"))


# ── Camera service control ────────────────────────────────────────────────────

@app.route('/api/backend/start', methods=['POST'])
def backend_start():
    global _backend_proc

    # Gate: system must be enabled in settings
    if not user_settings.system_enabled:
        return jsonify({"status": "disabled", "reason": "System is not enabled in settings"}), 200

    if _backend_proc is not None and _backend_proc.poll() is None:
        return jsonify({"status": "already_running", "pid": _backend_proc.pid}), 200

    # Reset per-session state
    global _session_start_time, upload_request_count, _productivity_alert_pending
    _session_start_time = datetime.now()
    upload_request_count = 0
    _productivity_alert_pending = False
    _score_reset()

    # Build CLI flags from current settings
    cmd = [sys.executable, _BACKEND_MAIN]

    _backend_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"status": "started", "pid": _backend_proc.pid}), 200


@app.route('/api/backend/stop', methods=['POST'])
def backend_stop():
    global _backend_proc
    if _backend_proc is None or _backend_proc.poll() is not None:
        _backend_proc = None
        return jsonify({"status": "not_running"}), 200
    try:
        # Send SIGINT (Ctrl+C) so the backend shuts down gracefully
        _backend_proc.send_signal(signal.SIGINT)
        _backend_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _backend_proc.kill()
    _backend_proc = None
    return jsonify({"status": "stopped"}), 200


@app.route('/api/backend/status', methods=['GET'])
def backend_status():
    running = _backend_proc is not None and _backend_proc.poll() is None
    pid = _backend_proc.pid if running else None
    return jsonify({"running": running, "pid": pid}), 200


# ── JSON settings / profile API (used by websiteV2) ──────────────────────────

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify({
        # System toggles
        "system_enabled":      bool(user_settings.system_enabled),
        "camera_enabled":      bool(user_settings.camera_enabled),
        "screen_enabled":      bool(user_settings.screen_enabled),
        # Misc
        "selected_voice":      user_settings.selected_voice or "Jessica",
        "blocklist":           user_settings.blocklist or "",
        "prodlist":            user_settings.prodlist or "",
        # Profile
        "user_name":           user_profile.user_name or "",
    }), 200


@app.route('/api/voices', methods=['GET'])
def api_get_voices():
    return jsonify(["Jessica", "Sarah", "Harry", "Daniel"]), 200


@app.route('/api/productivity_score', methods=['GET'])
def api_productivity_score():
    return jsonify({"productivity_score": _score_get()}), 200


@app.route('/api/productivity_alert', methods=['GET'])
def api_productivity_alert():
    """Returns whether a low-productivity alert is pending, then clears it."""
    global _productivity_alert_pending
    alert = _productivity_alert_pending
    _productivity_alert_pending = False
    return jsonify({"alert": alert}), 200


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    data = request.get_json(force=True) or {}
    user_settings.system_enabled     = data.get("system_enabled",     user_settings.system_enabled)
    user_settings.camera_enabled     = data.get("camera_enabled",     user_settings.camera_enabled)
    user_settings.screen_enabled     = data.get("screen_enabled",     user_settings.screen_enabled)
    user_settings.selected_voice     = data.get("selected_voice",     user_settings.selected_voice)
    user_settings.blocklist          = data.get("blocklist",          user_settings.blocklist)
    user_settings.prodlist           = data.get("prodlist",           user_settings.prodlist)
    return jsonify({"status": "ok"}), 200


@app.route('/api/profile', methods=['POST'])
def api_update_profile():
    data = request.get_json(force=True) or {}
    user_profile.user_name = data.get("name", user_profile.user_name)
    return jsonify({"status": "ok"}), 200

@app.route('/audio')
def audio():
    # Get the file parameter from query string
    file = request.args.get('source')

    if not file:
        return "No file specified", 400

    # Construct the file path (adjust your directory as needed)
    file_path = os.path.join('./static/audio', file)

    # Check if file exists
    if not os.path.exists(file_path):
        return "File not found", 404

    # Return the MP3 file
    return send_file(file_path, mimetype='audio/mpeg', as_attachment=False)


if __name__ == '__main__':
    _start_vite()
    app.run(port=5001)