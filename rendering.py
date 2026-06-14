import json
from pathlib import Path

import folium
import pandas as pd
from shapely.geometry import Point, shape

from config import AppConfig

# ---------------------------------------------------------------------------
# Client-side JS and controls — injected via HTML post-processing to avoid
# Jinja2 brace conflicts in Folium's template engine.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_price(val) -> str:
    try:
        if pd.isna(val):
            return "POA"
    except (TypeError, ValueError):
        pass
    return f"${val:,.0f}"


def format_area(val, unit="m²") -> str:
    if val == "" or val is None:
        return "—"
    try:
        if pd.isna(val):
            return "—"
    except (TypeError, ValueError):
        pass
    try:
        return f"{float(val):,.0f} {unit}"
    except (ValueError, TypeError):
        return "—"


# ---------------------------------------------------------------------------
# Marker and popup builders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Map assembly
# ---------------------------------------------------------------------------

def _build_legend(config: AppConfig) -> str:
    iz = config.listing_colors["in_zone"]
    oz = config.listing_colors["out_zone"]
    fp = config.flood_layers["flood_plains"]
    fpr = config.flood_layers["flood_prone"]
    school_zone_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        f'<span style="width:14px;height:3px;display:inline-block;border-top:2px dashed {info["zone_stroke"]}"></span>'
        f'{info["short"]} Zone</div>'
        for info in config.highlight_schools.values()
    )
    return f"""
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


def post_process_html(output_path: Path, prefs: dict) -> None:
    """Inject preferences, controls, and interaction JS into saved map HTML."""
    prefs_script = f"<script>var FMAH_PREFS={json.dumps(prefs)};</script>"
    html = output_path.read_text()
    html = html.replace("</body>", prefs_script + CONTROLS_HTML + INTERACTION_JS + "</body>")
    output_path.write_text(html)


def build_map(
    df: pd.DataFrame,
    flood_data: dict,
    school_zones: dict,
    schools: list,
    config: AppConfig,
    prefs: dict,
) -> None:
    """Assemble the full Folium map, save it, and post-process the HTML."""
    # The zone used for in/out colouring is always the first highlight school (MAGS = 69)
    zone_school_id = next(iter(config.highlight_schools))
    mags_zone = school_zones[zone_school_id]
    mags_polygons = [shape(f["geometry"]) for f in mags_zone["features"] if f.get("geometry")]

    def in_zone(lat: float, lng: float) -> bool:
        pt = Point(lng, lat)
        return any(poly.contains(pt) for poly in mags_polygons)

    center = [df["LATITUDE"].mean(), df["LONGITUDE"].mean()]
    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    # Flood zone layers
    for key, layer in config.flood_layers.items():
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
                fields=["Hazard"], aliases=["Type:"], localize=True,
            ) if key == "flood_plains" else None,
        ).add_to(m)

    # Highlighted school zones
    for school_id, info in config.highlight_schools.items():
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

    # School markers
    highlight_by_name = {i["name"]: i for i in config.highlight_schools.values()}
    schools_group = folium.FeatureGroup(name="Schools", show=True)
    for s in schools:
        name = s.get("Org_Name", "")
        lat, lng = s.get("Latitude"), s.get("Longitude")
        if not lat or not lng:
            continue
        hl_info = highlight_by_name.get(name)
        if hl_info:
            icon_html = (
                f'<div style="font-size:20px;line-height:1;'
                f'filter:drop-shadow(0 0 4px {hl_info["marker_bg"]})">📚</div>'
            )
            icon = folium.DivIcon(html=icon_html, icon_size=(24, 24), icon_anchor=(12, 12))
        else:
            icon_html = (
                f'<div style="font-size:14px;line-height:1;'
                f'filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))" title="{name}">📚</div>'
            )
            icon = folium.DivIcon(html=icon_html, icon_size=(20, 20), icon_anchor=(10, 10))

        decile = s.get("Decile") or "—"
        roll = s.get("Total") or "—"
        folium.Marker(
            location=[lat, lng],
            icon=icon,
            tooltip=f"{name} · {s.get('Definition') or s.get('Org_Type', '')} · Decile {decile}",
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

        colors = config.listing_colors["in_zone"] if in_zone(row["LATITUDE"], row["LONGITUDE"]) else config.listing_colors["out_zone"]
        folium.Marker(
            location=[row["LATITUDE"], row["LONGITUDE"]],
            icon=make_icon(listing_id, colors["fill"], colors["stroke"]),
            tooltip=f"{address}, {suburb} — {price}",
            popup=folium.Popup(make_popup(row, listing_id), max_width=280),
        ).add_to(m)

    m.get_root().html.add_child(folium.Element(_build_legend(config)))
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(str(config.output_path))
    post_process_html(config.output_path, prefs)
