import atexit
import json
import os
import signal
import shutil
import subprocess
import sys

from flask import Flask, jsonify, request, render_template, redirect, url_for, send_file, abort

class Settings:
    system_enabled = False
    camera_enabled = False
    screen_enabled = False

    selected_voice = "Jessica"
    blocklist = ""
    prodlist = ""

    def __init__(
        self,
        system_enabled=True,
        camera_enabled=False,
        screen_enabled=False,
        selected_voice="Jessica",
        blocklist="",
        prodlist=""
    ):
        self.system_enabled = system_enabled
        self.camera_enabled = camera_enabled
        self.screen_enabled = screen_enabled
        self.selected_voice = selected_voice
        self.blocklist = blocklist
        self.prodlist = prodlist

    def print(self):
        print(self.system_enabled)
        print(self.camera_enabled)
        print(self.screen_enabled)

    def to_dict(self):
        return self.__dict__

class Profile:
    user_name = None
    blocklist = ""
    prodlist = ""

    def __init__(self, user_name=None, blocklist="", prodlist=""):
        self.user_name = user_name
        self.blocklist = blocklist
        self.prodlist = prodlist

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

# Absolute path to backend/main.py (one level up from Website/)
_BACKEND_MAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "main.py")
_VITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "websiteV2")
_backend_proc: subprocess.Popen | None = None
_vite_proc:    subprocess.Popen | None = None


def _start_vite():
    """Install deps if needed, then launch the Vite dev server as a child process."""
    global _vite_proc
    npm = shutil.which("npm") or "npm"
    # Install dependencies if node_modules is missing
    if not os.path.isdir(os.path.join(_VITE_DIR, "node_modules")):
        print(" * Running npm install in websiteV2 …")
        subprocess.run([npm, "install"], cwd=_VITE_DIR, check=True)
    _vite_proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=_VITE_DIR,
    )
    print(f" * Vite dev server started (pid {_vite_proc.pid}) → http://localhost:5173")


def _stop_vite():
    """Terminate Vite when Flask exits."""
    global _vite_proc
    if _vite_proc and _vite_proc.poll() is None:
        _vite_proc.terminate()
        try:
            _vite_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _vite_proc.kill()
    _vite_proc = None


atexit.register(_stop_vite)

user_settings = Settings(False, False, False, selected_voice="Jessica")
user_profile = Profile("John Smith")

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

@app.route('/get_productivity_score', methods=['GET'])
def get_productivity_score():
    """Placeholder — productivity is computed client-side from tracker scores."""
    return jsonify({"productivity_score": 0})

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
        user_settings.selected_voice = data['voice_selection']
        user_settings.blocklist = data['blocklist']
        user_settings.prodlist = data['prodlist']
        user_settings.camera_enabled = data['camera_enabled']
        user_settings.screen_enabled = data['screen_enabled']

    except:
        return "", 200

    return "", 200


@app.route('/update_profile', methods=['POST'])
def update_profile():
    user_profile.user_name = request.form.get("name")
    user_profile.user_job = request.form.get("job_title")
    user_profile.user_project = request.form.get("project_desc")

    return redirect(url_for("settings"))


# ── Camera service control ────────────────────────────────────────────────────

@app.route('/api/backend/start', methods=['POST'])
def backend_start():
    global _backend_proc

    # Gate: system must be enabled in settings
    if not user_settings.system_enabled:
        return jsonify({"status": "disabled", "reason": "System is not enabled in settings"}), 200

    if _backend_proc is not None and _backend_proc.poll() is None:
        return jsonify({"status": "already_running", "pid": _backend_proc.pid}), 200

    # Build CLI flags from current settings
    cmd = [sys.executable, _BACKEND_MAIN]

    _backend_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"status": "started", "pid": _backend_proc.pid}), 200


@app.route('/api/backend/stop', methods=['POST'])
def backend_stop():
    global _backend_proc
    if _backend_proc is None or _backend_proc.poll() is not None:
        _backend_proc = None
        return jsonify({"status": "not_running"}), 200
    try:
        # Send SIGINT (Ctrl+C) so the backend shuts down gracefully
        _backend_proc.send_signal(signal.SIGINT)
        _backend_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _backend_proc.kill()
    _backend_proc = None
    return jsonify({"status": "stopped"}), 200


@app.route('/api/backend/status', methods=['GET'])
def backend_status():
    running = _backend_proc is not None and _backend_proc.poll() is None
    pid = _backend_proc.pid if running else None
    return jsonify({"running": running, "pid": pid}), 200


# ── JSON settings / profile API (used by websiteV2) ──────────────────────────

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify({
        # System toggles
        "system_enabled":      bool(user_settings.system_enabled),
        "camera_enabled":      bool(user_settings.camera_enabled),
        "screen_enabled":      bool(user_settings.screen_enabled),
        # Misc
        "selected_voice":      user_settings.selected_voice or "Jessica",
        "blocklist":           user_settings.blocklist or "",
        "prodlist":            user_settings.prodlist or "",
        # Profile
        "user_name":           user_profile.user_name or "",
    }), 200


@app.route('/api/voices', methods=['GET'])
def api_get_voices():
    return jsonify(["Jessica", "Sarah", "Harry", "Daniel"]), 200


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    data = request.get_json(force=True) or {}
    user_settings.system_enabled     = data.get("system_enabled",     user_settings.system_enabled)
    user_settings.camera_enabled     = data.get("camera_enabled",     user_settings.camera_enabled)
    user_settings.screen_enabled     = data.get("screen_enabled",     user_settings.screen_enabled)
    user_settings.selected_voice     = data.get("selected_voice",     user_settings.selected_voice)
    user_settings.blocklist          = data.get("blocklist",          user_settings.blocklist)
    user_settings.prodlist           = data.get("prodlist",           user_settings.prodlist)
    return jsonify({"status": "ok"}), 200


@app.route('/api/profile', methods=['POST'])
def api_update_profile():
    data = request.get_json(force=True) or {}
    user_profile.user_name = data.get("name", user_profile.user_name)
    return jsonify({"status": "ok"}), 200

@app.route('/audio')
def audio():
    # Get the file parameter from query string
    file = request.args.get('source')

    if not file:
        return "No file specified", 400

    # Construct the file path (adjust your directory as needed)
    file_path = os.path.join('./static/audio', file)

    # Check if file exists
    if not os.path.exists(file_path):
        return "File not found", 404

    # Return the MP3 file
    return send_file(file_path, mimetype='audio/mpeg', as_attachment=False)


if __name__ == '__main__':
    _start_vite()
    app.run(port=5001)