import json
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file

import map as map_module

PREFS_FILE = Path("data/preferences.json")
PORT = 5000

app = Flask(__name__)


def load_prefs() -> dict:
    if PREFS_FILE.exists():
        return json.loads(PREFS_FILE.read_text())
    return {}


@app.route("/")
def index():
    return send_file(Path("map.html").resolve())


@app.route("/api/prefs", methods=["GET"])
def get_prefs():
    return jsonify(load_prefs())


@app.route("/api/prefs", methods=["POST"])
def save_prefs():
    prefs = request.get_json()
    PREFS_FILE.write_text(json.dumps(prefs, indent=2))
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("Generating map...")
    map_module.main(initial_prefs=load_prefs())
    webbrowser.open(f"http://localhost:{PORT}")
    app.run(host="localhost", port=PORT)
