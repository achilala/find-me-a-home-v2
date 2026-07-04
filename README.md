# find-me-a-home-v2

## Updating listings

When you update `data/housing_data.csv`, you must regenerate the deployed map before new listings appear. The app on Vercel serves `public/index.html` as a static file — it does not pick up CSV changes automatically.

```bash
uv run python build.py  # regenerate public/index.html (simplified for deployment)
```

Then commit and push:

```bash
git add data/ public/index.html
git commit -m "Refresh data: <N> listings, <X>/<Y> thumbnails"
git push origin main
```

Vercel auto-deploys on push. Skipping `build.py` means new listings will be missing from the deployed app.

## Running locally

```bash
uv run server.py   # regenerates map.html, starts server at localhost:5000
```

The local server uses `map.html` (uncompressed, ~130MB) and supports preferences persistence via `data/preferences.json`.
