"""Tests for the map.py orchestrator."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config import AppConfig
from map import _norm_suburb, main


# ---------------------------------------------------------------------------
# _norm_suburb
# ---------------------------------------------------------------------------

def test_norm_suburb_lowercase():
    assert _norm_suburb("Grey Lynn") == "grey lynn"


def test_norm_suburb_mount_to_mt():
    assert _norm_suburb("Mount Albert") == "mt albert"


def test_norm_suburb_already_mt():
    assert _norm_suburb("Mt Eden") == "mt eden"


def test_norm_suburb_strips_whitespace():
    assert _norm_suburb("  Westmere  ") == "westmere"


# ---------------------------------------------------------------------------
# main() — all external calls mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config(tmp_path):
    cfg = AppConfig(data_dir=tmp_path, output_path=tmp_path / "map.html")
    # Create a minimal CSV so main() can load it
    csv = tmp_path / "Housing_test.csv"
    csv.write_text(
        'LATITUDE,LONGITUDE,LISTING_ID,LISTING_TITLE,URL,STREET_NUMBER,STREET,'
        'SUBURB,EXPECTED_SALE_PRICE,RATEABLE_VALUE,BEDROOM_COUNT,BATHROOM_COUNT,'
        'GARAGE_PARKING_COUNT,LAND_AREA_IN_M2,FLOOR_AREA,SALE_TYPE\n'
        '-36.88,174.73,111,House A,https://x.com,1,Alpha St,'
        '"Auckland,Auckland City,Mount Albert",1000000,900000,3,2,1,400,120,Auction\n'
    )
    return cfg


def _flood_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [174.70, -36.92], [174.76, -36.92],
                    [174.76, -36.83], [174.70, -36.83],
                    [174.70, -36.92],
                ]]
            },
            "properties": {"Hazard": "Flood Plain"},
        }]
    }


def _zone_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [174.70, -36.92], [174.76, -36.92],
                    [174.76, -36.83], [174.70, -36.83],
                    [174.70, -36.92],
                ]]
            },
            "properties": {},
        }]
    }


def test_main_creates_output_file(mock_config):
    flood = _flood_geojson()
    zone = _zone_geojson()
    schools = []

    with patch("map.fetch_flood_features", return_value=flood), \
         patch("map.fetch_school_zone", return_value=zone), \
         patch("map.fetch_schools_in_area", return_value=schools):
        main(initial_prefs={}, config=mock_config)

    assert mock_config.output_path.exists()


def test_main_loads_prefs_from_file(mock_config):
    import json
    mock_config.prefs_file.write_text(json.dumps({"999": "interested"}))
    flood = _flood_geojson()
    zone = _zone_geojson()

    with patch("map.fetch_flood_features", return_value=flood), \
         patch("map.fetch_school_zone", return_value=zone), \
         patch("map.fetch_schools_in_area", return_value=[]):
        main(config=mock_config)

    content = mock_config.output_path.read_text()
    assert "999" in content


def test_main_uses_default_config_when_none(tmp_path):
    """main() with no config should construct AppConfig() internally."""
    flood = _flood_geojson()
    zone = _zone_geojson()
    cfg = AppConfig(data_dir=tmp_path, output_path=tmp_path / "map.html")
    csv = tmp_path / "Housing_test.csv"
    csv.write_text(
        'LATITUDE,LONGITUDE,LISTING_ID,LISTING_TITLE,URL,STREET_NUMBER,STREET,'
        'SUBURB,EXPECTED_SALE_PRICE,RATEABLE_VALUE,BEDROOM_COUNT,BATHROOM_COUNT,'
        'GARAGE_PARKING_COUNT,LAND_AREA_IN_M2,FLOOR_AREA,SALE_TYPE\n'
        '-36.88,174.73,111,H,https://x.com,1,A St,'
        '"Auckland,Auckland City,Mt Albert",1000000,900000,3,2,1,400,120,Auction\n'
    )
    with patch("map.AppConfig", return_value=cfg), \
         patch("map.fetch_flood_features", return_value=flood), \
         patch("map.fetch_school_zone", return_value=zone), \
         patch("map.fetch_schools_in_area", return_value=[]):
        main(initial_prefs={})
