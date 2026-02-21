from flask import Flask, request, render_template, jsonify
import cv2
import pytesseract
import os
from transformers import pipeline

app = Flask(__name__)

# Get the directory where this app.py file is located
app_dir = os.path.dirname(os.path.abspath(__file__))
models_dir = os.path.join(app_dir, "models")

# Ensure models directory exists
os.makedirs(models_dir, exist_ok=True)

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['username']
        return f"Hello {name}, POST request received"
    return render_template('index.html')


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
        candidate_labels=[
            "work",
            "education",
            "communication",
            "entertainment",
            "social media"
        ]
    )

    # Get the label with highest probability
    top_label = result['labels'][0]
    top_probability = result['scores'][0]

    print(f"Top Label: {top_label}, Probability: {top_probability}")

    return jsonify({"status": "received", "label": top_label, "probability": float(top_probability)})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)