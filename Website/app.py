import atexit
from flask import Flask, request, render_template, jsonify
import pytesseract
import os
import csv
import json
import os
import signal
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from collections import Counter
from transformers import pipeline
from PIL import Image
import torch

from flask import Flask, jsonify, request, render_template, redirect, url_for, send_file, abort

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

user_settings = Settings(False, False, False, selected_voice="Jessica")
user_profile = Profile("John Smith")

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global user_settings, user_profile

    return render_template(
        "settings.html", 
        user_settings=user_settings,
        user_profile=user_profile)
notifier = WsNotifier()
notifier.start()

user_settings = Settings(True, False, False)
user_profile = Profile("John Smith", 
                       "Youtube, HBO MAX, Netflix",
                       "Work, Coding, Reading, School, Email", )

upload_request_count = 0

# Get the directory where this app.py file is located
app_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(app_dir, "models")
log_file = os.path.join(app_dir, "results_detailed.csv")
session_log_file = os.path.join(app_dir, "results_sessions.csv")
categories_cache_file = os.path.join(app_dir, "categories_cache.json")

# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

# Initialize CSV log file with headers if it doesn't exist
if not os.path.exists(log_file):
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Timestamp',
            'SessionId',
            'ActivityLabel',
            'ActivityScore',
            'ProductivityLabel',
            'ProductivityScore',
            'TextLength'
        ])

# Initialize session summary CSV if it doesn't exist
if not os.path.exists(session_log_file):
    with open(session_log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'SessionId',
            'SessionStart',
            'SessionEnd',
            'Samples',
            'ProductiveSamples',
            'UnproductiveSamples',
            'ProductivityScore',
            'TopActivity',
            'TopActivityShare'
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

def classify_activity(img):
    labels = get_blocklist() + get_prodlist()
    if not labels:
        return "unknown", 0.0
    result = classifier(img, candidate_labels=labels)
    top = result[0] if isinstance(result, list) and result else result
    return top["label"], float(top["score"])

def activity_to_productivity(activity_label, activity_score):
    if activity_label in get_blocklist() and activity_score > 0.4:
        return "unproductive"
    return "productive"

def log_detailed_result(activity_label, activity_score, productivity_label, productivity_score, session_id, text_length=0):
    """Log detailed classification result with timestamp to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            session_id,
            activity_label,
            activity_score,
            productivity_label,
            productivity_score,
            text_length
        ])

def read_session_log():
    sessions = {}
    if not os.path.exists(session_log_file):
        return sessions
    with open(session_log_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sessions[row['SessionId']] = row
    return sessions

def write_session_log(sessions):
    with open(session_log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'SessionId',
            'SessionStart',
            'SessionEnd',
            'Samples',
            'ProductiveSamples',
            'UnproductiveSamples',
            'ProductivityScore',
            'TopActivity',
            'TopActivityShare'
        ])
        for session_id, row in sessions.items():
            writer.writerow([
                row['SessionId'],
                row['SessionStart'],
                row['SessionEnd'],
                row['Samples'],
                row['ProductiveSamples'],
                row['UnproductiveSamples'],
                row['ProductivityScore'],
                row['TopActivity'],
                row['TopActivityShare']
            ])

def update_session_summary(session_id, session_start, session_end):
    if not os.path.exists(log_file):
        return 0

    activity_counts = Counter()
    productive_count = 0
    unproductive_count = 0
    total_count = 0

    with open(log_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['SessionId'] != session_id:
                continue
            total_count += 1
            activity_counts[row['ActivityLabel']] += 1
            if row['ProductivityLabel'] == 'productive':
                productive_count += 1
            else:
                unproductive_count += 1

    if total_count == 0:
        return 0

    productivity_score = round((productive_count / total_count) * 100, 2)
    top_activity, top_activity_count = activity_counts.most_common(1)[0]
    top_activity_share = round((top_activity_count / total_count) * 100, 2)

    sessions = read_session_log()
    sessions[session_id] = {
        'SessionId': session_id,
        'SessionStart': session_start.strftime("%Y-%m-%d %H:%M:%S"),
        'SessionEnd': session_end.strftime("%Y-%m-%d %H:%M:%S"),
        'Samples': str(total_count),
        'ProductiveSamples': str(productive_count),
        'UnproductiveSamples': str(unproductive_count),
        'ProductivityScore': str(productivity_score),
        'TopActivity': top_activity,
        'TopActivityShare': str(top_activity_share)
    }
    write_session_log(sessions)
    return productivity_score

def calculate_productivity_score():
    """Get the latest session productivity score"""
    if not os.path.exists(session_log_file):
        return 0

    try:
        with open(session_log_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                return 0
            latest = rows[-1]
            return float(latest.get('ProductivityScore', 0))
    except Exception as e:
        print(f"Error calculating productivity score: {e}")
        return 0

def was_recently_unproductive(window_seconds=30):
    if not os.path.exists(log_file):
        return False

    cutoff = datetime.now() - timedelta(seconds=window_seconds)
    try:
        with open(log_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            total_count = 0
            productive_count = 0
            for row in reader:
                timestamp = datetime.strptime(row['Timestamp'], "%Y-%m-%d %H:%M:%S")
                if timestamp < cutoff:
                    continue
                total_count += 1
                if row['ProductivityLabel'] == 'productive':
                    productive_count += 1
    except Exception as e:
        print(f"Error checking recent productivity: {e}")
        return False

    if total_count == 0:
        return False

    productivity_pct = (productive_count / total_count) * 100
    return productivity_pct < 50

@app.route("/upload", methods=["POST"])
def upload():
    global upload_request_count
    upload_request_count += 1
    
    image = request.files["image"]

    frame_path = os.path.join(app_dir, "frame.jpg")
    image.save(frame_path)

    img = Image.open(frame_path).convert("RGB")
    activity_label, activity_score = classify_activity(img)
    productivity_label = activity_to_productivity(activity_label, activity_score)
    productivity_score_value = 1 if productivity_label == "productive" else 0
    now = datetime.now()
    session_id, session_start, session_end = get_session_window(now)

    # Log the detailed result
    log_detailed_result(
        activity_label,
        activity_score,
        productivity_label,
        productivity_score_value,
        session_id,
    )

    if upload_request_count % 30 == 0:
        recently_unproductive = was_recently_unproductive()
    else:
        recently_unproductive = False
        
    if recently_unproductive:
        notifier.notify(
            module="focus",
            level="warning",
            simple="Low Productivity",
            detail="⚠️  User productivity has dropped below 50% in the last 30 seconds. Consider taking a break or refocusing."
        )

    # Update session summary and return session score
    productivity_score = update_session_summary(session_id, session_start, session_end)

    print(activity_label)

    return jsonify({
        "status": "received", 
        "activity_label": activity_label,
        "activity_score": float(activity_score),
        "productivity_label": productivity_label,
        "productivity_score": productivity_score
    })
# Keep the initialized settings/profile above; avoid resetting them later.

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/get_productivity_score', methods=['GET'])
def get_productivity_score():
    """Placeholder — productivity is computed client-side from tracker scores."""
    return jsonify({"productivity_score": 0})

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