#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

START = (2018, 1)
END = (2026, 8)
MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
ROW_KEYS = [
    "reference_month", "unemployment_rate_pct", "release_date",
    "release_geo_vintage", "source_url", "page_sha256", "source_route",
    "pit_status",
]
SEMANTIC_KEYS = [
    "reference_month", "unemployment_rate_pct", "release_date",
    "release_geo_vintage", "source_route", "pit_status",
]
MIN_REQUEST_INTERVAL_SECONDS = 1.0
_LAST_REQUEST_AT = 0.0


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        s = " ".join(data.split())
        if s:
            self.parts.append(s)


def text_from_html(raw: bytes) -> str:
    p = Text()
    p.feed(raw.decode("utf-8", errors="replace"))
    return html.unescape(" ".join(p.parts))


def months():
    y, m = START
    while (y, m) <= END:
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def last_weekday_of_next_month(y: int, m: int) -> date:
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    nxt = date(ny + 1, 1, 1) if nm == 12 else date(ny, nm + 1, 1)
    d = nxt - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def candidate_dates(y: int, m: int):
    anchor = last_weekday_of_next_month(y, m)
    ordered = [anchor]
    d = anchor
    while len(ordered) < 8:
        d += timedelta(days=1)
        if d.weekday() < 5:
            ordered.append(d)
    d = anchor
    while len(ordered) < 12:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            ordered.append(d)
    yield from ordered


def urls_for(d: date):
    key = d.strftime("%d%m%Y")
    legacy, modern = [], []
    for suffix in ("AP", "BP"):
        legacy.append((
            f"EUROSTAT_UNEMPLOYMENT_LEGACY_{suffix}",
            f"https://ec.europa.eu/eurostat/web/products-euro-indicators/-/3-{key}-{suffix}",
        ))
        modern.append((
            f"EUROSTAT_UNEMPLOYMENT_WEB_{suffix}",
            f"https://ec.europa.eu/eurostat/web/products-euro-indicators/w/3-{key}-{suffix.lower()}",
        ))
    return legacy + modern if d.year <= 2024 else modern + legacy


def throttle() -> None:
    global _LAST_REQUEST_AT
    now = time.monotonic()
    wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


def fetch(url: str):
    req = urllib.request.Request(
        url, headers={"User-Agent": "global-macro-fx-quant/1.0 strict-pit"}
    )
    for attempt in range(8):
        throttle()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None
            if e.code == 429 and attempt < 7:
                retry = e.headers.get("Retry-After") if e.headers else None
                try:
                    delay = max(15.0, float(retry)) if retry else min(120.0, 15.0 * (2 ** attempt))
                except (TypeError, ValueError):
                    delay = min(120.0, 15.0 * (2 ** attempt))
                print(
                    f"[transport] Eurostat 429; retry same URL in {delay:.0f}s "
                    f"attempt={attempt + 1}/8",
                    flush=True,
                )
                time.sleep(delay)
                continue
            raise


def parse_period(text: str, y: int, m: int):
    month = MONTHS[m - 1].capitalize()
    period = f"{month} {y}"
    if re.search(rf"\b{re.escape(period)}\b", text, re.I) is None:
        return None
    pats = [
        rf"euro area\s*\((EA\d+)\)\s*seasonally[- ]adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*in\s*{re.escape(month)}\s*{y}",
        rf"euro area\s*\((EA\d+)\)\s*seasonally[- ]adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)%\s*in\s*{re.escape(month)}\s*{y}",
        rf"In\s*{re.escape(month)}\s*{y},?\s*the euro area seasonally adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)%",
    ]
    hits = []
    for i, p in enumerate(pats):
        for x in re.finditer(p, text, re.I):
            if i < 2:
                hits.append((x.group(1).upper(), float(x.group(2))))
            else:
                hits.append(("EA_CURRENT_RELEASE", float(x.group(1))))
    uniq = []
    for g, v in hits:
        if (g, v) not in uniq:
            uniq.append((g, v))
    if not uniq:
        return None
    vals = {v for _, v in uniq}
    if len(vals) != 1:
        raise ValueError(f"ambiguous unemployment headline for {period}: {uniq}")
    geos = {g for g, _ in uniq}
    geo = next(iter(geos)) if len(geos) == 1 else sorted(geos)[0]
    return geo, next(iter(vals))


def capture_one(y: int, m: int, raw_dir: Path) -> dict:
    ref = f"{y:04d}-{m:02d}"
    for d in candidate_dates(y, m):
        for route, url in urls_for(d):
            got = fetch(url)
            if got is None:
                continue
            raw, final = got
            parsed = parse_period(text_from_html(raw), y, m)
            if parsed is None:
                continue
            geo, value = parsed
            filename = f"{ref}.html"
            (raw_dir / filename).write_bytes(raw)
            return {
                "reference_month": ref,
                "release_date": d.isoformat(),
                "source_url": final,
                "source_route": route,
                "raw_file": filename,
                "page_sha256": hashlib.sha256(raw).hexdigest(),
                "capture_parse_geo": geo,
                "capture_parse_value": value,
            }
    raise ValueError(f"no official Eurostat unemployment first release found for {ref}")


def capture(raw_dir: Path) -> int:
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    total = 104
    for i, (y, m) in enumerate(months(), 1):
        rec = capture_one(y, m, raw_dir)
        manifest.append(rec)
        (raw_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"[capture {i:03d}/{total}] {rec['reference_month']} "
            f"UNEMP={rec['capture_parse_value']} geo={rec['capture_parse_geo']} "
            f"release={rec['release_date']}",
            flush=True,
        )
    assert len(manifest) == 104
    return 0


def replay_row(rec: dict, raw_dir: Path) -> dict:
    ref = rec["reference_month"]
    y, m = map(int, ref.split("-"))
    raw = (raw_dir / rec["raw_file"]).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != rec["page_sha256"]:
        raise ValueError(f"raw sha mismatch for {ref}: {sha} != {rec['page_sha256']}")
    parsed = parse_period(text_from_html(raw), y, m)
    if parsed is None:
        raise ValueError(f"replay parser did not recover unemployment headline for {ref}")
    geo, value = parsed
    return {
        "reference_month": ref,
        "unemployment_rate_pct": value,
        "release_date": rec["release_date"],
        "release_geo_vintage": geo,
        "source_url": rec["source_url"],
        "page_sha256": sha,
        "source_route": rec["source_route"],
        "pit_status": "STRICT_FIRST_RELEASE",
    }


def digest(rows) -> str:
    canon = [{k: r[k] for k in SEMANTIC_KEYS} for r in rows]
    return hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def write_outputs(csv_path: Path, evidence_path: Path, rows: list[dict]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ROW_KEYS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    ev = {
        "schema": "GMFQ_EUR_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "EUR.labour",
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT",
        "authority": "Eurostat",
        "coverage": {
            "start": "2018-01", "end": "2026-08",
            "expected_months": 104, "materialized_months": len(rows),
        },
        "series_contract": {
            "series_id": "EA_UNEMP", "frequency": "M",
            "transformation": "level", "unit": "%",
            "first_release_semantics": "MONTHLY_UNEMPLOYMENT_HEADLINE_AS_PUBLISHED",
            "geography_semantics": "CONTEMPORANEOUS_EURO_AREA_COMPOSITION_AS_PUBLISHED",
        },
        "unique_page_hashes": len({r["page_sha256"] for r in rows}),
        "semantic_rowset_sha256": digest(rows),
        "semantic_fingerprint_fields": SEMANTIC_KEYS,
        "strict_rules": {
            "official_publisher_only": True,
            "period_specific_release_artifact_required": True,
            "publication_date_required": True,
            "url_and_sha256_required": True,
            "current_revised_history_forbidden": True,
            "revised_history_fallback_used": False,
            "network_capture_once_replay_twice": True,
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")


def replay(raw_dir: Path, csv_path: Path, evidence_path: Path) -> int:
    manifest_path = raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest) != 104:
        raise ValueError(f"expected 104 captured releases, got {len(manifest)}")
    rows = [replay_row(rec, raw_dir) for rec in manifest]
    assert rows[0]["reference_month"] == "2018-01"
    assert rows[-1]["reference_month"] == "2026-08"
    by = {r["reference_month"]: r for r in rows}
    anchors = {
        "2018-01": (8.6, "2018-03-01"),
        "2026-07": (6.4, "2026-09-01"),
        "2026-08": (6.4, "2026-10-01"),
    }
    for k, (v, d) in anchors.items():
        assert abs(by[k]["unemployment_rate_pct"] - v) < 1e-12 and by[k]["release_date"] == d, (k, by[k])
    write_outputs(csv_path, evidence_path, rows)
    ev = json.loads(evidence_path.read_text(encoding="utf-8"))
    ev["anchor_checks"] = {k: {"rate": v, "release_date": d} for k, (v, d) in anchors.items()}
    evidence_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ev, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    cap = sub.add_parser("capture")
    cap.add_argument("--raw-dir", type=Path, required=True)

    rep = sub.add_parser("replay")
    rep.add_argument("--raw-dir", type=Path, required=True)
    rep.add_argument("--csv", type=Path, required=True)
    rep.add_argument("--evidence", type=Path, required=True)

    args = ap.parse_args()
    if args.mode == "capture":
        return capture(args.raw_dir)
    return replay(args.raw_dir, args.csv, args.evidence)


if __name__ == "__main__":
    raise SystemExit(main())
