"""Vercel build script — generates a simplified, self-contained map.html into public/."""
import os
from pathlib import Path

import map as map_module
from config import AppConfig

os.makedirs("public", exist_ok=True)

cfg = AppConfig(
    output_path=Path("public/index.html"),
    simplify_tolerance=0.0001,  # reduces raw flood zone geometry from ~131 MB to a few MB
    externalize_flood=True,  # writes flood layers as public/*.json, loaded via fetch() instead of inlined
)
map_module.main(initial_prefs={}, config=cfg)
