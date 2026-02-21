from flask import Flask, request, render_template, jsonify
import cv2
import pytesseract
import os
from transformers import pipeline

app = Flask(__name__)

# Ensure models directory exists
os.makedirs("./models", exist_ok=True)

# create an application init to download the classifier
if not os.path.exists("./models/productivity_classifier"):
    print("File not found. Downloading classifier")
    classifier = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )
    classifier.save_pretrained("./models/productivity_classifier")
else:
    print("Model found.")
    classifier = pipeline(
        "zero-shot-classification",
        model="./models/productivity_classifier"
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
    image.save("frame.jpg")

    img = cv2.imread("frame.jpg")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(gray)

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