#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pypdf import PdfReader

START = (2018, 1)
END = (2026, 8)
EXPECTED_MONTHS = 104
BASE = "https://www.e-stat.go.jp"
SCHEMA = "GMFQ_JPY_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME"
SERIES_ID = "JP_CPI_HEADLINE_YOY"
MACRO_SERIES_ID = "JP_CPI_HEADLINE_YOY_history_value"
AUTHORITY = "Statistics Bureau of Japan / e-Stat"
SOURCE = "e-Stat period-specific national CPI result-summary PDFs"
MIN_REQUEST_INTERVAL_SECONDS = 0.35
QCODE = {1: "110103", 2: "120406", 3: "230709", 4: "241012"}

ROUTES = [
    ((2018, 1), (2021, 6), "2015_BASE", "000001084976", "000001085955"),
    ((2021, 7), (2026, 6), "2020_BASE", "000001150147", "000001150149"),
    ((2026, 7), (2026, 8), "2025_BASE", "000001243876", "000001243877"),
]


def iter_months(start: tuple[int, int], end: tuple[int, int]):
    y, m = start
    while (y, m) <= end:
        yield y, m
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def get(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GMFQ-Strict-PIT-validation/3.0",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read(), resp.headers.get("Content-Type", ""), resp.geturl()
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == 5:
                break
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def pdf_text(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    chunks = [(p.extract_text() or "") for p in reader.pages[:4]]
    text = "\n".join(chunks).replace("\u3000", " ").replace("−", "-").replace("－", "-")
    return re.sub(r"[ \t]+", " ", text)


def era_year(era: str, n: int) -> int:
    if era == "平成":
        return 1988 + n
    if era == "令和":
        return 2018 + n
    raise ValueError(f"unsupported Japanese era: {era}")


def parse_release_date(text: str) -> str:
    g = re.search(r"(?<!\d)(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月\s*([0-3]?\d)\s*日", text)
    if g:
        return f"{int(g.group(1)):04d}-{int(g.group(2)):02d}-{int(g.group(3)):02d}"
    e = re.search(r"(平成|令和)\s*([0-9０-９]+|元)\s*年\s*([0-9０-９]{1,2})\s*月\s*([0-9０-９]{1,2})\s*日", text)
    if e:
        trans = str.maketrans("０１２３４５６７８９", "0123456789")
        ey = 1 if e.group(2) == "元" else int(e.group(2).translate(trans))
        return f"{era_year(e.group(1), ey):04d}-{int(e.group(3).translate(trans)):02d}-{int(e.group(4).translate(trans)):02d}"
    raise ValueError("cannot parse release date from CPI PDF")


def parse_headline_yoy(text: str) -> float:
    compact = re.sub(r"\s+", "", text)
    pats = [
        r"総合指数.*?前年同月比は([0-9]+(?:\.[0-9]+)?)%の(上昇|下落)",
        r"総合指数.*?前年同月比([0-9]+(?:\.[0-9]+)?)%の(上昇|下落)",
        r"総合.*?前年同月比は([0-9]+(?:\.[0-9]+)?)%の(上昇|下落)",
    ]
    for pat in pats:
        m = re.search(pat, compact, flags=re.S)
        if m:
            v = float(m.group(1))
            return v if m.group(2) == "上昇" else -v
    z = re.search(r"総合指数.*?前年同月比(?:は)?0(?:\.0+)?%.*?(同水準|横ばい)", compact, flags=re.S)
    if z:
        return 0.0
    raise ValueError("cannot parse national all-items CPI YoY from CPI PDF")


def parse_period(text: str) -> tuple[int, int] | None:
    compact = re.sub(r"\s+", "", text)
    g = re.search(r"全国(20\d{2})年.*?([0-9]{1,2})月分", compact)
    if g:
        return int(g.group(1)), int(g.group(2))
    e = re.search(r"全国.*?(平成|令和)([0-9０-９]+|元)年.*?([0-9０-９]{1,2})月分", compact)
    if e:
        trans = str.maketrans("０１２３４５６７８９", "0123456789")
        ey = 1 if e.group(2) == "元" else int(e.group(2).translate(trans))
        return era_year(e.group(1), ey), int(e.group(3).translate(trans))
    return None


def month_code(m: int) -> str:
    return QCODE[(m - 1) // 3 + 1] + f"{m:02d}"


def route_for(y: int, m: int) -> tuple[str, str, str]:
    for start, end, name, tstat, tclass1 in ROUTES:
        if start <= (y, m) <= end:
            return name, tstat, tclass1
    raise ValueError(f"no CPI archive route for {y:04d}-{m:02d}")


def exact_estat_record(y: int, m: int) -> dict[str, Any]:
    route_name, tstat, tclass1 = route_for(y, m)
    params = {
        "cycle": "1",
        "layout": "datalist",
        "month": month_code(m),
        "page": "1",
        "result_back": "1",
        "tclass1": tclass1,
        "tclass2val": "0",
        "toukei": "00200573",
        "tstat": tstat,
        "year": f"{y}0",
    }
    search_url = BASE + "/stat-search/files?" + urlencode(params)
    raw, _, _ = get(search_url)
    page = html.unescape(raw.decode("utf-8", "replace"))
    ids: list[str] = []
    for hit in re.finditer(r"(?:stat_infid|statInfId)=(\d+)", page, re.I):
        window = html.unescape(page[max(0, hit.start() - 1400): hit.end() + 1400])
        if "結果の概要（全国）" in window or "結果の概要(全国)" in window:
            ids.append(hit.group(1))
    ids = list(dict.fromkeys(ids))

    candidates: list[dict[str, Any]] = []
    for sid in ids:
        meta_url = BASE + "/stat-search/files?" + urlencode({"stat_infid": sid})
        mraw, _, mfinal = get(meta_url)
        meta = html.unescape(mraw.decode("utf-8", "replace"))
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", meta))
        if "消費者物価指数" not in plain or "結果の概要（全国）" not in plain:
            continue
        if not re.search(rf"調査年月\s*{y}年\s*{m}月", plain):
            continue
        pub = re.search(r"公開年月日時分\s*(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})", plain)
        if not pub:
            continue
        durl = BASE + "/stat-search/file-download?" + urlencode({"fileKind": "2", "statInfId": sid})
        draw, ct, dfinal = get(durl)
        if not draw.startswith(b"%PDF"):
            continue
        text = pdf_text(draw)
        period = parse_period(text)
        if period is not None and period != (y, m):
            continue
        value = parse_headline_yoy(text)
        pdf_date = parse_release_date(text)
        if pdf_date != pub.group(1):
            raise ValueError(f"PDF/metadata release-date mismatch {y:04d}-{m:02d}: {pdf_date}!={pub.group(1)}")
        candidates.append({
            "route": route_name,
            "stat_inf_id": sid,
            "release_date": pub.group(1),
            "release_time_jst": pub.group(2),
            "metadata_url": mfinal,
            "source_url": dfinal,
            "content_type": ct,
            "raw": draw,
            "value": value,
        })
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS)

    uniq = {hashlib.sha256(c["raw"]).hexdigest(): c for c in candidates}
    if len(uniq) != 1:
        raise ValueError(f"e-Stat CPI exact-release ambiguity {y:04d}-{m:02d}: {len(uniq)} unique compatible PDFs from {len(ids)} ids")
    return next(iter(uniq.values()))


def semantic_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        [{k: r[k] for k in ("observation_date", "value", "release_date", "source_sha256")} for r in rows],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def replay(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in captured:
        raw = bytes.fromhex(item["source_hex"])
        text = pdf_text(raw)
        y, m = map(int, item["observation_date"].split("-"))
        period = parse_period(text)
        if period is not None and period != (y, m):
            raise ValueError(f"replay period mismatch {item['observation_date']}: {period}")
        rd = parse_release_date(text)
        if rd != item["release_date"]:
            raise ValueError(f"replay release-date mismatch {item['observation_date']}: {rd}!={item['release_date']}")
        out.append({k: item[k] for k in ("observation_date", "value", "release_date", "release_time_jst", "availability_timestamp_jst", "route", "stat_inf_id", "metadata_url", "source_url", "source_sha256")})
        if parse_headline_yoy(text) != item["value"]:
            raise ValueError(f"replay value mismatch {item['observation_date']}")
        if hashlib.sha256(raw).hexdigest() != item["source_sha256"]:
            raise ValueError(f"replay hash mismatch {item['observation_date']}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    months = list(iter_months(START, END))
    if len(months) != EXPECTED_MONTHS:
        raise ValueError(f"contract bug: expected {EXPECTED_MONTHS} months, got {len(months)}")

    rows: list[dict[str, Any]] = []
    captured: list[dict[str, Any]] = []
    for idx, (y, m) in enumerate(months, 1):
        rec = exact_estat_record(y, m)
        obs = f"{y:04d}-{m:02d}"
        digest = hashlib.sha256(rec["raw"]).hexdigest()
        row = {
            "observation_date": obs,
            "value": rec["value"],
            "release_date": rec["release_date"],
            "release_time_jst": rec["release_time_jst"],
            "availability_timestamp_jst": rec["release_date"] + "T" + rec["release_time_jst"] + ":00+09:00",
            "route": rec["route"],
            "stat_inf_id": rec["stat_inf_id"],
            "metadata_url": rec["metadata_url"],
            "source_url": rec["source_url"],
            "source_sha256": digest,
        }
        rows.append(row)
        captured.append({**row, "source_hex": rec["raw"].hex()})
        print(f"[capture {idx:03d}/{EXPECTED_MONTHS}] {obs} CPI_YOY={row['value']} release={row['release_date']} route={row['route']} sha={digest[:12]}", flush=True)
        time.sleep(MIN_REQUEST_INTERVAL_SECONDS)

    if len({r["source_sha256"] for r in rows}) != EXPECTED_MONTHS:
        raise ValueError("strict invariant failed: expected one unique source hash per monthly release")
    if [r["observation_date"] for r in rows] != [f"{y:04d}-{m:02d}" for y, m in months]:
        raise ValueError("strict invariant failed: coverage/order mismatch")
    for r in rows:
        if date.fromisoformat(r["release_date"]) <= date.fromisoformat(r["observation_date"] + "-01"):
            raise ValueError(f"strict invariant failed: implausible release chronology {r}")
        if r["release_time_jst"] != "08:30":
            raise ValueError(f"strict invariant failed: unexpected publication time {r}")

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
        "route_transitions": {"2015_base_end": "2021-06", "2020_base_start": "2021-07", "2020_base_end": "2026-06", "2025_base_start": "2026-07"},
        "semantic_rowset_sha256": sh,
        "anchors": {
            "2018-01": next(r for r in rows if r["observation_date"] == "2018-01"),
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
