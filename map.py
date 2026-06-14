import json
import time
from pathlib import Path

import folium
import pandas as pd
import requests

DATA_DIR = Path("data")

BBOX = "174.65,-36.95,174.82,-36.80"  # xmin,ymin,xmax,ymax

MAGS_ZONE_URL = "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services/NZ_School_Zone_boundaries/FeatureServer/0"
MAGS_SCHOOL_ID = 69

FLOOD_LAYERS = {
    "flood_plains": {
        "url": "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Flood_Plains/FeatureServer/0",
        "name": "Flood Plains (1-in-100yr)",
        "fill": "#90CAF9",
        "stroke": "#64B5F6",
        "opacity": 0.35,
    },
    "flood_prone": {
        "url": "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Flood_Prone_Areas/FeatureServer/0",
        "name": "Flood Prone Areas",
        "fill": "#FFCC80",
        "stroke": "#FFA726",
        "opacity": 0.3,
    },
}


def fetch_school_zone(service_url: str, school_id: int, cache_path: Path) -> dict:
    if cache_path.exists():
        print(f"  Using cached {cache_path.name}")
        return json.loads(cache_path.read_text())

    params = {
        "where": f"School_ID = {school_id}",
        "outFields": "School_name,School_ID",
        "outSR": "4326",
        "f": "geojson",
    }
    resp = requests.get(f"{service_url}/query", params=params, timeout=30)
    resp.raise_for_status()
    geojson = resp.json()
    cache_path.write_text(json.dumps(geojson))
    return geojson


def fetch_features(service_url: str, bbox: str, cache_path: Path) -> dict:
    if cache_path.exists():
        print(f"  Using cached {cache_path.name}")
        return json.loads(cache_path.read_text())

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
        data = resp.json()
        features = data.get("features", [])
        all_features.extend(features)
        print(f"  Fetched {len(all_features)} features...")
        if len(features) < batch:
            break
        offset += batch
        time.sleep(0.2)

    geojson = {"type": "FeatureCollection", "features": all_features}
    cache_path.write_text(json.dumps(geojson))
    return geojson


def format_price(val) -> str:
    if pd.isna(val):
        return "POA"
    return f"${val:,.0f}"


def format_area(val, unit="m²") -> str:
    if pd.isna(val) or val == "":
        return "—"
    try:
        return f"{float(val):,.0f} {unit}"
    except (ValueError, TypeError):
        return "—"


def make_popup(row: pd.Series) -> str:
    title = row.get("LISTING_TITLE", "") or ""
    url = row.get("URL", "") or ""
    address = f"{row.get('STREET_NUMBER', '')} {row.get('STREET', '')}".strip()
    suburb_raw = row.get("SUBURB", "") or ""
    suburb = suburb_raw.split(",")[-1].strip() if suburb_raw else ""

    price = format_price(row.get("EXPECTED_SALE_PRICE"))
    land = format_area(row.get("LAND_AREA_IN_M2"))
    floor = format_area(row.get("FLOOR_AREA"))
    beds = int(row["BEDROOM_COUNT"]) if pd.notna(row.get("BEDROOM_COUNT")) else "—"
    baths = int(row["BATHROOM_COUNT"]) if pd.notna(row.get("BATHROOM_COUNT")) else "—"
    garage = int(row["GARAGE_PARKING_COUNT"]) if pd.notna(row.get("GARAGE_PARKING_COUNT")) else "—"
    sale_type = row.get("SALE_TYPE", "") or ""
    rv = format_price(row.get("RATEABLE_VALUE")) if pd.notna(row.get("RATEABLE_VALUE")) else "—"

    title_html = f'<a href="{url}" target="_blank"><b>{title}</b></a>' if url else f"<b>{title}</b>"

    return f"""
    <div style="font-family:sans-serif;font-size:13px;min-width:220px">
      {title_html}
      <div style="color:#555;margin:4px 0">{address}, {suburb}</div>
      <hr style="margin:6px 0;border-color:#eee">
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="color:#888">Price</td><td><b style="color:#1a237e">{price}</b></td></tr>
        <tr><td style="color:#888">RV</td><td>{rv}</td></tr>
        <tr><td style="color:#888">Sale type</td><td>{sale_type}</td></tr>
        <tr><td style="color:#888">Beds / Baths</td><td>{beds} bd / {baths} ba</td></tr>
        <tr><td style="color:#888">Garage</td><td>{garage}</td></tr>
        <tr><td style="color:#888">Land</td><td>{land}</td></tr>
        <tr><td style="color:#888">Floor</td><td>{floor}</td></tr>
      </table>
    </div>
    """


def main():
    # Load housing data
    df = pd.read_csv("data/Housing_2026-06-14-1602.csv")
    df = df.dropna(subset=["LATITUDE", "LONGITUDE"])
    print(f"Loaded {len(df)} houses")

    # Fetch flood zone layers
    flood_data = {}
    for key, layer in FLOOD_LAYERS.items():
        print(f"Fetching {layer['name']}...")
        geojson = fetch_features(layer["url"], BBOX, DATA_DIR / f"{key}.geojson")
        flood_data[key] = geojson
        print(f"  Total: {len(geojson['features'])} features")

    # Fetch MAGS enrolment zone
    print("Fetching Mt Albert Grammar School zone...")
    mags_zone = fetch_school_zone(MAGS_ZONE_URL, MAGS_SCHOOL_ID, DATA_DIR / "mags_zone.geojson")
    print(f"  Total: {len(mags_zone['features'])} features")

    # Build map
    center = [df["LATITUDE"].mean(), df["LONGITUDE"].mean()]
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    # Flood zone layers (add beneath house markers)
    for key, layer in FLOOD_LAYERS.items():
        folium.GeoJson(
            flood_data[key],
            name=layer["name"],
            style_function=lambda _, l=layer: {
                "fillColor": l["fill"],
                "color": l["stroke"],
                "weight": 1,
                "fillOpacity": l["opacity"],
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["Hazard"] if key == "flood_plains" else [],
                aliases=["Type:"] if key == "flood_plains" else [],
                localize=True,
            ) if key == "flood_plains" else None,
        ).add_to(m)

    # MAGS enrolment zone (prominent border, no fill so flood layers show through)
    folium.GeoJson(
        mags_zone,
        name="Mt Albert Grammar Zone",
        style_function=lambda _: {
            "fillColor": "#A5D6A7",
            "color": "#81C784",
            "weight": 2,
            "fillOpacity": 0.12,
            "dashArray": "6 4",
        },
        tooltip="Mt Albert Grammar School Enrolment Zone",
    ).add_to(m)

    # House markers
    for _, row in df.iterrows():
        price = format_price(row.get("EXPECTED_SALE_PRICE"))
        address = f"{row.get('STREET_NUMBER', '')} {row.get('STREET', '')}".strip()
        suburb_raw = row.get("SUBURB", "") or ""
        suburb = suburb_raw.split(",")[-1].strip() if suburb_raw else ""

        folium.CircleMarker(
            location=[row["LATITUDE"], row["LONGITUDE"]],
            radius=8,
            color="#1a237e",
            fill=True,
            fill_color="#3949ab",
            fill_opacity=0.9,
            weight=2,
            tooltip=f"{address}, {suburb} — {price}",
            popup=folium.Popup(make_popup(row), max_width=280),
        ).add_to(m)

    # Legend
    legend_html = """
    <div style="
        position:fixed;bottom:30px;right:10px;z-index:1000;
        background:white;padding:12px 16px;border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,.2);font-family:sans-serif;font-size:13px">
      <b style="display:block;margin-bottom:8px">Legend</b>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;border-radius:50%;background:#3949ab;display:inline-block"></span>
        Listing
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;background:#90CAF9;display:inline-block;border:1px solid #64B5F6"></span>
        Flood Plain (1-in-100yr)
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;background:#FFCC80;display:inline-block;border:1px solid #FFA726"></span>
        Flood Prone Area
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="width:14px;height:3px;background:#81C784;display:inline-block;border-top:2px dashed #81C784"></span>
        MAGS Enrolment Zone
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    out = Path("map.html")
    m.save(str(out))
    print(f"\nSaved → {out.resolve()}")


if __name__ == "__main__":
    main()
