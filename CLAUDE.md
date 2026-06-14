# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run server.py              # generate map and start server at localhost:5000
uv run pytest                 # run full test suite with coverage
uv run pytest tests/test_X.py # run a single test file
uv run pytest -k test_name    # run a single test by name
uv add <package>              # add a runtime dependency
uv add --dev <package>        # add a dev dependency
```

`map.html` is gitignored (generated output). `data/preferences.json` is gitignored (personal).

## Architecture

The project is split into four source modules:

| Module | Responsibility |
|---|---|
| `config.py` | Single source of truth — `AppConfig` dataclass with all constants (colours, URLs, school IDs, bbox, port). Change a value here and it propagates everywhere. |
| `fetchers.py` | All ArcGIS data fetching. `cached_fetch()` is the single DRY cache-check-or-call pattern used by all three fetch functions. |
| `rendering.py` | Map assembly — `build_map()`, `post_process_html()`, `make_popup()`, `make_icon()`, `format_price()`, `format_area()`. Also holds `INTERACTION_JS` and `CONTROLS_HTML` string templates. |
| `map.py` | Thin ~35-line orchestrator: loads config → reads CSV → calls fetchers → calls `build_map()`. |
| `server.py` | Flask app. Serves `map.html`, handles `GET/POST /api/prefs` to persist preferences to `data/preferences.json`. |

## Key config values (all in `config.py`)

| Field | Purpose |
|---|---|
| `AppConfig.bbox` | Spatial filter for ArcGIS queries (xmin,ymin,xmax,ymax WGS84) |
| `AppConfig.highlight_schools` | Dict of `school_id → {name, short, zone_fill, zone_stroke, marker_bg}` |
| `AppConfig.listing_colors` | `in_zone` and `out_zone` fill/stroke colours for listing markers |
| `AppConfig.flood_layers` | Dict of flood layer configs — URL, name, colours, opacity |
| `AppConfig.port` | Flask server port (default 5000) |

## Test structure

```
tests/
  conftest.py        — shared fixtures (sample_config, sample_df, sample_geojson, etc.)
  test_config.py     — AppConfig defaults and derived properties
  test_fetchers.py   — cached_fetch, fetch_school_zone, fetch_schools_in_area, fetch_flood_features
  test_rendering.py  — format helpers, make_popup, make_icon, build_map, post_process_html
  test_map.py        — _norm_suburb, main() orchestration
  test_server.py     — Flask endpoints via test client
```

HTTP calls in tests are mocked with `unittest.mock.patch`. No real ArcGIS requests are made during testing.

## Data sources

- **Flood Plains / Flood Prone Areas**: Auckland Council ArcGIS (`services1.arcgis.com/n4yPwebTjJCmXB6W`)
- **School zones**: MOE NZ School Zone Boundaries (`services.arcgis.com/XTtANUDT8Va4DLwI`)
- **Schools directory**: MOE Schools Directory (`services.arcgis.com/XTtANUDT8Va4DLwI`)

All fetched data is cached in `data/` and re-used on subsequent runs.
