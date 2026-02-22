import os
import signal
import subprocess
import sys

from flask import Flask, jsonify, request, render_template, redirect, url_for

class Settings:
    system_enabled = False
    camera_enabled = False
    screen_enabled = False

    track_productivity = False
    track_focus = False
    track_hydration = False
    track_posture = False

    selected_voice = "Voice 1"
    blocklist = ""
    prodlist = ""

    def __init__(
        self,
        system_enabled=True,
        camera_enabled=False,
        screen_enabled=False,
        track_productivity=False,
        track_focus=False,
        track_hydration=False,
        track_posture=False,
        selected_voice="Voice 1",
        blocklist="",
        prodlist=""
    ):
        self.system_enabled = system_enabled
        self.camera_enabled = camera_enabled
        self.screen_enabled = screen_enabled
        self.track_productivity = track_productivity
        self.track_focus = track_focus
        self.track_hydration = track_hydration
        self.track_posture = track_posture
        self.selected_voice = selected_voice
        self.blocklist = blocklist
        self.prodlist = prodlist

    def print(self):
        print(self.system_enabled)
        print(self.camera_enabled)
        print(self.screen_enabled)
        print(self.track_productivity)
        print(self.track_focus)
        print(self.track_hydration)
        print(self.track_posture)

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
_backend_proc: subprocess.Popen | None = None

user_settings = Settings(True, False, False)
user_profile = Profile("John Smith", "Instagram, Facebook, YouTube, Reddit, Twitter, TikTok, Netflix, Social Media", "Work, Programming, Writing, Research, Learning")

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
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )
    temp_classifier.save_pretrained(classifier_path)
    print("Model saved locally.")

print("Loading classifier model...")
classifier = pipeline(
    "zero-shot-classification",
    model=classifier_path
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

def classify_activity(text):
    labels = get_blocklist() + get_prodlist()
    result = classifier(text, candidate_labels=labels)
    return result["labels"][0], float(result["scores"][0])

def activity_to_productivity(activity_label, activity_score):
    if activity_label in get_blocklist() and activity_score > 0.6:
        return "unproductive"
    return "productive"

def log_detailed_result(activity_label, activity_score, productivity_label, productivity_score, session_id, text_length):
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
       
    # save or OCR here
    frame_path = os.path.join(app_dir, "frame.jpg")
    image.save(frame_path)

    img = cv2.imread(frame_path)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(gray)
    
    text_path = os.path.join(app_dir, "text.txt")
    with open(text_path, 'w') as f:
        f.write(text)
    
    activity_label, activity_score = classify_activity(text)
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
        len(text)
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
    """Get the overall productivity score"""
    score = calculate_productivity_score()
    return jsonify({"productivity_score": score})

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
        user_settings.track_productivity = data['productivity_enabled']
        user_settings.track_focus = data['focus_enabled']
        user_settings.track_hydration = data['hydration_enabled']
        user_settings.track_posture = data['posture_enabled']
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
    if _backend_proc is not None and _backend_proc.poll() is None:
        return jsonify({"status": "already_running", "pid": _backend_proc.pid}), 200
    _backend_proc = subprocess.Popen(
        [sys.executable, _BACKEND_MAIN],
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



# ── Camera service control ────────────────────────────────────────────────────

@app.route('/api/backend/start', methods=['POST'])
def backend_start():
    global _backend_proc
    if _backend_proc is not None and _backend_proc.poll() is None:
        return jsonify({"status": "already_running", "pid": _backend_proc.pid}), 200
    _backend_proc = subprocess.Popen(
        [sys.executable, _BACKEND_MAIN],
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


if __name__ == '__main__':
    app.run(port=5001)
    app.run(port=5001)