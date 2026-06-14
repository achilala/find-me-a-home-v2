from pathlib import Path
import pytest
from config import AppConfig


def test_default_bbox():
    cfg = AppConfig()
    assert cfg.bbox == "174.65,-36.95,174.82,-36.80"


def test_default_port():
    assert AppConfig().port == 5000


def test_default_data_dir():
    assert AppConfig().data_dir == Path("data")


def test_prefs_file_derived_from_data_dir():
    cfg = AppConfig()
    assert cfg.prefs_file == cfg.data_dir / "preferences.json"


def test_custom_data_dir_propagates_to_prefs_file():
    cfg = AppConfig(data_dir=Path("/tmp/test"))
    assert cfg.prefs_file == Path("/tmp/test/preferences.json")


def test_highlight_schools_contains_mags():
    assert 69 in AppConfig().highlight_schools


def test_highlight_schools_contains_gladstone():
    assert 1282 in AppConfig().highlight_schools


def test_highlight_school_has_required_keys():
    school = AppConfig().highlight_schools[69]
    for key in ("name", "short", "zone_fill", "zone_stroke", "marker_bg"):
        assert key in school


def test_flood_layers_contains_flood_plains():
    assert "flood_plains" in AppConfig().flood_layers


def test_flood_layers_contains_flood_prone():
    assert "flood_prone" in AppConfig().flood_layers


def test_flood_layer_has_required_keys():
    layer = AppConfig().flood_layers["flood_plains"]
    for key in ("url", "name", "fill", "stroke", "opacity"):
        assert key in layer


def test_listing_colors_has_in_zone():
    assert "in_zone" in AppConfig().listing_colors


def test_listing_colors_has_out_zone():
    assert "out_zone" in AppConfig().listing_colors


def test_listing_color_has_fill_and_stroke():
    colors = AppConfig().listing_colors["in_zone"]
    assert "fill" in colors and "stroke" in colors


def test_output_path_default():
    assert AppConfig().output_path == Path("map.html")


def test_school_zones_url_not_empty():
    assert AppConfig().school_zones_url.startswith("https://")


def test_schools_dir_url_not_empty():
    assert AppConfig().schools_dir_url.startswith("https://")
