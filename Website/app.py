from flask import Flask, request, render_template

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/report', methods=['GET'])
def report():
    return render_template('report.html')

if __name__ == '__main__':
    app.run()