from flask import Flask, request, render_template, jsonify
import cv2
import pytesseract
import os
import csv
import json
from datetime import datetime, timedelta
from collections import Counter
from transformers import pipeline
import json

class Settings:
    system_enabled = False
    camera_enabled = False
    screen_enabled = False

    track_productivity = True
    track_focus = True
    track_hydration = True
    track_posture = True

    selected_voice = "Voice 1"
    blocklist = ""

    def __init__(
        self,
        system_enabled=True,
        camera_enabled=False,
        screen_enabled=False,
        track_productivity=True,
        track_focus=True,
        track_hydration=True,
        track_posture=True,
        selected_voice="Voice 1",
        blocklist=""
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

    def __init__(self, user_name=None, blocklist=""):
        self.user_name = user_name
        self.blocklist = blocklist

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

user_settings = Settings(True, False, False)
user_profile = Profile("John Smith", "Software Engineer")

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

ACTIVITY_LABELS = [
    "coding",
    "writing",
    "research",
    "documentation",
    "email",
    "meeting",
    "chatting",
    "browsing",
    "video",
    "social media",
    "gaming",
    "idle"
]

PRODUCTIVITY_MAP = {
    "coding": "productive",
    "writing": "productive",
    "research": "productive",
    "documentation": "productive",
    "email": "productive",
    "meeting": "productive",
    "chatting": "unproductive",
    "browsing": "unproductive",
    "video": "unproductive",
    "social media": "unproductive",
    "gaming": "unproductive",
    "idle": "unproductive"
}

def get_session_window(dt, window_minutes=SESSION_WINDOW_MINUTES):
    window_start = dt.replace(second=0, microsecond=0)
    minutes = (window_start.minute // window_minutes) * window_minutes
    window_start = window_start.replace(minute=minutes)
    window_end = window_start + timedelta(minutes=window_minutes)
    session_id = window_start.strftime("%Y%m%d_%H%M")
    return session_id, window_start, window_end

def classify_activity(text):
    result = classifier(
        text,
        candidate_labels=ACTIVITY_LABELS
    )
    return result['labels'][0], float(result['scores'][0])

def activity_to_productivity(activity_label):
    return PRODUCTIVITY_MAP.get(activity_label, "unproductive")

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

@app.route("/upload", methods=["POST"])
def upload():
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
    productivity_label = activity_to_productivity(activity_label)
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

        user_settings.camera_enabled = data['camera_enabled']
        user_settings.screen_enabled = data['screen_enabled']

    except:
        return "", 200

    return "", 200


@app.route('/update_profile', methods=['POST'])
def update_profile():
    
    data = json.loads(request.data)

    user_profile.user_name = data['name']
    user_profile.blocklist = data['blocklist']

    return "", 200

if __name__ == '__main__':
    app.run()