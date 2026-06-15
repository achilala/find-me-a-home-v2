import json
from dataclasses import dataclass, field
from pathlib import Path

# Color palette cycled when adding new schools via manage_schools.py
SCHOOL_COLOR_PALETTE = [
    {"zone_fill": "#A5D6A7", "zone_stroke": "#66BB6A", "marker_bg": "#43A047"},  # green
    {"zone_fill": "#CE93D8", "zone_stroke": "#AB47BC", "marker_bg": "#8E24AA"},  # purple
    {"zone_fill": "#90CAF9", "zone_stroke": "#64B5F6", "marker_bg": "#1565C0"},  # blue
    {"zone_fill": "#FFCC80", "zone_stroke": "#FFA726", "marker_bg": "#E65100"},  # orange
    {"zone_fill": "#F48FB1", "zone_stroke": "#E91E63", "marker_bg": "#C2185B"},  # pink
    {"zone_fill": "#80CBC4", "zone_stroke": "#4DB6AC", "marker_bg": "#00695C"},  # teal
]

_DEFAULT_SCHOOLS = {
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


@dataclass
class AppConfig:
    data_dir: Path = field(default_factory=lambda: Path("data"))
    output_path: Path = field(default_factory=lambda: Path("map.html"))
    bbox: str = "174.65,-36.95,174.82,-36.80"
    port: int = 5000

    school_zones_url: str = (
        "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services"
        "/NZ_School_Zone_boundaries/FeatureServer/0"
    )
    schools_dir_url: str = (
        "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services"
        "/Schools_Directory_New_Zealand/FeatureServer/0"
    )

    # Populated from data/schools_config.json if present; falls back to _DEFAULT_SCHOOLS
    highlight_schools: dict = field(default_factory=lambda: dict(_DEFAULT_SCHOOLS))

    listing_colors: dict = field(default_factory=lambda: {
        "in_zone":  {"fill": "#2ECC71", "stroke": "#27AE60"},
        "out_zone": {"fill": "#EF9A9A", "stroke": "#E53935"},
    })

    flood_layers: dict = field(default_factory=lambda: {
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
    })

    # Geometry simplification tolerance (degrees). 0 = no simplification.
    # Use ~0.0001 for Vercel/static builds to keep HTML under 10 MB.
    simplify_tolerance: float = 0.0

    def __post_init__(self) -> None:
        # Load highlight_schools from data/schools_config.json when present,
        # so changes made via manage_schools.py take effect without editing code.
        config_path = self.data_dir / "schools_config.json"
        if config_path.exists():
            raw = json.loads(config_path.read_text())
            self.highlight_schools = {int(k): v for k, v in raw.items()}

    @property
    def prefs_file(self) -> Path:
        return self.data_dir / "preferences.json"

    @property
    def schools_config_file(self) -> Path:
        return self.data_dir / "schools_config.json"
