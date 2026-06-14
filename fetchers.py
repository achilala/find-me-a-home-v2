import json
import time
from pathlib import Path
from typing import Callable, TypeVar

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
