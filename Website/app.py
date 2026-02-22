from flask import Flask, request, render_template, redirect, url_for

class Settings:
    system_enabled = False
    camera_enabled = False
    screen_enabled = False

    def __init__(self, system, camera, screen):
        system_enabled = system
        camera_enabled = camera
        screen_enabled = screen

class Profile:
    user_name = None
    user_job = None
    user_project = None

    def __init__(self, name, job, project):
        user_name = name
        user_job = job
        user_project = project

app = Flask(__name__)

user_settings = Settings(False, False, False)
user_profile = Profile("John Smith", "Software Engineer", "Making Github 2")

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
    user_profile.user_name = request.form.get("name")
    user_profile.user_job = request.form.get("job_title")
    user_profile.user_project = request.form.get("project_desc")

    return redirect(url_for("index"))

if __name__ == '__main__':
    app.run()