import json
from unittest.mock import MagicMock, patch

import pytest

from config import AppConfig, SCHOOL_COLOR_PALETTE
from manage_schools import (
    build_parser,
    cmd_add,
    cmd_list,
    cmd_remove,
    derive_short_name,
    fetch_school_by_id,
    load_config,
    next_color,
    save_config,
    search_schools,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg(tmp_path):
    return AppConfig(data_dir=tmp_path)


@pytest.fixture
def cfg_with_schools(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    save_config({
        69: {"name": "Mt Albert Grammar School", "short": "MAGS",
             "zone_fill": "#A5D6A7", "zone_stroke": "#66BB6A", "marker_bg": "#43A047"},
        1282: {"name": "Gladstone School (Auckland)", "short": "Gladstone",
               "zone_fill": "#CE93D8", "zone_stroke": "#AB47BC", "marker_bg": "#8E24AA"},
    }, cfg)
    return cfg


# ---------------------------------------------------------------------------
# config.py: __post_init__ loads from schools_config.json
# ---------------------------------------------------------------------------

def test_appconfig_loads_from_schools_config_json(tmp_path):
    (tmp_path / "schools_config.json").write_text(json.dumps({
        "74": {"name": "Mt Roskill Grammar School", "short": "MRG",
               "zone_fill": "#A", "zone_stroke": "#B", "marker_bg": "#C"}
    }))
    cfg = AppConfig(data_dir=tmp_path)
    assert 74 in cfg.highlight_schools
    assert 69 not in cfg.highlight_schools


def test_appconfig_uses_defaults_when_no_config_file(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    assert 69 in cfg.highlight_schools
    assert 1282 in cfg.highlight_schools


def test_appconfig_schools_config_file_property(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    assert cfg.schools_config_file == tmp_path / "schools_config.json"


# ---------------------------------------------------------------------------
# load_config / save_config
# ---------------------------------------------------------------------------

def test_load_config_reads_from_file(cfg_with_schools):
    schools = load_config(cfg_with_schools)
    assert 69 in schools and 1282 in schools


def test_load_config_falls_back_to_defaults(cfg):
    schools = load_config(cfg)
    assert 69 in schools


def test_save_config_writes_json(cfg):
    save_config({99: {"name": "Test School", "short": "TS"}}, cfg)
    raw = json.loads(cfg.schools_config_file.read_text())
    assert "99" in raw
    assert raw["99"]["name"] == "Test School"


def test_save_config_creates_directory(tmp_path):
    cfg = AppConfig(data_dir=tmp_path / "nested")
    save_config({99: {"name": "Test"}}, cfg)
    assert cfg.schools_config_file.exists()


# ---------------------------------------------------------------------------
# next_color
# ---------------------------------------------------------------------------

def test_next_color_cycles_palette():
    for i in range(len(SCHOOL_COLOR_PALETTE) + 2):
        schools = {k: {} for k in range(i)}
        color = next_color(schools)
        assert color == SCHOOL_COLOR_PALETTE[i % len(SCHOOL_COLOR_PALETTE)]


def test_next_color_returns_dict_with_required_keys():
    color = next_color({})
    assert {"zone_fill", "zone_stroke", "marker_bg"} <= color.keys()


# ---------------------------------------------------------------------------
# derive_short_name
# ---------------------------------------------------------------------------

def test_derive_short_name_two_words():
    assert derive_short_name("Mt Albert Grammar School") == "MAG"


def test_derive_short_name_single_word():
    assert derive_short_name("Gladstone") == "Gladstone"


def test_derive_short_name_two_word_name():
    assert derive_short_name("Westmere School") == "Westmere"


# ---------------------------------------------------------------------------
# search_schools / fetch_school_by_id (HTTP mocked)
# ---------------------------------------------------------------------------

def _mock_features(attrs_list):
    return MagicMock(json=lambda: {
        "features": [{"attributes": a} for a in attrs_list]
    })


def test_search_schools_returns_attributes():
    schools = [{"School_Id": 74, "Org_Name": "Mt Roskill Grammar School", "Org_Type": "Secondary (Year 9-15)"}]
    with patch("manage_schools.requests.get", return_value=_mock_features(schools)):
        result = search_schools("Roskill")
    assert result == schools


def test_search_schools_empty():
    with patch("manage_schools.requests.get", return_value=_mock_features([])):
        assert search_schools("Nonexistent XYZ") == []


def test_fetch_school_by_id_found():
    s = {"School_Id": 74, "Org_Name": "Mt Roskill Grammar School", "Org_Type": "Secondary"}
    with patch("manage_schools.requests.get", return_value=_mock_features([s])):
        assert fetch_school_by_id(74) == s


def test_fetch_school_by_id_not_found():
    with patch("manage_schools.requests.get", return_value=_mock_features([])):
        assert fetch_school_by_id(9999) is None


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

def test_cmd_list_prints_schools(cfg_with_schools, capsys):
    cmd_list(build_parser().parse_args(["list"]), cfg_with_schools)
    out = capsys.readouterr().out
    assert "MAGS" in out
    assert "Gladstone" in out


def test_cmd_list_empty(cfg, capsys):
    # Write an empty config
    save_config({}, cfg)
    cmd_list(build_parser().parse_args(["list"]), cfg)
    assert "No schools" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

def test_cmd_add_by_id(cfg, capsys):
    s = {"School_Id": 74, "Org_Name": "Mt Roskill Grammar School", "Org_Type": "Secondary"}
    with patch("manage_schools.fetch_school_by_id", return_value=s):
        cmd_add(build_parser().parse_args(["add", "--id", "74"]), cfg)
    schools = load_config(cfg)
    assert 74 in schools
    assert schools[74]["name"] == "Mt Roskill Grammar School"
    assert "MRG" == schools[74]["short"]


def test_cmd_add_by_id_with_custom_short(cfg):
    s = {"School_Id": 74, "Org_Name": "Mt Roskill Grammar School", "Org_Type": "Secondary"}
    with patch("manage_schools.fetch_school_by_id", return_value=s):
        cmd_add(build_parser().parse_args(["add", "--id", "74", "--short", "MRGS"]), cfg)
    assert load_config(cfg)[74]["short"] == "MRGS"


def test_cmd_add_assigns_color(cfg):
    s = {"School_Id": 74, "Org_Name": "Mt Roskill Grammar School", "Org_Type": "Secondary"}
    with patch("manage_schools.fetch_school_by_id", return_value=s):
        cmd_add(build_parser().parse_args(["add", "--id", "74"]), cfg)
    info = load_config(cfg)[74]
    assert "zone_fill" in info and "zone_stroke" in info and "marker_bg" in info


def test_cmd_add_already_exists(cfg_with_schools, capsys):
    s = {"School_Id": 69, "Org_Name": "Mt Albert Grammar School", "Org_Type": "Secondary"}
    with patch("manage_schools.fetch_school_by_id", return_value=s):
        cmd_add(build_parser().parse_args(["add", "--id", "69"]), cfg_with_schools)
    assert "already configured" in capsys.readouterr().out


def test_cmd_add_not_found_exits(cfg):
    with patch("manage_schools.fetch_school_by_id", return_value=None):
        with pytest.raises(SystemExit):
            cmd_add(build_parser().parse_args(["add", "--id", "9999"]), cfg)


# ---------------------------------------------------------------------------
# cmd_remove
# ---------------------------------------------------------------------------

def test_cmd_remove(cfg_with_schools):
    cmd_remove(build_parser().parse_args(["remove", "69"]), cfg_with_schools)
    schools = load_config(cfg_with_schools)
    assert 69 not in schools
    assert 1282 in schools


def test_cmd_remove_not_found_exits(cfg_with_schools):
    with pytest.raises(SystemExit):
        cmd_remove(build_parser().parse_args(["remove", "9999"]), cfg_with_schools)
