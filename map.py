import json
import time
from pathlib import Path

import folium
import pandas as pd
import requests
from shapely.geometry import Point, shape

DATA_DIR = Path("data")
PREFS_FILE = DATA_DIR / "preferences.json"

BBOX = "174.65,-36.95,174.82,-36.80"  # xmin,ymin,xmax,ymax

SCHOOL_ZONES_URL = "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services/NZ_School_Zone_boundaries/FeatureServer/0"
SCHOOLS_DIR_URL = "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services/Schools_Directory_New_Zealand/FeatureServer/0"

# Schools with highlighted zones and markers
HIGHLIGHT_SCHOOLS = {
    69: {
        "name": "Mt Albert Grammar School",
        "short": "MAGS",
        "zone_fill": "#A5D6A7",
        "zone_stroke": "#66BB6A",
        "marker_bg": "#43A047",
    },
    1282: {
        "name": "Gladstone School (Auckland)",
        "short": "Gladstone",
        "zone_fill": "#CE93D8",
        "zone_stroke": "#AB47BC",
        "marker_bg": "#8E24AA",
    },
}

LISTING_COLORS = {
    "in_zone":  {"fill": "#2ECC71", "stroke": "#27AE60"},
    "out_zone": {"fill": "#FFAB76", "stroke": "#FB8C00"},
}

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

# Raw JS injected by post-processing (not via folium.Element, to avoid Jinja2 brace conflicts).
# FMAH_PREFS is embedded separately as a <script>var FMAH_PREFS=...;</script> block.
# Preferences are POSTed to /api/prefs on each change; server.py writes them to data/preferences.json.
INTERACTION_JS = """
<script>
(function(){
  var prefs = Object.assign({}, window.FMAH_PREFS || {});
  var hist = [];

  function persist() {
    fetch('/api/prefs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(prefs)
    }).catch(function(){});
  }

  function applyMark(id, state) {
    var el = document.getElementById('mk' + id);
    if (!el) return false;
    var em = el.querySelector('.mke');
    var base = el.querySelector('.mkb');
    if (state === 'interested') {
      em.textContent = '❤️'; em.style.display = 'block';
      base.style.display = 'none';
    } else if (state === 'uninterested') {
      em.textContent = '✕'; em.style.display = 'block';
      base.style.display = 'none';
    } else {
      em.style.display = 'none';
      base.style.display = 'block';
    }
    return true;
  }

  window.fmahMark = function(id, state) {
    var prev = prefs[id] || null, next = prev === state ? null : state;
    hist.push({id: id, prev: prev});
    if (next) prefs[id] = next; else delete prefs[id];
    persist(); applyMark(id, next); refresh();
  };

  window.fmahUndo = function() {
    if (!hist.length) return;
    var last = hist.pop();
    if (last.prev) prefs[last.id] = last.prev; else delete prefs[last.id];
    persist(); applyMark(last.id, last.prev || null); refresh();
  };

  window.fmahClear = function() {
    if (!confirm('Clear all saved preferences?')) return;
    prefs = {}; hist = [];
    persist();
    document.querySelectorAll('.mke').forEach(function(e) { e.style.display = 'none'; });
    document.querySelectorAll('.mkb').forEach(function(e) { e.style.display = 'block'; });
    refresh();
  };

  function refresh() {
    var u = document.getElementById('fmah-undo');
    if (u) u.disabled = !hist.length;
    var n = Object.keys(prefs).length;
    var c = document.getElementById('fmah-count');
    if (c) c.textContent = n ? '(' + n + ' saved)' : '';
  }

  // Fetch current preferences from server on every load so they're always fresh.
  // Falls back to the embedded FMAH_PREFS constant if the server isn't available.
  window.addEventListener('load', function() {
    function applyAll() {
      var ids = Object.keys(prefs), attempts = 0;
      function tryApply() {
        var missing = ids.filter(function(id) { return !applyMark(id, prefs[id]); });
        refresh();
        if (missing.length && ++attempts < 20) setTimeout(tryApply, 150);
      }
      setTimeout(tryApply, 100);
    }
    fetch('/api/prefs')
      .then(function(r) { return r.json(); })
      .then(function(saved) { prefs = saved; applyAll(); })
      .catch(function() { applyAll(); });
  });
})();
</script>
"""

CONTROLS_HTML = """
<div style="
    position:fixed;bottom:30px;left:10px;z-index:1000;
    background:white;padding:10px 14px;border-radius:8px;
    box-shadow:0 2px 8px rgba(0,0,0,.2);font-family:sans-serif;font-size:13px">
  <div style="font-weight:bold;margin-bottom:8px">
    Preferences
    <span id="fmah-count" style="font-weight:normal;color:#888;margin-left:4px"></span>
  </div>
  <div style="display:flex;gap:8px">
    <button id="fmah-undo" onclick="fmahUndo()" disabled style="
        padding:5px 10px;border:1px solid #ddd;border-radius:4px;
        background:white;cursor:pointer;font-size:13px">&#8617; Undo</button>
    <button onclick="fmahClear()" style="
        padding:5px 10px;border:1px solid #ddd;border-radius:4px;
        background:white;cursor:pointer;font-size:13px;color:#c62828">Clear all</button>
  </div>
</div>
"""


def fetch_school_zone(school_id: int, cache_path: Path) -> dict:
    if cache_path.exists():
        print(f"  Using cached {cache_path.name}")
        return json.loads(cache_path.read_text())

    params = {"where": f"School_ID = {school_id}", "outFields": "School_name,School_ID", "outSR": "4326", "f": "geojson"}
    resp = requests.get(f"{SCHOOL_ZONES_URL}/query", params=params, timeout=30)
    resp.raise_for_status()
    geojson = resp.json()
    cache_path.write_text(json.dumps(geojson))
    return geojson


def fetch_schools_in_area(bbox: str, cache_path: Path) -> list[dict]:
    if cache_path.exists():
        print(f"  Using cached {cache_path.name}")
        return json.loads(cache_path.read_text())

    params = {
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": "Status='Open'",
        "outFields": "School_Id,Org_Name,Org_Type,Definition,Decile,Total,Latitude,Longitude,Add1_Suburb",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(f"{SCHOOLS_DIR_URL}/query", params=params, timeout=30)
    resp.raise_for_status()
    schools = [f["attributes"] for f in resp.json().get("features", []) if f["attributes"].get("Latitude")]
    cache_path.write_text(json.dumps(schools))
    return schools


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


def make_popup(row: pd.Series, listing_id: str) -> str:
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

    link_html = (
        f'<a href="{url}" target="_blank" style="'
        f'display:block;margin-top:10px;padding:6px 10px;text-align:center;'
        f'background:#3949ab;color:white;border-radius:4px;text-decoration:none;font-weight:bold">'
        f'View listing &rarr;</a>'
    ) if url else ""

    btn_style = (
        "flex:1;padding:7px 4px;border:1px solid #ddd;border-radius:4px;"
        "background:#f5f5f5;cursor:pointer;font-size:15px"
    )

    return f"""
    <div style="font-family:sans-serif;font-size:13px;min-width:220px">
      <b>{title}</b>
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
      <div style="display:flex;gap:6px;margin-top:10px">
        <button onclick="fmahMark('{listing_id}','interested')" style="{btn_style}" title="Interested">❤️</button>
        <button onclick="fmahMark('{listing_id}','uninterested')" style="{btn_style}" title="Not interested">✕</button>
      </div>
      {link_html}
    </div>
    """


def make_icon(listing_id: str, fill_color: str, stroke_color: str) -> folium.DivIcon:
    html = (
        f'<div id="mk{listing_id}" style="position:relative;width:20px;height:20px">'
        f'<div class="mkb" style="width:20px;height:20px;border-radius:50%;'
        f'background:{fill_color};border:2px solid {stroke_color};box-sizing:border-box"></div>'
        f'<span class="mke" style="display:none;position:absolute;inset:0;'
        f'font-size:16px;line-height:20px;text-align:center;pointer-events:none"></span>'
        f'</div>'
    )
    return folium.DivIcon(html=html, icon_size=(20, 20), icon_anchor=(10, 10))


def main(initial_prefs: dict = None):
    if initial_prefs is None:
        initial_prefs = json.loads(PREFS_FILE.read_text()) if PREFS_FILE.exists() else {}

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

    # Fetch highlighted school zones
    school_zones = {}
    for school_id, info in HIGHLIGHT_SCHOOLS.items():
        print(f"Fetching {info['short']} zone...")
        zone = fetch_school_zone(school_id, DATA_DIR / f"zone_{school_id}.geojson")
        school_zones[school_id] = zone
        print(f"  Total: {len(zone['features'])} features")

    # Fetch schools in area, filtered to suburbs present in the listings
    print("Fetching schools in area...")
    schools_all = fetch_schools_in_area(BBOX, DATA_DIR / "schools.json")

    def norm(s: str) -> str:
        return s.lower().replace("mount ", "mt ").strip()

    listing_suburbs = {
        norm(row["SUBURB"].split(",")[-1].strip())
        for _, row in df.iterrows()
        if row.get("SUBURB")
    }
    schools = [
        s for s in schools_all
        if norm(s.get("Add1_Suburb") or "") in listing_suburbs
        or s.get("School_Id") in HIGHLIGHT_SCHOOLS
    ]
    print(f"  Showing {len(schools)} of {len(schools_all)} schools (in listing suburbs)")

    # Keep mags_zone reference for point-in-polygon check (backwards compat)
    mags_zone = school_zones[69]

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
                fields=["Hazard"],
                aliases=["Type:"],
                localize=True,
            ) if key == "flood_plains" else None,
        ).add_to(m)

    # Highlighted school zones
    for school_id, info in HIGHLIGHT_SCHOOLS.items():
        folium.GeoJson(
            school_zones[school_id],
            name=f"{info['short']} Enrolment Zone",
            style_function=lambda _, i=info: {
                "fillColor": i["zone_fill"],
                "color": i["zone_stroke"],
                "weight": 2,
                "fillOpacity": 0.12,
                "dashArray": "6 4",
            },
            tooltip=f"{info['name']} Enrolment Zone",
        ).add_to(m)

    # Build MAGS zone polygon for point-in-polygon checks
    mags_polygons = [shape(f["geometry"]) for f in mags_zone["features"] if f.get("geometry")]

    def in_mags_zone(lat, lng) -> bool:
        pt = Point(lng, lat)
        return any(poly.contains(pt) for poly in mags_polygons)

    # School markers
    highlight_ids = {info["name"]: info for info in HIGHLIGHT_SCHOOLS.values()}
    schools_group = folium.FeatureGroup(name="Schools", show=True)
    for s in schools:
        name = s.get("Org_Name", "")
        lat, lng = s.get("Latitude"), s.get("Longitude")
        if not lat or not lng:
            continue
        info = highlight_ids.get(name)
        if info:
            # Highlighted school: larger 📚 with coloured glow
            icon_html = (
                f'<div style="font-size:20px;line-height:1;'
                f'filter:drop-shadow(0 0 4px {info["marker_bg"]})">'
                f'📚</div>'
            )
            icon = folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12))
        else:
            # Regular school: small 🏫 emoji
            school_type = s.get("Definition") or s.get("Org_Type", "")
            icon_html = (
                f'<div style="font-size:14px;line-height:1;'
                f'filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))" '
                f'title="{name}">📚</div>'
            )
            icon = folium.DivIcon(html=icon_html, icon_size=(20, 20), icon_anchor=(10, 10))

        decile = s.get("Decile") or "—"
        roll = s.get("Total") or "—"
        tooltip_text = f"{name} · {s.get('Definition') or s.get('Org_Type', '')} · Decile {decile}"

        folium.Marker(
            location=[lat, lng],
            icon=icon,
            tooltip=tooltip_text,
            popup=folium.Popup(
                f'<div style="font-family:sans-serif;font-size:13px">'
                f'<b>{name}</b><br>'
                f'<span style="color:#888">{s.get("Definition") or s.get("Org_Type", "")}</span><br>'
                f'Decile {decile} &nbsp;·&nbsp; Roll {roll}'
                f'</div>',
                max_width=220,
            ),
        ).add_to(schools_group)
    schools_group.add_to(m)

    # House markers
    for i, (_, row) in enumerate(df.iterrows()):
        listing_id = str(int(row["LISTING_ID"])) if pd.notna(row.get("LISTING_ID")) else str(i)
        price = format_price(row.get("EXPECTED_SALE_PRICE"))
        address = f"{row.get('STREET_NUMBER', '')} {row.get('STREET', '')}".strip()
        suburb_raw = row.get("SUBURB", "") or ""
        suburb = suburb_raw.split(",")[-1].strip() if suburb_raw else ""

        inside = in_mags_zone(row["LATITUDE"], row["LONGITUDE"])
        colors = LISTING_COLORS["in_zone"] if inside else LISTING_COLORS["out_zone"]
        fill_color, stroke_color = colors["fill"], colors["stroke"]

        folium.Marker(
            location=[row["LATITUDE"], row["LONGITUDE"]],
            icon=make_icon(listing_id, fill_color, stroke_color),
            tooltip=f"{address}, {suburb} — {price}",
            popup=folium.Popup(make_popup(row, listing_id), max_width=280),
        ).add_to(m)

    # Legend — colours pulled from constants so they stay in sync automatically
    iz, oz = LISTING_COLORS["in_zone"], LISTING_COLORS["out_zone"]
    fp, fpr = FLOOD_LAYERS["flood_plains"], FLOOD_LAYERS["flood_prone"]
    school_zone_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        f'<span style="width:14px;height:3px;display:inline-block;border-top:2px dashed {info["zone_stroke"]}"></span>'
        f'{info["short"]} Zone</div>'
        for info in HIGHLIGHT_SCHOOLS.values()
    )
    legend_html = f"""
    <div style="
        position:fixed;bottom:30px;right:10px;z-index:1000;
        background:white;padding:12px 16px;border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,.2);font-family:sans-serif;font-size:13px">
      <b style="display:block;margin-bottom:8px">Legend</b>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;border-radius:50%;background:{iz['fill']};border:2px solid {iz['stroke']};display:inline-block"></span>
        Listing (in MAGS zone)
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;border-radius:50%;background:{oz['fill']};border:2px solid {oz['stroke']};display:inline-block"></span>
        Listing (outside zone)
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;background:{fp['fill']};display:inline-block;border:1px solid {fp['stroke']}"></span>
        Flood Plain (1-in-100yr)
      </div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:14px;height:14px;background:{fpr['fill']};display:inline-block;border:1px solid {fpr['stroke']}"></span>
        Flood Prone Area
      </div>
      {school_zone_rows}
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:13px">📚</span>
        School
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)

    out = Path("map.html")
    m.save(str(out))

    # Post-process: inject controls, prefs init, and interaction JS directly into the HTML
    # (bypasses Jinja2 so JS object literals don't need escaping)
    prefs_script = f"<script>var FMAH_PREFS={json.dumps(initial_prefs)};</script>"
    html = out.read_text()
    html = html.replace("</body>", prefs_script + CONTROLS_HTML + INTERACTION_JS + "</body>")
    out.write_text(html)

    print(f"\nSaved → {out.resolve()}")


if __name__ == "__main__":
    main()
