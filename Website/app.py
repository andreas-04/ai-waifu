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
    user_name = None
    user_job = None
    user_project = None

    def __init__(self, name, job, project):
        self.user_name = name
        self.user_job = job
        self.user_project = project

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

#@app.route('/settings', methods=['GET', 'POST'])
#def settings():
#    global user_settings, user_profile
#
#    return render_template(
#        "settings.html", 
#        user_settings=user_settings,
#        user_profile=user_profile)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

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
    app.run()