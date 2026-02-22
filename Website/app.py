from flask import Flask, request, render_template, redirect, url_for, jsonify
import cv2
import pytesseract
import os
import csv
import json
from datetime import datetime
from transformers import pipeline
from openai import OpenAI

class Settings:
    def __init__(self, system, camera, screen):
        self.system_enabled = system
        self.camera_enabled = camera
        self.screen_enabled = screen

class Profile:
    def __init__(self, name, job, project):
        self.user_name = name
        self.user_job = job
        self.user_project = project
    
class Categories: 
    def __init__(self, productive, unproductive):
        self.productive = productive if isinstance(productive, list) else [productive]
        self.unproductive = unproductive if isinstance(unproductive, list) else [unproductive]

app = Flask(__name__)

# Configure OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    print("Warning: OPENAI_API_KEY not set. Set it with: export OPENAI_API_KEY='your-key-here'")
    client = None

user_settings = Settings(False, False, False)
user_profile = Profile("John Smith", "Software Engineer", "Making Github 2")
user_categories = Categories([], [])

# Initialize with default categories
user_categories.productive = ["vscode", "github", "documentation", "slack", "email"]
user_categories.unproductive = ["instagram", "youtube", "twitter", "tiktok", "reddit"]

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

def set_categories():
    """Set categories based on profile settings using OpenAI ChatGPT (with caching)"""
    global user_categories
    
    if not client:
        print("OpenAI API not configured. Using default categories.")
        return
    
    try:
        # Get the user's job and project
        job = user_profile.user_job
        project = user_profile.user_project
        
        # Create a cache key from job and project
        cache_key = f"{job}|{project}"
        
        # Check if categories are cached
        if os.path.exists(categories_cache_file):
            try:
                with open(categories_cache_file, 'r') as f:
                    cache = json.load(f)
                    if cache_key in cache:
                        print(f"Loading categories from cache for: {job} / {project}")
                        cached_cats = cache[cache_key]
                        user_categories.productive = cached_cats['productive']
                        user_categories.unproductive = cached_cats['unproductive']
                        return
            except:
                pass
        
        print(f"Generating categories from ChatGPT for: {job} / {project}")
        
        # Create concise prompt
        prompt = f"List 5 productive and 5 unproductive activities for a {job} working on {project}.\nFormat:\nproductive: item1, item2, item3, item4, item5\nunproductive: item1, item2, item3, item4, item5"
        
        # Query ChatGPT with faster model
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        # Parse the response
        response_text = response.choices[0].message.content
        if response_text:
            lines = response_text.strip().split('\n')
            for line in lines:
                if line.startswith('productive:'):
                    items = line.replace('productive:', '').strip().split(',')
                    user_categories.productive = [item.strip() for item in items if item.strip()]
                elif line.startswith('unproductive:'):
                    items = line.replace('unproductive:', '').strip().split(',')
                    user_categories.unproductive = [item.strip() for item in items if item.strip()]
            
            # Cache the results
            cache = {}
            if os.path.exists(categories_cache_file):
                try:
                    with open(categories_cache_file, 'r') as f:
                        cache = json.load(f)
                except:
                    pass
            
            cache[cache_key] = {
                'productive': user_categories.productive,
                'unproductive': user_categories.unproductive
            }
            
            with open(categories_cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
            
            print(f"Categories set and cached:")
            print(f"  Productive: {user_categories.productive}")
            print(f"  Unproductive: {user_categories.unproductive}")
    except Exception as e:
        print(f"Error setting categories: {e}")
        # Keep default categories if API call fails
        pass

@app.route("/upload", methods=["POST"])
def upload():
    image = request.files["image"]
        
    # Check if categories are set
    if not user_categories.productive or not user_categories.unproductive:
        return jsonify({
            "status": "error",
            "message": "Categories not set. Please update your profile first."
        }), 400
        
    # save or OCR here
    frame_path = os.path.join(app_dir, "frame.jpg")
    image.save(frame_path)

    img = cv2.imread(frame_path)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(gray)
    
    text_path = os.path.join(app_dir, "text.txt")
    with open(text_path, 'w') as f:
        f.write(text)

    # Use categories from user_categories class
    all_categories = user_categories.productive + user_categories.unproductive
    
    result = classifier(
        text,
        candidate_labels=all_categories
    )

    # Get the label with highest probability
    top_label = result['labels'][0]
    top_probability = result['scores'][0]
    
    # Evaluate if the predicted label is in productive or unproductive list
    productivity_status = "unknown"
    if any(top_label.lower() == cat.lower() for cat in user_categories.productive):
        productivity_status = "productive"
    elif any(top_label.lower() == cat.lower() for cat in user_categories.unproductive):
        productivity_status = "unproductive"

    print(f"Top Label: {top_label}, Probability: {top_probability}, Status: {productivity_status}")
    
    # Log the result
    log_result(top_label, top_probability, productivity_status)

    return jsonify({
        "status": "received", 
        "label": top_label, 
        "probability": float(top_probability),
        "productivity": productivity_status
    })

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global user_settings, user_profile

    return render_template(
        "settings.html", 
        user_settings=user_settings,
        user_profile=user_profile)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    user_settings.system_enabled = request.form.get("system_enabled")
    user_settings.camera_enabled = request.form.get("camera_enabled")
    user_settings.screen_enabled = request.form.get("screen_enabled")

    return redirect(url_for("index"))


@app.route('/update_profile', methods=['POST'])
def update_profile():
    global user_categories
    
    user_profile.user_name = request.form.get("name")
    user_profile.user_job = request.form.get("job_title")
    user_profile.user_project = request.form.get("project_desc")
    
    # Set categories based on updated profile
    set_categories()

    return redirect(url_for("settings"))

if __name__ == '__main__':
    app.run(debug=True)