import html
import json
import re
import time
from pathlib import Path
from typing import Callable, TypeVar

import pandas as pd
import requests

from config import AppConfig

T = TypeVar("T")


def cached_fetch(cache_path: Path, fetcher: Callable[[], T]) -> T:
    """Return cached JSON if the file exists, otherwise call fetcher, cache result, and return."""
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    result = fetcher()
    cache_path.write_text(json.dumps(result))
    return result


def fetch_school_zone(school_id: int, config: AppConfig) -> dict:
    cache_path = config.data_dir / f"zone_{school_id}.geojson"

    def _fetch() -> dict:
        params = {
            "where": f"School_ID = {school_id}",
            "outFields": "School_name,School_ID",
            "outSR": "4326",
            "f": "geojson",
        }
        resp = requests.get(f"{config.school_zones_url}/query", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    return cached_fetch(cache_path, _fetch)


def fetch_schools_in_area(config: AppConfig) -> list[dict]:
    cache_path = config.data_dir / "schools.json"

    def _fetch() -> list[dict]:
        params = {
            "geometry": config.bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": "Status='Open'",
            "outFields": "School_Id,Org_Name,Org_Type,Definition,Decile,Total,Latitude,Longitude,Add1_Suburb",
            "outSR": "4326",
            "f": "json",
        }
        resp = requests.get(f"{config.schools_dir_url}/query", params=params, timeout=30)
        resp.raise_for_status()
        return [
            f["attributes"]
            for f in resp.json().get("features", [])
            if f["attributes"].get("Latitude")
        ]

    return cached_fetch(cache_path, _fetch)


def fetch_flood_features(service_url: str, bbox: str, cache_path: Path) -> dict:
    def _fetch() -> dict:
        all_features = []
        offset = 0
        batch = 1000
        params_base = {
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": batch,
        }
        while True:
            params = {**params_base, "resultOffset": offset}
            resp = requests.get(f"{service_url}/query", params=params, timeout=30)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            all_features.extend(features)
            if len(features) < batch:
                break
            offset += batch
            time.sleep(0.2)
        return {"type": "FeatureCollection", "features": all_features}

    return cached_fetch(cache_path, _fetch)


_OG_IMAGE_RE = re.compile(
    r'property="og:image"\s+content="([^"]+)"|content="([^"]+)"\s+property="og:image"',
    re.IGNORECASE,
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; find-me-a-home-bot/1.0)"}


def _extract_og_image(page_html: str) -> str:
    m = _OG_IMAGE_RE.search(page_html)
    if m:
        return html.unescape(m.group(1) or m.group(2))
    return ""


def fetch_listing_thumbnails(df: pd.DataFrame, config: AppConfig) -> dict[str, str]:
    """Return {listing_id: thumbnail_url} for all listings, fetching missing ones."""
    cache_path = config.data_dir / "thumbnails.json"
    cache: dict[str, str] = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    updated = False
    for _, row in df.iterrows():
        listing_id = str(int(row["LISTING_ID"])) if pd.notna(row.get("LISTING_ID")) else None
        if not listing_id or listing_id in cache:
            continue

        url_raw = row.get("URL")
        url = "" if (not url_raw or pd.isna(url_raw)) else str(url_raw).strip()
        if not url:
            url = f"https://www.trademe.co.nz/a/property/residential/sale/listing/{listing_id}"

        try:
            resp = requests.get(url, timeout=8, headers=_HEADERS, allow_redirects=True)
            cache[listing_id] = _extract_og_image(resp.text)
        except Exception:
            cache[listing_id] = ""

        updated = True
        time.sleep(0.3)
        print(f"  Fetched thumbnail for {listing_id}: {'found' if cache[listing_id] else 'not found'}")

    if updated:
        cache_path.write_text(json.dumps(cache, indent=2))

    return cache
