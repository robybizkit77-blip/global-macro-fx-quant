#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
URL_TEMPLATE = "https://www.asx.com.au/data/futures/reports/EODWebMarketSummary{stamp}ZFT.htm"
TARGET_DAYS = {"3m": 90, "6m": 180, "12m": 365}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/155 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
EXPIRY_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(20\d{2})$")


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            text = " ".join("".join(self._cell).replace("\xa0", " ").split())
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}: {url}")
        return body


def _asx_contract_expiry(month: int, year: int) -> date:
    # ASX NZ 90-day bank bill futures expire at noon on the first Wednesday
    # after the ninth day of the settlement month.
    d = date(year, month, 10)
    while d.weekday() != 2:  # Wednesday
        d += timedelta(days=1)
    return d


def _num(text: str) -> float | None:
    t = text.strip().replace(",", "")
    if not t or t in {"-", "—", "–"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _parse_bb_rows(html: str) -> list[dict]:
    parser = TableRows()
    parser.feed(html)
    rows = parser.rows
    in_bb = False
    out: list[dict] = []
    for row in rows:
        joined = " | ".join(row)
        if "BB - 90 Day Bank Bill" in joined or "BB - 90-Day Bank Bill" in joined:
            in_bb = True
            continue
        if not in_bb:
            continue
        if row and re.match(r"^[A-Z0-9]{1,4}\s*-\s*", row[0]) and "Bank Bill" not in joined:
            break
        if len(row) < 7:
            continue
        m = EXPIRY_RE.match(row[0])
        if not m:
            continue
        month = MONTHS[m.group(1)]
        year = int(m.group(2))
        settlement = _num(row[5])
        settlement_change = _num(row[6])
        if settlement is None:
            continue
        if not 80.0 < settlement < 105.0:
            raise RuntimeError(f"implausible ASX BB settlement {settlement}: {row}")
        out.append({
            "expiry_label": row[0],
            "expiration": _asx_contract_expiry(month, year),
            "settlement_price": settlement,
            "settlement_change": settlement_change,
            "implied_bank_bill_rate": round(100.0 - settlement, 4),
            "change_1d_bp": None if settlement_change is None else round(-settlement_change * 100.0, 1),
        })
    if len(out) < 3:
        raise RuntimeError(f"ASX NZ BB parser found only {len(out)} valid contracts")
    out.sort(key=lambda x: x["expiration"])
    return out


def _report_url(trade_date: date) -> str:
    return URL_TEMPLATE.format(stamp=trade_date.strftime("%y%m%d"))


def _latest_report(today: date, max_lookback_days: int = 8) -> tuple[date, str, list[dict]]:
    errors = []
    for delta in range(max_lookback_days + 1):
        d = today - timedelta(days=delta)
        if d.weekday() >= 5:
            continue
        url = _report_url(d)
        try:
            html = _fetch(url)
            rows = _parse_bb_rows(html)
            return d, url, rows
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
            errors.append(f"{d}: {exc}")
    raise RuntimeError("no usable recent ASX NZ futures report; " + " ; ".join(errors[-4:]))


def _business_days_before(d: date, n: int) -> date:
    out = d
    left = n
    while left:
        out -= timedelta(days=1)
        if out.weekday() < 5:
            left -= 1
    return out


def _historical_report(target: date, max_lookback_days: int = 4) -> tuple[date, str, list[dict]] | None:
    for delta in range(max_lookback_days + 1):
        d = target - timedelta(days=delta)
        if d.weekday() >= 5:
            continue
        url = _report_url(d)
        try:
            html = _fetch(url)
            return d, url, _parse_bb_rows(html)
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError):
            continue
    return None


def _select_horizons(rows: list[dict], trade_date: date) -> dict[str, dict]:
    future = [r for r in rows if r["expiration"] >= trade_date]
    selected: dict[str, dict] = {}
    used: set[str] = set()
    for horizon, days in TARGET_DAYS.items():
        target = trade_date + timedelta(days=days)
        candidates = [r for r in future if r["expiry_label"] not in used]
        if not candidates:
            raise RuntimeError(f"ASX NZ BB: no contract candidate for {horizon}")
        row = min(candidates, key=lambda r: (abs((r["expiration"] - target).days), r["expiration"]))
        selected[horizon] = dict(row)
        selected[horizon]["mapping"] = f"nearest listed expiry to trade_date+{days}d; no interpolation"
        used.add(row["expiry_label"])
    return selected


def collect(today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    trade_date, source_url, current_rows = _latest_report(today)
    selected = _select_horizons(current_rows, trade_date)

    prior_target = _business_days_before(trade_date, 5)
    prior = _historical_report(prior_target)
    prior_by_expiry: dict[str, dict] = {}
    prior_date = None
    prior_url = None
    if prior is not None:
        prior_date, prior_url, prior_rows = prior
        prior_by_expiry = {r["expiry_label"]: r for r in prior_rows}

    for row in selected.values():
        old = prior_by_expiry.get(row["expiry_label"])
        if old is None:
            row["change_1w_bp"] = None
            row["weekly_reference_trade_date"] = None
        else:
            row["change_1w_bp"] = round((row["implied_bank_bill_rate"] - old["implied_bank_bill_rate"]) * 100.0, 1)
            row["weekly_reference_trade_date"] = prior_date.isoformat() if prior_date else None

    return {
        "schema": "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1",
        "status": "LIVE_DIRECTIONAL_PROXY_READY",
        "as_of": trade_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "currency": "NZD",
        "instrument": "ASX New Zealand 90 Day Bank Accepted Bill Futures (BB)",
        "source": "ASX official NZ futures end-of-day total traded report",
        "source_url": source_url,
        "weekly_reference_source_url": prior_url,
        "source_quality": "OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY",
        "confidence_grade": "B_FOR_DIRECTION_C_FOR_POLICY_LEVEL",
        "basis_warning": "Bank-bill/FRA rates contain bank-credit and term/basis components. Do not treat these levels as OCR OIS and do not compute OCR policy deltas from them.",
        "mapping_policy": "Directional market-rates proxy only; 3M/6M/12M use nearest listed expiry with no interpolation. 1W compares the same contract expiry only.",
        "horizons": selected,
        "governance": {
            "informational_only": True,
            "substitutes_for_ois_level": False,
            "policy_delta_from_proxy_allowed": False,
            "core_score_effect": "NONE",
            "bias_effect": "NONE",
            "sizing_effect": "NONE",
            "pair_engine_effect": "NONE",
            "backtest_eligible_as_official_ois": False,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    data = collect()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "as_of": data["as_of"],
        "horizons": {
            h: {
                "contract": r["expiry_label"],
                "bank_bill_rate": r["implied_bank_bill_rate"],
                "change_1d_bp": r["change_1d_bp"],
                "change_1w_bp": r["change_1w_bp"],
            }
            for h, r in data["horizons"].items()
        },
        "ois_level_substitution": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
