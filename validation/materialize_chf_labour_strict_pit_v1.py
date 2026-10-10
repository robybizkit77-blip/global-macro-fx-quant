#!/usr/bin/env python3
"""Materialise Swiss seasonally-adjusted unemployment-rate first releases.

Strict PIT rule: use only period-specific SECO monthly release artifacts. The
published seasonally-adjusted rate is one decimal. Current SNB history is
forbidden because seasonal-adjustment history can be revised and exposes extra
precision that was not published contemporaneously.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from pypdf import PdfReader

START = (2018, 1)
END = (2026, 9)
EXPECTED_MONTHS = 105
BASE = "https://www.seco.admin.ch"
UA = "global-macro-fx-quant/chf-labour-strict-pit-v1"
MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)
MONTH_NUMBER = {name: i + 1 for i, name in enumerate(MONTHS_DE)}
DAM_ROOT = (
    BASE + "/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/"
    "Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt"
)


def months():
    year, month = START
    while (year, month) <= END:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "de"})
    with urlopen(req, timeout=60) as response:
        raw = response.read()
        return raw, response.geturl()


def release_window(year: int, month: int) -> tuple[str, str]:
    if month == 12:
        y, m = year + 1, 1
    else:
        y, m = year, month + 1
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-15"


def parse_release_date(text: str) -> str:
    patterns = (
        r"Veröffentlicht am\s+(\d{1,2})\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})",
        r"(?:Bern|Neuchâtel|Neuenburg),\s*(\d{1,2})\.(\d{1,2})\.(20\d{2})",
        r"(?:Pressedokumentation|Mediendokumentation),\s*(\d{1,2})\.(\d{1,2})\.(20\d{2})",
        r"\b(\d{1,2})\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})\b",
    )
    m = re.search(patterns[0], text)
    if m:
        return date(int(m.group(3)), MONTH_NUMBER[m.group(2)], int(m.group(1))).isoformat()
    for pattern in patterns[1:3]:
        m = re.search(pattern, text)
        if m:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    m = re.search(patterns[3], text[:1200])
    if m:
        return date(int(m.group(3)), MONTH_NUMBER[m.group(2)], int(m.group(1))).isoformat()
    raise ValueError("SECO release date missing")


def discover_newnsb(year: int, month: int) -> dict | None:
    start, end = release_window(year, month)
    query = urlencode({"from": start, "to": end, "organization": "703", "topic": ""})
    index_url = f"{BASE}/de/overview/nsb?{query}"
    raw, _ = fetch(index_url)
    soup = BeautifulSoup(raw, "html.parser")
    month_name = MONTHS_DE[month - 1]
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/newnsb/" not in href:
            continue
        context = " ".join(a.stripped_strings)
        if not context and a.parent:
            context = " ".join(a.parent.stripped_strings)
        context = re.sub(r"\s+", " ", context)
        if "Lage auf dem Arbeitsmarkt" in context and month_name in context and str(year) in context:
            candidates.append(urljoin(BASE, href))
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) > 1:
        raise ValueError(f"SECO newnsb release ambiguity {year:04d}-{month:02d}: {candidates}")
    if not candidates:
        return None
    return {"kind": "html", "url": candidates[0],
            "source_route": "SECO_PERIOD_SPECIFIC_NEWNSB_RELEASE"}


def direct_pdf_candidates(year: int, month: int) -> list[str]:
    yy = year % 100
    mm = f"{month:02d}"
    month_name = MONTHS_DE[month - 1]
    folders = [
        f"Lage_arbeitsmarkt_{year}",
        f"Arbeitsmarkt_{year}",
        f"arbeitsmarkt_{year}",
        f"lage_arbeitsmarkt_{year}",
    ]
    files = [
        f"Publikation_{month_name}_{year}.pdf.download.pdf/PRESSEDOK{yy:02d}{mm}_D.pdf",
        f"alz_{mm}_{yy:02d}.pdf.download.pdf/PRESSEDOK{yy:02d}{mm}_D.pdf",
        f"ALZ_{mm}_{yy:02d}.pdf.download.pdf/PRESSEDOK{yy:02d}{mm}_D.pdf",
        f"ALZ_PRESSEDOK_{yy:02d}{mm}.pdf.download.pdf/PRESSEDOK{yy:02d}{mm}_D.pdf",
        f"pressedok_alz_{mm}_{yy:02d}.pdf.download.pdf/pressedok_alz_{mm}_{yy:02d}_de.pdf",
        f"alz_{mm}_{year}.pdf.download.pdf/PRESSEDOK{yy:02d}{mm}_D.pdf",
    ]
    return [f"{DAM_ROOT}/{folder}/{file_name}" for folder in folders for file_name in files]


def discover_direct_pdf(year: int, month: int) -> dict:
    hits: list[tuple[str, str]] = []
    for candidate in direct_pdf_candidates(year, month):
        try:
            raw, final_url = fetch(candidate)
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        if not raw.startswith(b"%PDF"):
            continue
        hits.append((final_url, hashlib.sha256(raw).hexdigest()))
    if not hits:
        raise ValueError(f"SECO direct PDF discovery failed {year:04d}-{month:02d}")
    hashes = {sha for _, sha in hits}
    if len(hashes) != 1:
        raise ValueError(f"SECO direct PDF ambiguity {year:04d}-{month:02d}: {hits}")
    return {"kind": "pdf", "url": hits[0][0],
            "source_route": "SECO_PERIOD_SPECIFIC_DIRECT_PDF"}


def discover_release(year: int, month: int) -> dict:
    modern = discover_newnsb(year, month)
    return modern if modern is not None else discover_direct_pdf(year, month)


def pdf_text(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_rate(text: str, year: int, month: int) -> float:
    compact = re.sub(r"\s+", " ", text).replace("’", "'")
    hits: list[float] = []
    patterns = (
        r"saisonbereinigte\s+Arbeitslosenquote.{0,420}?(?:auf|bei|betrug|belief sich auf|lag bei)\s+([0-9]+[,.][0-9])\s*%",
        r"Arbeitslosenquote\s+auf\s+saisonbereinigter\s+Basis.{0,420}?(?:auf|bei|betrug|belief sich auf|lag bei|einen Wert von)\s+([0-9]+[,.][0-9])\s*%",
    )
    for pattern in patterns:
        for v in re.findall(pattern, compact, re.I):
            hits.append(float(v.replace(",", ".")))
    values = list(dict.fromkeys(hits))
    if len(values) != 1:
        raise ValueError(f"SECO reported SA unemployment-rate ambiguity {year:04d}-{month:02d}: {values}")
    return values[0]


def materialize_row(year: int, month: int) -> dict:
    source = discover_release(year, month)
    raw, final_url = fetch(source["url"])
    if source["kind"] == "pdf":
        text = pdf_text(raw)
    else:
        text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    release_date = parse_release_date(text)
    value = parse_rate(text, year, month)
    start, end = release_window(year, month)
    if not (start <= release_date <= end):
        raise ValueError(f"SECO release date outside bounded window {year:04d}-{month:02d}: {release_date}")
    return {
        "reference_month": f"{year:04d}-{month:02d}",
        "unemployment_rate_sa_pct": value,
        "release_date": release_date,
        "reported_precision_decimals": 1,
        "source_route": source["source_route"],
        "source_url": final_url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "pit_status": "STRICT_FIRST_RELEASE",
    }


def digest(rows: list[dict]) -> str:
    fields = ("reference_month", "unemployment_rate_sa_pct", "release_date", "source_route", "pit_status")
    canonical = [{k: r[k] for k in fields} for r in rows]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def materialize() -> dict:
    rows = []
    for index, (year, month) in enumerate(months(), 1):
        row = materialize_row(year, month)
        rows.append(row)
        print(f"[{index:03d}/{EXPECTED_MONTHS}] {row['reference_month']}={row['unemployment_rate_sa_pct']:.1f} release={row['release_date']} route={row['source_route']}", flush=True)
        time.sleep(0.12)
    if len(rows) != EXPECTED_MONTHS or len({r["reference_month"] for r in rows}) != EXPECTED_MONTHS:
        raise ValueError("incomplete or duplicate CHF labour coverage")
    if len({r["source_sha256"] for r in rows}) != EXPECTED_MONTHS:
        raise ValueError("period-specific SECO source hash reused")
    return {
        "schema": "GMFQ_CHF_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "CHF.labour",
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT",
        "authority": "State Secretariat for Economic Affairs (SECO)",
        "source": "SECO period-specific monthly labour-market first-release artifacts",
        "coverage": {"start": "2018-01", "end": "2026-09", "expected_months": EXPECTED_MONTHS, "materialized_months": len(rows)},
        "series_contract": {
            "series_id": "CH_UNEMP_RATE",
            "macro_series_id": "CH_UNEMP_RATE_history_value",
            "frequency": "M",
            "transformation": "level",
            "unit": "%",
            "first_release_semantics": "OFFICIAL_REPORTED_SEASONALLY_ADJUSTED_RATE_1DP",
        },
        "strict_rules": {
            "official_publisher_only": True,
            "period_specific_release_artifact_required": True,
            "reported_precision_required": "1_decimal",
            "current_snb_revised_history_forbidden": True,
            "revised_history_fallback_used": False,
        },
        "unique_source_hashes": len({r["source_sha256"] for r in rows}),
        "network_capture_count": len(rows),
        "semantic_rowset_sha256": digest(rows),
        "source_route_counts": {route: sum(r["source_route"] == route for r in rows) for route in sorted({r["source_route"] for r in rows})},
        "rows": rows,
        "current_revised_history_used": False,
        "revised_fallback_used": False,
        "changes_live_data": False,
        "changes_engine_rules": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    evidence = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
