from flask import Flask, request, render_template, jsonify
import cv2
import pytesseract
import os
import csv
from datetime import datetime
from transformers import pipeline

app = Flask(__name__)

# Get the directory where this app.py file is located
app_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(app_dir, "models")
log_file = os.path.join(app_dir, "results.csv")

# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

# Initialize CSV log file with headers if it doesn't exist
if not os.path.exists(log_file):
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Label', 'Probability'])

# create an application init to download the classifier
classifier_path = os.path.join(models_dir, "productivity_classifier")
if not os.path.exists(classifier_path):
    print("File not found. Downloading classifier")
    classifier = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )
    classifier.save_pretrained(classifier_path)
else:
    print("Model found.")
    classifier = pipeline(
        "zero-shot-classification",
        model=classifier_path
    )

def log_result(label, probability):
    """Log classification result with timestamp to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, label, probability])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['username']
        return f"Hello {name}, POST request received"
    return render_template('index.html')


@app.route("/upload", methods=["POST"])
def upload():
    image = request.files["image"]
    categories = request.form.get("categories")
    categories_list = eval(categories)  # Convert JSON string to list
    
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
        candidate_labels=categories_list
    )

    # Get the label with highest probability
    top_label = result['labels'][0]
    top_probability = result['scores'][0]

    print(f"Top Label: {top_label}, Probability: {top_probability}")
    
    # Log the result
    log_result(top_label, top_probability)

    return jsonify({"status": "received", "label": top_label, "probability": float(top_probability)})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)