#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
needle = "normalizedSeriesImpulse"
hits = []
for base in [ROOT / "payload", ROOT / "index.html", ROOT / "history"]:
    paths = [base] if base.is_file() else list(base.rglob("*")) if base.exists() else []
    for p in paths:
        if not p.is_file() or p.suffix.lower() not in {".txt", ".html", ".js", ".json", ""}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if needle not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if needle in line:
                lo = max(0, i - 15)
                hi = min(len(lines), i + 45)
                hits.append({
                    "path": str(p.relative_to(ROOT)),
                    "line": i + 1,
                    "snippet": "\n".join(lines[lo:hi])
                })

out = ROOT / "validation/ENGINE_SYMBOL_NORMALIZED_SERIES_IMPULSE_2026-10-03.json"
out.write_text(json.dumps({"needle": needle, "hits": hits}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"hits": len(hits), "locations": [(h['path'], h['line']) for h in hits]}, indent=2))
if not hits:
    raise SystemExit(1)
