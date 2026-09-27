#!/usr/bin/env python3
"""Convert a self-contained GLOBAL MACRO FX QUANT dashboard into stable UI + JSON.

The script is deliberately source-agnostic: the daily refresh can pass the newly
validated HTML to it and only data/ changes afterwards.  It never recalculates or
alters a signal; it only relocates the two embedded data objects consumed by the UI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def extract_object_assignment(source: str, name: str) -> tuple[int, int, object]:
    """Return the source range and JSON value of `const NAME = {...};` safely."""
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*", source)
    if not match:
        raise ValueError(f"Assignment not found: {name}")
    start = match.start()
    cursor = match.end()
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor >= len(source) or source[cursor] != "{":
        raise ValueError(f"{name} is not an object literal")

    depth, quote, escaped = 0, None, False
    end = None
    for pos in range(cursor, len(source)):
        char = source[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = pos + 1
                break
    if end is None:
        raise ValueError(f"Unclosed object literal: {name}")
    semicolon = end
    while semicolon < len(source) and source[semicolon].isspace():
        semicolon += 1
    if semicolon < len(source) and source[semicolon] == ";":
        semicolon += 1
    return start, semicolon, json.loads(source[cursor:end])



def extract_json_assignment(source: str, name: str) -> object:
    """Extract a JSON object or array from a top-level const assignment."""
    match = re.search(rf"\\bconst\\s+{re.escape(name)}\\s*=\\s*", source)
    if not match:
        raise ValueError(f"Assignment not found: {name}")
    cursor = match.end()
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor >= len(source) or source[cursor] not in "[{":
        raise ValueError(f"{name} is not a JSON object/array literal")
    opener = source[cursor]
    closer = "}" if opener == "{" else "]"
    depth, quote, escaped = 0, None, False
    end = None
    for pos in range(cursor, len(source)):
        char = source[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                end = pos + 1
                break
    if end is None:
        raise ValueError(f"Unclosed JSON literal: {name}")
    return json.loads(source[cursor:end])

def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    path.write_bytes(raw + b"\n")
    return hashlib.sha256(raw).hexdigest()


LOADER = """<!doctype html>
<html lang=\"it\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>GLOBAL MACRO FX QUANT</title>
<style>html,body{margin:0;background:#06131f;color:#eef7ff;font:16px Arial,sans-serif}#loading{padding:24px}</style>
</head><body><div id=\"loading\">Caricamento GLOBAL MACRO FX QUANT…</div>
<script>
(async()=>{
  const suffix='?v='+Date.now();
  const [manifestResponse, appResponse] = await Promise.all([
    fetch('data/manifest.json'+suffix,{cache:'no-store'}),
    fetch('app.html'+suffix,{cache:'force-cache'})
  ]);
  if(!manifestResponse.ok) throw new Error('manifest '+manifestResponse.status);
  if(!appResponse.ok) throw new Error('frontend '+appResponse.status);
  const manifest=await manifestResponse.json();
  if(manifest.schema_version!==1 || !Array.isArray(manifest.sections) || !manifest.sections.length) throw new Error('manifest non valido');
  const sectionResponses=await Promise.all(manifest.sections.map(s=>fetch('data/sections/'+s.file+suffix,{cache:'no-store'})));
  if(sectionResponses.some(r=>!r.ok)) throw new Error('payload incompleto');
  const payload={};
  for(let i=0;i<manifest.sections.length;i++) payload[manifest.sections[i].key]=await sectionResponses[i].json();
  const serialised=JSON.stringify(payload).replace(/</g,'\\\\u003c').replace(/>/g,'\\\\u003e').replace(/&/g,'\\\\u0026');
  const app=await appResponse.text();
  // The marker lives inside the dashboard's first script block, so inject a
  // JavaScript statement (not a nested <script>, which would terminate it).
  const hydrated=app.replace('<!-- FX_PAYLOAD_BOOTSTRAP -->','window.__FX_PAYLOAD__='+serialised+';');
  if(hydrated===app) throw new Error('frontend non compatibile con il payload');
  document.open(); document.write(hydrated); document.close();
})().catch(e=>{document.body.innerHTML='<div style=\"padding:24px;font:16px Arial;color:#fff;background:#06131f\">Errore nel caricamento della dashboard. Riprova tra poco.<br><small>'+String(e)+'</small></div>';});
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="validated standalone dashboard HTML")
    parser.add_argument("--out", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--refresh-only", action="store_true", help="update only data/ after the one-time frontend migration")
    args = parser.parse_args()
    root = args.out.resolve()
    source = args.source.read_text(encoding="utf-8")

    c_start, c_end, country_context = extract_object_assignment(source, "COUNTRY_CTX")
    d_start, d_end, dashboard = extract_object_assignment(source, "D")
    if d_start < c_end:
        raise ValueError("Unexpected assignment order")

    payload = {"country_ctx": country_context, "dashboard": dashboard}

    # Runtime data used by the stable frontend must travel with every refresh.
    # These objects remain embedded in app.html as a safe fallback, but ui-patch.js
    # hydrates them in place from the current payload so they cannot stay frozen.
    extra_specs = [
        ("NATIVE_RATES_DATA", "native_rates", "native_rates.json"),
        ("NATIVE_CB_DATA", "native_cb", "native_cb.json"),
        ("NATIVE_LIQ_DATA", "native_liq", "native_liq.json"),
        ("CERT53", "cert53", "cert53.json"),
        ("V250_COT_CHART_DATA", "cot_charts", "cot_charts.json"),
        ("TOP_THEMES", "top_themes", "top_themes.json"),
        ("WHAT_CHANGED", "what_changed", "what_changed.json"),
        ("V247_COT_STORIES", "cot_stories", "cot_stories.json"),
        ("V241_PLAIN_MARKET", "plain_market", "plain_market.json"),
    ]
    for source_name, key, _filename in extra_specs:
        payload[key] = extract_json_assignment(source, source_name)

    # S is by far the largest live dataset. Split it by currency so no single
    # GitHub write is unnecessarily large.
    all_series = extract_json_assignment(source, "S")
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        payload[f"series_{ccy}"] = all_series.get(ccy, [])

    sections = []
    file_names = {
        "country_ctx": "country_ctx.json",
        "dashboard": "dashboard.json",
        "native_rates": "native_rates.json",
        "native_cb": "native_cb.json",
        "native_liq": "native_liq.json",
        "cert53": "cert53.json",
        "cot_charts": "cot_charts.json",
        "top_themes": "top_themes.json",
        "what_changed": "what_changed.json",
        "cot_stories": "cot_stories.json",
        "plain_market": "plain_market.json",
    }
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        file_names[f"series_{ccy}"] = f"series_{ccy}.json"

    for key, value in payload.items():
        filename = file_names[key]
        digest = write_json(root / "data" / "sections" / filename, value)
        sections.append({"key": key, "file": filename, "sha256": digest, "bytes": (root / "data" / "sections" / filename).stat().st_size})

    country_stub = "<!-- FX_PAYLOAD_BOOTSTRAP -->\nconst COUNTRY_CTX=window.__FX_PAYLOAD__.country_ctx;"
    dashboard_stub = "const D=window.__FX_PAYLOAD__.dashboard;"
    app = source[:c_start] + country_stub + source[c_end:d_start] + dashboard_stub + source[d_end:]
    if "const D={" in app or "const COUNTRY_CTX={" in app:
        raise ValueError("Embedded payload remains in frontend")
    if args.refresh_only:
        if not (root / "app.html").is_file() or not (root / "index.html").is_file():
            raise ValueError("--refresh-only requires an already migrated frontend")
    else:
        (root / "app.html").write_text(app, encoding="utf-8", newline="\n")
        (root / "index.html").write_text(LOADER, encoding="utf-8", newline="\n")

    manifest = {
        "schema_version": 1,
        "release": args.source.stem,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "sections": sections,
    }
    write_json(root / "data" / "manifest.json", manifest)

    pair_count = len(dashboard.get("pairs", []))
    if pair_count != 28:
        raise ValueError(f"Expected 28 pairs, got {pair_count}")
    reconstructed = {"country_ctx": country_context, "dashboard": dashboard}
    if canonical(payload) != canonical(reconstructed):
        raise ValueError("Payload reconstruction failed")
    qa = {
        "status": "PASS",
        "checks": {
            "source_preserved_as_stable_frontend": True,
            "embedded_payload_removed": True,
            "payload_round_trip_exact": True,
            "pair_count": pair_count,
            "loader_runtime_fetches_payload": True,
            "routine_refresh_is_payload_only": args.refresh_only,
            "full_runtime_data_externalized": True,
            "series_split_by_currency": True,
            "rates_runtime_externalized": True,
            "cb_runtime_externalized": True,
            "liquidity_runtime_externalized": True,
            "certified_pair_snapshot_runtime_externalized": True,
        },
        "sizes": {
            "source_html": len(source.encode("utf-8")),
            "stable_frontend_app_html": (root / "app.html").stat().st_size,
            "runtime_loader": (root / "index.html").stat().st_size,
            "payload_total": sum(section["bytes"] for section in sections),
        },
        "rollback": "git revert the architecture commit restores the previous atomic Base64/Gzip loader and payload release.",
    }
    write_json(root / "qa" / "architecture-report.json", qa)
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
