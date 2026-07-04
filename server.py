import json
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_file

import map as map_module
from config import AppConfig

app = Flask(__name__)
cfg = AppConfig()


def load_prefs() -> dict:
    if cfg.prefs_file.exists():
        return json.loads(cfg.prefs_file.read_text())
    return {}


@app.route("/")
def index():
    return send_file(Path(cfg.output_path).resolve())


@app.route("/api/prefs", methods=["GET"])
def get_prefs():
    return jsonify(load_prefs())


@app.route("/api/prefs", methods=["POST"])
def save_prefs():
    prefs = request.get_json()
    cfg.prefs_file.write_text(json.dumps(prefs, indent=2))
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("Generating map...")
    map_module.main(initial_prefs=load_prefs(), config=cfg)
    webbrowser.open(f"http://localhost:{cfg.port}")
    app.run(host="localhost", port=cfg.port)
