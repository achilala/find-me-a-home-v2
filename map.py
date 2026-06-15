import json

import pandas as pd

from config import AppConfig
from fetchers import fetch_flood_features, fetch_listing_thumbnails, fetch_school_zone, fetch_schools_in_area
from rendering import build_map


def _norm_suburb(s: str) -> str:
    return s.lower().replace("mount ", "mt ").strip()


def main(initial_prefs: dict = None, config: AppConfig = None) -> None:
    if config is None:
        config = AppConfig()
    if initial_prefs is None:
        initial_prefs = json.loads(config.prefs_file.read_text()) if config.prefs_file.exists() else {}

    # Load housing data (latest Housing_*.csv)
    csv_files = sorted(config.data_dir.glob("Housing_*.csv"))
    df = pd.read_csv(csv_files[-1])
    df = df.dropna(subset=["LATITUDE", "LONGITUDE"])
    print(f"Loaded {len(df)} houses from {csv_files[-1].name}")

    # Fetch flood zone layers
    flood_data = {}
    for key, layer in config.flood_layers.items():
        print(f"Fetching {layer['name']}...")
        flood_data[key] = fetch_flood_features(
            layer["url"], config.bbox, config.data_dir / f"{key}.geojson"
        )
        print(f"  Total: {len(flood_data[key]['features'])} features")

    # Fetch highlighted school zones
    school_zones = {}
    for school_id, info in config.highlight_schools.items():
        print(f"Fetching {info['short']} zone...")
        school_zones[school_id] = fetch_school_zone(school_id, config)
        print(f"  Total: {len(school_zones[school_id]['features'])} features")

    # Fetch and filter schools to listing suburbs
    print("Fetching schools in area...")
    all_schools = fetch_schools_in_area(config)
    listing_suburbs = {
        _norm_suburb(row["SUBURB"].split(",")[-1].strip())
        for _, row in df.iterrows()
        if row.get("SUBURB")
    }
    schools = [
        s for s in all_schools
        if _norm_suburb(s.get("Add1_Suburb") or "") in listing_suburbs
        or s.get("School_Id") in config.highlight_schools
    ]
    print(f"  Showing {len(schools)} of {len(all_schools)} schools (in listing suburbs)")

    print("Fetching listing thumbnails...")
    thumbnails = fetch_listing_thumbnails(df, config)
    print(f"  {sum(1 for v in thumbnails.values() if v)} of {len(thumbnails)} have thumbnails")

    build_map(df, flood_data, school_zones, schools, config, initial_prefs, thumbnails)
    print(f"\nSaved → {config.output_path.resolve()}")


if __name__ == "__main__":
    main()
