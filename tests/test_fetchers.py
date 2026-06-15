import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from config import AppConfig
from fetchers import (
    _extract_og_image,
    cached_fetch,
    fetch_flood_features,
    fetch_listing_thumbnails,
    fetch_school_zone,
    fetch_schools_in_area,
)


# ---------------------------------------------------------------------------
# cached_fetch
# ---------------------------------------------------------------------------

def test_cached_fetch_returns_cached_without_calling_fetcher(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"cached": True}))
    fetcher = MagicMock()

    result = cached_fetch(cache, fetcher)

    assert result == {"cached": True}
    fetcher.assert_not_called()


def test_cached_fetch_calls_fetcher_when_no_cache(tmp_path):
    cache = tmp_path / "cache.json"
    fetcher = MagicMock(return_value={"fresh": True})

    result = cached_fetch(cache, fetcher)

    assert result == {"fresh": True}
    fetcher.assert_called_once()


def test_cached_fetch_writes_file_after_fetch(tmp_path):
    cache = tmp_path / "cache.json"
    fetcher = MagicMock(return_value={"key": "value"})

    cached_fetch(cache, fetcher)

    assert cache.exists()
    assert json.loads(cache.read_text()) == {"key": "value"}


def test_cached_fetch_does_not_write_file_on_error(tmp_path):
    cache = tmp_path / "cache.json"
    fetcher = MagicMock(side_effect=RuntimeError("network error"))

    with pytest.raises(RuntimeError):
        cached_fetch(cache, fetcher)

    assert not cache.exists()


# ---------------------------------------------------------------------------
# fetch_school_zone
# ---------------------------------------------------------------------------

def test_fetch_school_zone_uses_cache(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    cache = tmp_path / "zone_69.geojson"
    zone_data = {"type": "FeatureCollection", "features": []}
    cache.write_text(json.dumps(zone_data))

    with patch("fetchers.requests.get") as mock_get:
        result = fetch_school_zone(69, cfg)

    mock_get.assert_not_called()
    assert result == zone_data


def test_fetch_school_zone_calls_api_when_no_cache(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    zone_data = {"type": "FeatureCollection", "features": [{"id": 1}]}

    mock_resp = MagicMock()
    mock_resp.json.return_value = zone_data

    with patch("fetchers.requests.get", return_value=mock_resp) as mock_get:
        result = fetch_school_zone(69, cfg)

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "School_ID = 69" in call_kwargs.kwargs["params"]["where"]
    assert result == zone_data


def test_fetch_school_zone_caches_result(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    zone_data = {"type": "FeatureCollection", "features": []}
    mock_resp = MagicMock()
    mock_resp.json.return_value = zone_data

    with patch("fetchers.requests.get", return_value=mock_resp):
        fetch_school_zone(69, cfg)

    cache = tmp_path / "zone_69.geojson"
    assert cache.exists()
    assert json.loads(cache.read_text()) == zone_data


# ---------------------------------------------------------------------------
# fetch_schools_in_area
# ---------------------------------------------------------------------------

def test_fetch_schools_in_area_filters_missing_latitude(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    raw_features = [
        {"attributes": {"Org_Name": "School A", "Latitude": -36.87, "Longitude": 174.73}},
        {"attributes": {"Org_Name": "School B", "Latitude": None}},
        {"attributes": {"Org_Name": "School C", "Latitude": -36.88, "Longitude": 174.74}},
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": raw_features}

    with patch("fetchers.requests.get", return_value=mock_resp):
        result = fetch_schools_in_area(cfg)

    assert len(result) == 2
    assert all(s["Latitude"] for s in result)


def test_fetch_schools_in_area_uses_cache(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    cached = [{"Org_Name": "Cached School", "Latitude": -36.87}]
    (tmp_path / "schools.json").write_text(json.dumps(cached))

    with patch("fetchers.requests.get") as mock_get:
        result = fetch_schools_in_area(cfg)

    mock_get.assert_not_called()
    assert result == cached


# ---------------------------------------------------------------------------
# fetch_flood_features
# ---------------------------------------------------------------------------

def test_fetch_flood_features_single_page(tmp_path):
    cache = tmp_path / "flood.geojson"
    features = [{"id": i} for i in range(5)]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"features": features}

    with patch("fetchers.requests.get", return_value=mock_resp) as mock_get:
        result = fetch_flood_features("https://example.com/service", "bbox", cache)

    assert len(result["features"]) == 5
    mock_get.assert_called_once()


def test_fetch_flood_features_paginates(tmp_path):
    cache = tmp_path / "flood.geojson"
    page1 = [{"id": i} for i in range(1000)]
    page2 = [{"id": i} for i in range(500)]
    mock_resp = MagicMock()
    mock_resp.json.side_effect = [
        {"features": page1},
        {"features": page2},
    ]

    with patch("fetchers.requests.get", return_value=mock_resp) as mock_get:
        with patch("fetchers.time.sleep"):
            result = fetch_flood_features("https://example.com/service", "bbox", cache)

    assert len(result["features"]) == 1500
    assert mock_get.call_count == 2


def test_fetch_flood_features_uses_cache(tmp_path):
    cache = tmp_path / "flood.geojson"
    cached_data = {"type": "FeatureCollection", "features": [{"cached": True}]}
    cache.write_text(json.dumps(cached_data))

    with patch("fetchers.requests.get") as mock_get:
        result = fetch_flood_features("https://example.com/service", "bbox", cache)

    mock_get.assert_not_called()
    assert result == cached_data


# ---------------------------------------------------------------------------
# _extract_og_image
# ---------------------------------------------------------------------------

def test_extract_og_image_property_first():
    html = '<meta property="og:image" content="https://example.com/img.jpg">'
    assert _extract_og_image(html) == "https://example.com/img.jpg"


def test_extract_og_image_content_first():
    html = '<meta content="https://example.com/img.jpg" property="og:image">'
    assert _extract_og_image(html) == "https://example.com/img.jpg"


def test_extract_og_image_unescapes_entities():
    html = '<meta property="og:image" content="https://example.com/img.jpg?w=500&amp;h=300">'
    assert _extract_og_image(html) == "https://example.com/img.jpg?w=500&h=300"


def test_extract_og_image_not_found():
    assert _extract_og_image("<html><body>no og:image here</body></html>") == ""


# ---------------------------------------------------------------------------
# fetch_listing_thumbnails
# ---------------------------------------------------------------------------

def test_fetch_listing_thumbnails_uses_cache(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    cached = {"111": "https://example.com/cached.jpg", "222": ""}
    (tmp_path / "thumbnails.json").write_text(json.dumps(cached))

    df = pd.DataFrame([
        {"LISTING_ID": 111, "URL": "https://example.com/1"},
        {"LISTING_ID": 222, "URL": float("nan")},
    ])

    with patch("fetchers.requests.get") as mock_get:
        result = fetch_listing_thumbnails(df, cfg)

    mock_get.assert_not_called()
    assert result == cached


def test_fetch_listing_thumbnails_fetches_missing(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    df = pd.DataFrame([{"LISTING_ID": 999, "URL": "https://example.com/listing"}])

    mock_resp = MagicMock()
    mock_resp.text = '<meta property="og:image" content="https://example.com/img.jpg">'

    with patch("fetchers.requests.get", return_value=mock_resp), \
         patch("fetchers.time.sleep"):
        result = fetch_listing_thumbnails(df, cfg)

    assert result["999"] == "https://example.com/img.jpg"
    assert (tmp_path / "thumbnails.json").exists()


def test_fetch_listing_thumbnails_handles_request_error(tmp_path):
    cfg = AppConfig(data_dir=tmp_path)
    df = pd.DataFrame([{"LISTING_ID": 999, "URL": "https://example.com/listing"}])

    with patch("fetchers.requests.get", side_effect=Exception("network error")), \
         patch("fetchers.time.sleep"):
        result = fetch_listing_thumbnails(df, cfg)

    assert result["999"] == ""
