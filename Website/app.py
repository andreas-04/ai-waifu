from flask import Flask, request, render_template, redirect, url_for, jsonify
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

    def __init__(self):
        self.system_enabled = True
        self.camera_enabled = False
        self.screen_enabled = False

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

    def __init__(self):
        self.user_name = None
        self.blocklist = ""

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

user_settings = Settings()
user_profile = Profile()

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

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