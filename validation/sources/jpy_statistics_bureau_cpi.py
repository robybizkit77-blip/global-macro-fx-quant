#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERIES_PATH = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
HEATMAP_PATH = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"
SOURCE = "Statistics Bureau of Japan / CPI"
SOURCE_URL = "https://www.stat.go.jp/english/"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def html_to_text(payload: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", payload)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text).replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_official_headline(payload: str) -> tuple[str, float, str]:
    text = html_to_text(payload)

    # Preferred live transport: the Statistics Bureau English homepage exposes
    # the national headline CPI as a compact latest-indicator block.
    en = re.search(
        r"Consumer Price Index\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*%\s*"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(20\d{2})\s*change over the year",
        text,
        flags=re.I | re.S,
    )
    if en:
        value = float(en.group(1))
        month = MONTHS[en.group(2).lower()]
        obs_date = f"{int(en.group(3)):04d}-{month:02d}"
        return obs_date, value, "Consumer Price Index / change over the year / national latest indicator"

    # Deterministic fixture and defensive fallback for the official Japanese
    # monthly-results page. Only the first headline point (all items) is valid.
    period = re.search(r"(?P<year>20\d{2})年(?:（[^）]*）)?\s*(?P<month>1[0-2]|0?[1-9])月分", text)
    point = re.search(
        r"(?:\(\s*1\s*\)|（\s*1\s*）)\s*総合指数.*?前年同月比は\s*([0-9]+(?:\.[0-9]+)?)\s*[％%]\s*の\s*(上昇|下落)",
        text,
        flags=re.S,
    )
    if not period or not point:
        raise ValueError("cannot identify official national headline CPI period/value on Statistics Bureau page")
    obs_date = f"{int(period.group('year')):04d}-{int(period.group('month')):02d}"
    raw = float(point.group(1))
    direction = point.group(2)
    value = raw if direction == "上昇" else -raw
    return obs_date, value, f"総合指数 / 前年同月比 / {direction}"


def resolve_ids() -> tuple[str, str, str, str]:
    series = load_json(SERIES_PATH)
    heat = load_json(HEATMAP_PATH)
    h = heat["currencies"]["JPY"]["inflation"]
    heat_series_id = str(h["series_id"])
    rows = series["JPY"]

    exact = [r for r in rows if str(r.get("id")) == heat_series_id]
    if len(exact) == 1:
        macro_series_id = str(exact[0]["id"])
    else:
        preferred = "JP_CPI_HEADLINE_YOY_history_value"
        pinned = [r for r in rows if str(r.get("id")) == preferred]
        if len(pinned) == 1:
            macro_series_id = preferred
        else:
            hits = []
            for r in rows:
                text = " ".join(str(r.get(k, "")) for k in ("id", "name", "title", "indicator", "label")).lower()
                if "cpi" in text and ("headline" in text or "infl" in text):
                    hits.append(r)
            if len(hits) != 1:
                raise ValueError(
                    f"cannot resolve unique JPY headline CPI MACRO_SERIES row; heatmap series_id={heat_series_id!r}"
                )
            macro_series_id = str(hits[0]["id"])

    frequency = str(h.get("frequency", "M"))
    transformation = str(h.get("transformation", "reported_yoy_rate"))
    if frequency != "M":
        raise ValueError(f"unexpected JPY CPI frequency: {frequency!r}")
    return macro_series_id, heat_series_id, frequency, transformation


def fetch_html() -> str:
    req = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "global-macro-fx-quant/1.0",
            "Accept-Language": "en,ja;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset()
    encodings = [charset, "utf-8", "cp932", "shift_jis"]
    for enc in encodings:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            pass
    raise ValueError("cannot decode Statistics Bureau response")


def build_candidate(payload: str) -> tuple[dict[str, Any], dict[str, Any]]:
    obs_date, value, semantics = extract_official_headline(payload)
    macro_series_id, heat_series_id, frequency, transformation = resolve_ids()
    candidate = {
        "currency": "JPY",
        "dimension": "inflation",
        "macro_series_id": macro_series_id,
        "observation_date": obs_date,
        "value": value,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "series_id": heat_series_id,
        "frequency": frequency,
        "transformation": transformation,
        "unit": "Percent YoY",
    }
    audit = {
        "authority": "Statistics Bureau of Japan",
        "retrieval_url": SOURCE_URL,
        "latest_period": obs_date,
        "latest_value": value,
        "matched_semantics": semantics,
        "candidate_only": True,
        "live_data_written": False,
    }
    return candidate, audit


def main() -> int:
    ap = argparse.ArgumentParser(description="Build canonical JPY headline CPI candidate from Statistics Bureau of Japan")
    ap.add_argument("--fixture", type=Path, help="Read deterministic official-page HTML fixture instead of network")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit-output", type=Path)
    args = ap.parse_args()

    if args.fixture:
        payload = args.fixture.read_text(encoding="utf-8")
        mode = "fixture"
    else:
        payload = fetch_html()
        mode = "live"

    candidate, audit = build_candidate(payload)
    audit["mode"] = mode
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True, exist_ok=True)
        args.audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate": candidate, "audit": audit}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
