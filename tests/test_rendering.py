import json
import math
from pathlib import Path

import folium
import pandas as pd
import pytest

from config import AppConfig
from rendering import (
    CONTROLS_HTML,
    INTERACTION_JS,
    build_map,
    format_area,
    format_price,
    make_icon,
    make_popup,
    post_process_html,
)


# ---------------------------------------------------------------------------
# format_price
# ---------------------------------------------------------------------------

def test_format_price_integer():
    assert format_price(1075000) == "$1,075,000"


def test_format_price_float():
    assert format_price(1075000.0) == "$1,075,000"


def test_format_price_nan():
    assert format_price(float("nan")) == "POA"


def test_format_price_pd_na():
    assert format_price(pd.NA) == "POA"


# ---------------------------------------------------------------------------
# format_area
# ---------------------------------------------------------------------------

def test_format_area_valid():
    assert format_area(256) == "256 m²"


def test_format_area_float():
    assert format_area(256.7) == "257 m²"


def test_format_area_empty_string():
    assert format_area("") == "—"


def test_format_area_nan():
    assert format_area(float("nan")) == "—"


def test_format_area_custom_unit():
    assert format_area(100, "ft²") == "100 ft²"


def test_format_area_non_numeric_string():
    assert format_area("N/A") == "—"


def test_format_price_non_scalar_raises_no_error():
    # pd.isna([1,2]) would raise TypeError — should fall through to formatting
    result = format_price(1000)
    assert result == "$1,000"


def test_format_area_list_falls_through():
    # pd.isna on a list raises TypeError — should fall through to float conversion
    assert format_area("42") == "42 m²"


# ---------------------------------------------------------------------------
# make_popup
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_row():
    return pd.Series({
        "LISTING_TITLE": "Nice House",
        "URL": "https://example.com/listing/123",
        "STREET_NUMBER": "42",
        "STREET": "Main Street",
        "SUBURB": "Auckland,Auckland City,Mount Albert",
        "EXPECTED_SALE_PRICE": 1200000.0,
        "RATEABLE_VALUE": 1100000.0,
        "BEDROOM_COUNT": 3.0,
        "BATHROOM_COUNT": 2.0,
        "GARAGE_PARKING_COUNT": 1.0,
        "LAND_AREA_IN_M2": 500.0,
        "FLOOR_AREA": 150.0,
        "SALE_TYPE": "Auction",
    })


def test_make_popup_contains_address(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "42" in html
    assert "Main Street" in html


def test_make_popup_contains_suburb(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "Mount Albert" in html


def test_make_popup_contains_price(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "$1,200,000" in html


def test_make_popup_contains_beds_and_baths(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "3" in html
    assert "2" in html


def test_make_popup_has_view_listing_link(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "View listing" in html
    assert "https://example.com/listing/123" in html


def test_make_popup_falls_back_to_trademe_url(sample_row):
    sample_row["URL"] = ""
    sample_row["LISTING_ID"] = 5920645336
    html = make_popup(sample_row, "abc123")
    assert "trademe.co.nz" in html
    assert "5920645336" in html
    assert "View listing" in html


def test_make_popup_no_link_when_no_url_and_no_listing_id(sample_row):
    sample_row["URL"] = ""
    sample_row["LISTING_ID"] = float("nan")
    html = make_popup(sample_row, "abc123")
    assert "View listing" not in html


def test_make_popup_has_mark_buttons(sample_row):
    html = make_popup(sample_row, "abc123")
    assert "fmahMark('abc123','interested')" in html
    assert "fmahMark('abc123','uninterested')" in html


def test_make_popup_price_poa_when_missing(sample_row):
    sample_row["EXPECTED_SALE_PRICE"] = float("nan")
    html = make_popup(sample_row, "abc123")
    assert "POA" in html


# ---------------------------------------------------------------------------
# make_icon
# ---------------------------------------------------------------------------

def test_make_icon_returns_divicon():
    icon = make_icon("12345", "#2ECC71", "#27AE60")
    assert isinstance(icon, folium.DivIcon)


def test_make_icon_contains_listing_id():
    icon = make_icon("12345", "#2ECC71", "#27AE60")
    assert "mk12345" in icon.options["html"]


def test_make_icon_contains_fill_color():
    icon = make_icon("12345", "#2ECC71", "#27AE60")
    assert "#2ECC71" in icon.options["html"]


def test_make_icon_has_mke_span():
    icon = make_icon("12345", "#2ECC71", "#27AE60")
    assert 'class="mke"' in icon.options["html"]


# ---------------------------------------------------------------------------
# build_map
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config(tmp_path):
    return AppConfig(data_dir=tmp_path, output_path=tmp_path / "map.html")


@pytest.fixture
def minimal_df():
    return pd.DataFrame([
        {
            "LATITUDE": -36.88, "LONGITUDE": 174.73,
            "LISTING_ID": 111, "LISTING_TITLE": "House A",
            "URL": "", "STREET_NUMBER": "1", "STREET": "Test St",
            "SUBURB": "Auckland,Auckland City,Mount Albert",
            "EXPECTED_SALE_PRICE": 1000000.0, "RATEABLE_VALUE": 900000.0,
            "BEDROOM_COUNT": 3.0, "BATHROOM_COUNT": 2.0,
            "GARAGE_PARKING_COUNT": 1.0, "LAND_AREA_IN_M2": 400.0,
            "FLOOR_AREA": 120.0, "SALE_TYPE": "Auction",
        }
    ])


@pytest.fixture
def minimal_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [174.70, -36.90],
                    [174.75, -36.90],
                    [174.75, -36.85],
                    [174.70, -36.85],
                    [174.70, -36.90],
                ]]
            },
            "properties": {"Hazard": "Flood Plain"},
        }]
    }


@pytest.fixture
def minimal_school_zone():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [174.70, -36.92],
                    [174.76, -36.92],
                    [174.76, -36.83],
                    [174.70, -36.83],
                    [174.70, -36.92],
                ]]
            },
            "properties": {},
        }]
    }


def test_build_map_creates_output_file(minimal_config, minimal_df, minimal_geojson, minimal_school_zone):
    flood_data = {
        "flood_plains": minimal_geojson,
        "flood_prone": minimal_geojson,
    }
    school_zones = {
        69: minimal_school_zone,
        1282: minimal_school_zone,
    }
    build_map(minimal_df, flood_data, school_zones, [], minimal_config, {})
    assert minimal_config.output_path.exists()


def test_build_map_output_is_html(minimal_config, minimal_df, minimal_geojson, minimal_school_zone):
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    build_map(minimal_df, flood_data, school_zones, [], minimal_config, {})
    content = minimal_config.output_path.read_text()
    assert "<html" in content.lower()
    assert "leaflet" in content.lower()


def test_build_map_embeds_prefs(minimal_config, minimal_df, minimal_geojson, minimal_school_zone):
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    prefs = {"99999": "interested"}
    build_map(minimal_df, flood_data, school_zones, [], minimal_config, prefs)
    content = minimal_config.output_path.read_text()
    assert "FMAH_PREFS" in content
    assert "99999" in content


# ---------------------------------------------------------------------------
# post_process_html
# ---------------------------------------------------------------------------

def test_build_map_with_schools(minimal_config, minimal_df, minimal_geojson, minimal_school_zone):
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    schools = [
        # Highlighted school
        {"School_Id": 69, "Org_Name": "Mt Albert Grammar School", "Latitude": -36.88,
         "Longitude": 174.72, "Decile": 8, "Total": 2200, "Org_Type": "Secondary", "Definition": None},
        # Regular school
        {"School_Id": 999, "Org_Name": "Test School", "Latitude": -36.87,
         "Longitude": 174.73, "Decile": 5, "Total": 300, "Org_Type": "Contributing", "Definition": None},
        # School with no lat/lng — should be skipped
        {"School_Id": 888, "Org_Name": "No Location School", "Latitude": None,
         "Longitude": None, "Decile": 3, "Total": 100, "Org_Type": "Contributing", "Definition": None},
    ]
    build_map(minimal_df, flood_data, school_zones, schools, minimal_config, {})
    assert minimal_config.output_path.exists()


def test_post_process_injects_prefs(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body></body></html>")
    prefs = {"12345": "interested"}
    post_process_html(html_file, prefs)
    content = html_file.read_text()
    assert "FMAH_PREFS" in content
    assert "12345" in content


def test_post_process_injects_controls(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body></body></html>")
    post_process_html(html_file, {})
    content = html_file.read_text()
    assert "fmah-undo" in content


def test_post_process_injects_interaction_js(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body></body></html>")
    post_process_html(html_file, {})
    content = html_file.read_text()
    assert "fmahMark" in content


def test_post_process_preserves_body_close(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body><p>content</p></body></html>")
    post_process_html(html_file, {})
    content = html_file.read_text()
    assert "</body>" in content
    assert "<p>content</p>" in content
