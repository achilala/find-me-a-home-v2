from dataclasses import dataclass, field
from pathlib import Path


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

    highlight_schools: dict = field(default_factory=lambda: {
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
    })

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

    @property
    def prefs_file(self) -> Path:
        return self.data_dir / "preferences.json"
