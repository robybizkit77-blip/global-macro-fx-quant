#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from pypdf import PdfReader

START = (2018, 1)
END = (2026, 8)
EXPECTED_MONTHS = 104
BASE_URL = "https://www.stat.go.jp/data/cpi/kako/pdf/{yyyymm}-z.pdf"
SCHEMA = "GMFQ_JPY_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME"
SERIES_ID = "JP_CPI_HEADLINE_YOY"
MACRO_SERIES_ID = "JP_CPI_HEADLINE_YOY_history_value"
AUTHORITY = "Statistics Bureau of Japan"
SOURCE = "Statistics Bureau of Japan / CPI monthly archived release PDF"
MIN_REQUEST_INTERVAL_SECONDS = 0.6


def iter_months(start: tuple[int, int], end: tuple[int, int]):
    y, m = start
    while (y, m) <= end:
        yield y, m
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "global-macro-fx-quant/1.0",
            "Accept": "application/pdf,*/*;q=0.8",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == 5:
                break
            time.sleep(2.0 * (attempt + 1))
    assert last is not None
    raise last


def pdf_text(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    chunks: list[str] = []
    for page in reader.pages[:3]:
        chunks.append(page.extract_text() or "")
    text = "\n".join(chunks)
    text = text.replace("\u3000", " ").replace("−", "-").replace("－", "-")
    return re.sub(r"[ \t]+", " ", text)


def era_year(era: str, n: int) -> int:
    if era == "平成":
        return 1988 + n
    if era == "令和":
        return 2018 + n
    raise ValueError(f"unsupported Japanese era: {era}")


def parse_release_date(text: str) -> str:
    # Modern PDFs can expose Gregorian dates; older archived PDFs use Japanese eras.
    g = re.search(r"(?<!\d)(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月\s*([0-3]?\d)\s*日", text)
    if g:
        return f"{int(g.group(1)):04d}-{int(g.group(2)):02d}-{int(g.group(3)):02d}"
    e = re.search(r"(平成|令和)\s*([0-9０-９]+|元)\s*年\s*(1[0-2]|0?[1-9]|[０-９]{1,2})\s*月\s*([0-3]?\d|[０-９]{1,2})\s*日", text)
    if e:
        trans = str.maketrans("０１２３４５６７８９", "0123456789")
        ey = 1 if e.group(2) == "元" else int(e.group(2).translate(trans))
        year = era_year(e.group(1), ey)
        month = int(e.group(3).translate(trans))
        day = int(e.group(4).translate(trans))
        return f"{year:04d}-{month:02d}-{day:02d}"
    raise ValueError("cannot parse Statistics Bureau release date from archived CPI PDF")


def parse_headline_yoy(text: str) -> float:
    # First headline bullet is All items. Keep the regex tightly bound to 総合指数.
    compact = re.sub(r"\s+", "", text)
    patterns = [
        r"総合指数.*?前年同月比は([0-9]+(?:\.[0-9]+)?)\s*[％%]の(上昇|下落)",
        r"総合.*?前年同月比は([0-9]+(?:\.[0-9]+)?)\s*[％%]の(上昇|下落)",
    ]
    hits: list[tuple[float, str]] = []
    for pat in patterns:
        m = re.search(pat, compact, flags=re.S)
        if m:
            hits.append((float(m.group(1)), m.group(2)))
            break
    if not hits:
        # Rare zero-change wording.
        z = re.search(r"総合指数.*?前年同月比は(?:0(?:\.0+)?)\s*[％%].*?(同水準|横ばい)", compact, flags=re.S)
        if z:
            return 0.0
        raise ValueError("cannot parse national all-items CPI YoY from archived CPI PDF")
    raw, direction = hits[0]
    return raw if direction == "上昇" else -raw


def parse_period_title(text: str) -> tuple[int, int] | None:
    compact = re.sub(r"\s+", "", text)
    g = re.search(r"全国(20\d{2})年.*?(1[0-2]|0?[1-9])月分", compact)
    if g:
        return int(g.group(1)), int(g.group(2))
    e = re.search(r"全国.*?(平成|令和)([0-9０-９]+|元)年.*?([0-9０-９]{1,2})月分", compact)
    if e:
        trans = str.maketrans("０１２３４５６７８９", "0123456789")
        ey = 1 if e.group(2) == "元" else int(e.group(2).translate(trans))
        return era_year(e.group(1), ey), int(e.group(3).translate(trans))
    return None


def semantic_hash(rows: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "observation_date": r["observation_date"],
            "value": r["value"],
            "release_date": r["release_date"],
            "source_sha256": r["source_sha256"],
        }
        for r in rows
    ]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def replay(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in captured:
        raw = bytes.fromhex(item["source_hex"])
        text = pdf_text(raw)
        period = parse_period_title(text)
        y, m = map(int, item["observation_date"].split("-"))
        if period is not None and period != (y, m):
            raise ValueError(f"replay period mismatch {item['observation_date']}: {period}")
        out.append(
            {
                "observation_date": item["observation_date"],
                "value": parse_headline_yoy(text),
                "release_date": parse_release_date(text),
                "source_url": item["source_url"],
                "source_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    months = list(iter_months(START, END))
    if len(months) != EXPECTED_MONTHS:
        raise ValueError(f"contract bug: expected {EXPECTED_MONTHS} months, got {len(months)}")

    captured: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for idx, (y, m) in enumerate(months, 1):
        url = BASE_URL.format(yyyymm=f"{y:04d}{m:02d}")
        raw = fetch_bytes(url)
        digest = hashlib.sha256(raw).hexdigest()
        text = pdf_text(raw)
        period = parse_period_title(text)
        if period is not None and period != (y, m):
            raise ValueError(f"official PDF period mismatch for {y:04d}-{m:02d}: parsed {period}")
        value = parse_headline_yoy(text)
        release = parse_release_date(text)
        obs = f"{y:04d}-{m:02d}"
        row = {
            "observation_date": obs,
            "value": value,
            "release_date": release,
            "source_url": url,
            "source_sha256": digest,
        }
        rows.append(row)
        captured.append({**row, "source_hex": raw.hex()})
        print(f"[capture {idx:03d}/{EXPECTED_MONTHS}] {obs} CPI_YOY={value} release={release} sha={digest[:12]}", flush=True)
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS)

    if len({r["source_sha256"] for r in rows}) != EXPECTED_MONTHS:
        raise ValueError("strict invariant failed: expected one unique source hash per monthly release")
    if [r["observation_date"] for r in rows] != [f"{y:04d}-{m:02d}" for y, m in months]:
        raise ValueError("strict invariant failed: coverage/order mismatch")
    for r in rows:
        if date.fromisoformat(r["release_date"]) <= date.fromisoformat(r["observation_date"] + "-01"):
            raise ValueError(f"strict invariant failed: implausible release chronology {r}")

    replay1 = replay(captured)
    replay2 = replay(captured)
    if replay1 != rows or replay2 != rows or replay1 != replay2:
        raise ValueError("strict invariant failed: deterministic replay mismatch")

    sh = semantic_hash(rows)
    evidence = {
        "schema": SCHEMA,
        "target": {"currency": "JPY", "dimension": "inflation", "macro_series_id": MACRO_SERIES_ID},
        "series_id": SERIES_ID,
        "authority": AUTHORITY,
        "source": SOURCE,
        "evidence_class": "STRICT_DIRECT_ARCHIVAL_PIT",
        "verdict": "STRICT_DIRECT_ARCHIVAL_PIT_CERTIFIABLE",
        "frequency": "M",
        "transformation": "reported_yoy_rate",
        "coverage": {"start": "2018-01", "end": "2026-08", "expected": EXPECTED_MONTHS, "observed": len(rows)},
        "unique_source_hashes": len({r["source_sha256"] for r in rows}),
        "network_capture_count": EXPECTED_MONTHS,
        "replay_count": 2,
        "replay_equal": True,
        "current_revised_history_used": False,
        "revised_fallback_used": False,
        "semantic_rowset_sha256": sh,
        "anchors": {
            "2026-07": next(r for r in rows if r["observation_date"] == "2026-07"),
            "2026-08": next(r for r in rows if r["observation_date"] == "2026-08"),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "coverage": evidence["coverage"], "unique_source_hashes": evidence["unique_source_hashes"], "semantic_rowset_sha256": sh, "replay_equal": True}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
