"""Tests for server.py Flask endpoints."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import server
from config import AppConfig


@pytest.fixture
def client(tmp_path):
    cfg = AppConfig(data_dir=tmp_path, output_path=tmp_path / "map.html")
    # Write a minimal map.html so send_file has something to serve
    (tmp_path / "map.html").write_text("<html><body>map</body></html>")
    server.cfg = cfg
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_get_prefs_empty(client, tmp_path):
    resp = client.get("/api/prefs")
    assert resp.status_code == 200
    assert resp.get_json() == {}


def test_get_prefs_returns_saved(client, tmp_path):
    prefs_file = tmp_path / "preferences.json"
    prefs_file.write_text(json.dumps({"123": "interested"}))
    resp = client.get("/api/prefs")
    assert resp.get_json() == {"123": "interested"}


def test_post_prefs_saves_to_file(client, tmp_path):
    prefs = {"456": "uninterested"}
    resp = client.post("/api/prefs", json=prefs)
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    saved = json.loads((tmp_path / "preferences.json").read_text())
    assert saved == prefs


def test_post_prefs_overwrites_existing(client, tmp_path):
    (tmp_path / "preferences.json").write_text(json.dumps({"old": "interested"}))
    client.post("/api/prefs", json={"new": "uninterested"})
    saved = json.loads((tmp_path / "preferences.json").read_text())
    assert "new" in saved
    assert "old" not in saved


def test_index_serves_map_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"map" in resp.data
