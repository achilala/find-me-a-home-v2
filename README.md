# find-me-a-home-v2

## Updating listings

When you update `data/housing_data.csv`, you must regenerate the map before the new listings appear in the app:

```bash
uv run python map.py   # regenerate map.html
```

Then commit and push:

```bash
git add data/
git commit -m "Refresh data: <N> listings, <X>/<Y> thumbnails"
git push origin main
```

The server serves `map.html` as a static file — it does not pick up CSV changes automatically. Skipping the regeneration step means new listings will be missing from the app.
