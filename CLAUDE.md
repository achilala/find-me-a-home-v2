# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run map.py        # generate map.html (the output)
uv add <package>     # add a dependency
```

`map.html` is gitignored (generated output). Re-run `map.py` to rebuild it.

## Architecture

Single-script project. `map.py` is the entire application:

1. **Flood zone data** — fetched from Auckland Council's ArcGIS FeatureServer, spatially filtered to the bounding box of the listings, and cached to `data/flood_plains.geojson` and `data/flood_prone.geojson`. Delete these files to force a re-fetch.

2. **School zone data** — fetched by `School_ID` from the Ministry of Education's NZ School Zone Boundaries FeatureServer, cached to `data/mags_zone.geojson`.

3. **Housing data** — read from `data/Housing_2026-06-14-1602.csv` (static input, committed to the repo). Key columns: `LATITUDE`, `LONGITUDE`, `URL`, `EXPECTED_SALE_PRICE`, `RATEABLE_VALUE`, `BEDROOM_COUNT`, `BATHROOM_COUNT`, `GARAGE_PARKING_COUNT`, `LAND_AREA_IN_M2`, `FLOOR_AREA`, `SALE_TYPE`.

4. **Map rendering** — Folium (Leaflet.js wrapper). Layer order matters: flood zones are added before markers so they sit beneath. `shapely` is used for point-in-polygon to decide marker colour (blue = inside MAGS zone, grey = outside).

## Key constants

| Constant | Purpose |
|---|---|
| `BBOX` | Spatial filter for flood zone queries (xmin,ymin,xmax,ymax in WGS84) |
| `MAGS_SCHOOL_ID` | Ministry of Education school ID for Mt Albert Grammar (69) |
| `FLOOD_LAYERS` | Dict of flood layer configs — URL, display name, colours, opacity |

## Data sources

- **Flood Plains / Flood Prone Areas**: `https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/`
- **School zones**: `https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services/NZ_School_Zone_boundaries/FeatureServer/0`
- Both are public Auckland Council / MOE ArcGIS services; no API key required.
