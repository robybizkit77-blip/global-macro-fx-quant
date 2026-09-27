GLOBAL MACRO FX QUANT

GitHub Pages delivery for the validated dashboard. The visible UI is kept in
`app.html`; the small `index.html` loader retrieves the current JSON payload at
runtime. There is no Base64 chunk assembly in this architecture.

## Daily refresh

After the research engine has produced and QA-approved the new standalone
dashboard, run:

```powershell
python tools/build_runtime_payload.py <validated-dashboard.html> --out . --refresh-only
```

Then publish only `data/`. This updates `data/sections/*.json` and
`data/manifest.json`; `index.html` and `app.html` are intentionally unchanged.
The generated `qa/architecture-report.json` must be `PASS`, including exactly
28 pairs, before publishing.

## One-time frontend migration / rollback

Use the same command without `--refresh-only` only for a deliberately approved
UI release. A normal Git revert of the migration commit restores the previous
GitHub Pages loader and its atomic Base64/Gzip release, so the pre-migration
site remains an easy rollback point.
