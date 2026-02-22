from flask import Flask, request, render_template, jsonify
import cv2
import pytesseract
import os
import csv
import json
from datetime import datetime
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

    def __init__(self, system, camera, screen):
        self.system_enabled = system
        self.camera_enabled = camera
        self.screen_enabled = screen

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
    def __init__(self, name, job, project):
        self.user_name = name
        self.user_job = job
        self.user_project = project
    


app = Flask(__name__)

user_settings = Settings(False, False, False)

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
user_profile = Profile("John Smith", "Software Engineer", "Making Github 2")

# Get the directory where this app.py file is located
app_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(app_dir, "models")
log_file = os.path.join(app_dir, "results.csv")
categories_cache_file = os.path.join(app_dir, "categories_cache.json")

# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

# Initialize CSV log file with headers if it doesn't exist
if not os.path.exists(log_file):
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Label', 'Probability', 'Productivity'])

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

def log_result(label, probability, productivity="unknown"):
    """Log classification result with timestamp to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, label, probability, productivity])

def calculate_productivity_score():
    """Calculate productivity score out of 100 based on logged results"""
    if not os.path.exists(log_file):
        return 0
    
    productive_count = 0
    unproductive_count = 0
    
    try:
        with open(log_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = row['Label'].lower()
                if label == 'productive':
                    productive_count += 1
                elif label == 'unproductive':
                    unproductive_count += 1
        
        total_count = productive_count + unproductive_count
        if total_count == 0:
            return 0
        
        score = (productive_count / total_count) * 100
        return round(score, 2)
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
    
    result = classifier(
        text,
        candidate_labels=["productive", "unproductive"]
    )

    # Get the label with highest probability
    top_label = result['labels'][0]
    top_probability = result['scores'][0]

    
    # Log the result
    log_result(top_label, top_probability)

    # Calculate overall productivity score
    productivity_score = calculate_productivity_score()

    return jsonify({
        "status": "received", 
        "label": top_label, 
        "probability": float(top_probability),
        "productivity_score": productivity_score
    })

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

@app.route('/update_settings', methods=['POST'])
def update_settings():
    data = json.loads(request.data)
    print(data)

    try:
        user_settings.system_enabled = data['system_enabled']
        user_settings.track_productivity = data['productivity_enabled']
        user_settings.track_focus = data['focus_enabled']
        user_settings.track_hydration = data['hydration_enabled']
        user_settings.track_posture = data['posture_enabled']
        user_settings.selected_voice = data['voice_selection']

        user_settings.camera_enabled = data['camera_enabled']
        user_settings.screen_enabled = data['screen_enabled']

    except:
        print("BAH")
        return "", 200

    return "", 200


@app.route('/update_profile', methods=['POST'])
def update_profile():
    
    data = json.loads(request.data)

    user_profile.user_name = data['name']
    user_profile.user_job = data['job_title']
    user_profile.user_project = data['project_desc']

    return "", 200

if __name__ == '__main__':
    app.run(debug=True)