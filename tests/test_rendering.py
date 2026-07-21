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
    _prepare_flood_geojson,
    _round_coords,
    build_map,
    format_area,
    format_price,
    make_icon,
    make_popup,
    post_process_html,
    write_flood_geojson,
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


def test_make_popup_falls_back_to_trademe_when_url_is_empty_string(sample_row):
    sample_row["URL"] = ""
    sample_row["LISTING_ID"] = 5920645336
    html = make_popup(sample_row, "abc123")
    assert "trademe.co.nz" in html
    assert "5920645336" in html


def test_make_popup_falls_back_to_trademe_when_url_is_nan(sample_row):
    # pandas reads missing CSV URL fields as float NaN, not empty string
    sample_row["URL"] = float("nan")
    sample_row["LISTING_ID"] = 5920645336
    html = make_popup(sample_row, "abc123")
    assert "trademe.co.nz" in html
    assert "5920645336" in html
    assert "nan" not in html  # must not link to literal "nan"


def test_make_popup_no_link_when_url_and_listing_id_both_missing(sample_row):
    sample_row["URL"] = float("nan")
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


def test_make_icon_default_class_name():
    icon = make_icon("12345", "#2ECC71", "#27AE60")
    assert icon.options["class_name"].startswith("fmah-marker")


def test_make_icon_out_zone_class_name():
    icon = make_icon("12345", "#EF9A9A", "#E53935", class_name="fmah-marker fmah-out-zone")
    assert "fmah-out-zone" in icon.options["class_name"]


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


def test_persist_falls_back_to_localstorage_on_non_ok_response():
    # A 404 from Vercel is a valid HTTP response — fetch() resolves, not rejects.
    # The JS must check r.ok and throw to reach the localStorage fallback.
    content = (
        Path(__file__).parent.parent / "rendering.py"
    ).read_text()
    assert "if (!r.ok) throw" in content, (
        "persist() must check r.ok — a 404 resolves fetch() and won't reach .catch()"
    )


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


def test_post_process_injects_flood_loader_when_config_given(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text(
        "<html><body></body>"
        "<script>var map_abc123 = L.map('x');\n"
        "var layer_control_abc123 = L.control.layers().addTo(map_abc123);\n"
        "</script>\n</html>"
    )
    flood_layer_config = [
        {"url": "flood_plains.json", "name": "Flood Plains", "fill": "#90CAF9",
         "stroke": "#64B5F6", "opacity": 0.35, "tooltipField": "Hazard"},
    ]
    post_process_html(html_file, {}, flood_layer_config)
    content = html_file.read_text()
    assert "map_abc123" in content
    assert "layer_control_abc123" in content
    assert "flood_plains.json" in content
    assert content.index("var map_abc123") < content.rindex("map_abc123")


def test_post_process_without_flood_config_unchanged(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body></body><script>var map_abc = 1;</script>\n</html>")
    post_process_html(html_file, {}, None)
    content = html_file.read_text()
    assert "fetch(cfg.url)" not in content


def test_post_process_raises_when_map_var_not_found(tmp_path):
    html_file = tmp_path / "map.html"
    html_file.write_text("<html><body></body><script>no map var here</script>\n</html>")
    flood_layer_config = [{"url": "x.json", "name": "X", "fill": "#fff", "stroke": "#000",
                            "opacity": 0.3, "tooltipField": None}]
    with pytest.raises(ValueError):
        post_process_html(html_file, {}, flood_layer_config)


# ---------------------------------------------------------------------------
# _round_coords
# ---------------------------------------------------------------------------

def test_round_coords_point():
    assert _round_coords([174.123456789, -36.987654321], 6) == [174.123457, -36.987654]


def test_round_coords_nested_polygon():
    coords = [[[174.1234567, -36.9876543], [174.2, -36.8]]]
    result = _round_coords(coords, 4)
    assert result == [[[174.1235, -36.9877], [174.2, -36.8]]]


# ---------------------------------------------------------------------------
# _prepare_flood_geojson / write_flood_geojson
# ---------------------------------------------------------------------------

def test_prepare_flood_geojson_rounds_coordinates(sample_geojson):
    sample_geojson["features"][0]["geometry"]["coordinates"] = [[[174.123456789, -36.987654321]] * 4]
    result = _prepare_flood_geojson(sample_geojson, tolerance=0, keep_properties=["Hazard"])
    coords = result["features"][0]["geometry"]["coordinates"][0][0]
    assert coords == [174.123457, -36.987654]


def test_prepare_flood_geojson_strips_properties(sample_geojson):
    result = _prepare_flood_geojson(sample_geojson, tolerance=0, keep_properties=[])
    assert result["features"][0]["properties"] == {}


def test_prepare_flood_geojson_keeps_specified_properties(sample_geojson):
    result = _prepare_flood_geojson(sample_geojson, tolerance=0, keep_properties=["Hazard"])
    assert result["features"][0]["properties"] == {"Hazard": "Flood Plain"}


def test_write_flood_geojson_creates_files(tmp_path, sample_geojson):
    config = AppConfig(data_dir=tmp_path, output_path=tmp_path / "index.html")
    flood_data = {"flood_plains": sample_geojson, "flood_prone": sample_geojson}
    written = write_flood_geojson(flood_data, config)
    assert (tmp_path / "flood_plains.json").exists()
    assert (tmp_path / "flood_prone.json").exists()
    assert len(written) == 2


def test_write_flood_geojson_strips_properties_per_layer(tmp_path, sample_geojson):
    config = AppConfig(data_dir=tmp_path, output_path=tmp_path / "index.html")
    flood_data = {"flood_plains": sample_geojson, "flood_prone": sample_geojson}
    write_flood_geojson(flood_data, config)
    plains = json.loads((tmp_path / "flood_plains.json").read_text())
    prone = json.loads((tmp_path / "flood_prone.json").read_text())
    assert plains["features"][0]["properties"] == {"Hazard": "Flood Plain"}
    assert prone["features"][0]["properties"] == {}


# ---------------------------------------------------------------------------
# build_map with externalize_flood
# ---------------------------------------------------------------------------

def test_build_map_externalize_flood_writes_external_files(minimal_df, minimal_geojson, minimal_school_zone, tmp_path):
    config = AppConfig(data_dir=tmp_path, output_path=tmp_path / "index.html", externalize_flood=True)
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    build_map(minimal_df, flood_data, school_zones, [], config, {})
    assert (tmp_path / "flood_plains.json").exists()
    assert (tmp_path / "flood_prone.json").exists()


def test_build_map_externalize_flood_excludes_inline_geojson(minimal_df, minimal_geojson, minimal_school_zone, tmp_path):
    config = AppConfig(data_dir=tmp_path, output_path=tmp_path / "index.html", externalize_flood=True)
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    build_map(minimal_df, flood_data, school_zones, [], config, {})
    content = config.output_path.read_text()
    # -36.85 only appears in the flood polygon fixture — must not be inlined
    assert "-36.85" not in content
    assert "fetch(" in content
    assert "flood_plains.json" in content
    assert "flood_prone.json" in content


def test_build_map_default_does_not_write_external_files(minimal_config, minimal_df, minimal_geojson, minimal_school_zone):
    flood_data = {"flood_plains": minimal_geojson, "flood_prone": minimal_geojson}
    school_zones = {69: minimal_school_zone, 1282: minimal_school_zone}
    build_map(minimal_df, flood_data, school_zones, [], minimal_config, {})
    assert not (minimal_config.output_path.parent / "flood_plains.json").exists()
    content = minimal_config.output_path.read_text()
    assert "fetch(cfg.url)" not in content
