#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import calendar
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json"

SPECS = {
    "USD": {
        "exchange": "CBOT",
        "root": "ZQ",
        "chain_url": "https://www.tradingview.com/symbols/CBOT-ZQ1%21/contracts/",
        "contract_url": "https://www.tradingview.com/symbols/CBOT-ZQ1%21/?contract={contract}",
        "instrument": "30 Day Federal Funds Futures",
        "confidence": "B",
    },
    "EUR": {
        "exchange": "EUREX",
        "root": "FST3",
        "chain_url": "https://www.tradingview.com/symbols/EUREX-FST31%21/contracts/",
        "contract_url": "https://www.tradingview.com/symbols/EUREX-FST31%21/?contract={contract}",
        "instrument": "Three-Month Euro STR Futures",
        "confidence": "B",
    },
    "CHF": {
        "exchange": "ICEEUR",
        "root": "SA3",
        "chain_url": "https://www.tradingview.com/symbols/ICEEUR-SA31%21/contracts/",
        "contract_url": "https://www.tradingview.com/symbols/ICEEUR-SA31%21/?contract={contract}",
        "instrument": "Three Month SARON",
        "confidence": "B",
    },
}
TARGET_DAYS = {"3m": 90, "6m": 180, "12m": 365}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/155 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
CONTRACT_RE = re.compile(
    r'\{"fullname":"(?P<fullname>[^"]+)","short_name":"(?P<short>[^"]+)"'
    r'.{0,1400}?"expiration":"(?P<expiration>\d{8})"'
    r'.{0,500}?"contract_description":"(?P<description>[^"]*)"'
    r'.{0,500}?"instrument_name":"(?P<instrument>[^"]*)"',
    re.S,
)
# SSR hydrated daily-bar metadata contains an actual per-instrument update time.
# Only accept a date when daily-bar close equals the specific offer price AND
# the update clock matches the Offer timestamp independently (<=2 seconds).
SSR_BAR_RE = re.compile(
    r'"daily_bar"\s*:\s*\{\s*"close"\s*:\s*"(?P<close>[0-9]+(?:\.[0-9]+)?)"'
    r'\s*,\s*"data_update_time"\s*:\s*"(?P<updated>[0-9]+(?:\.[0-9]+)?)"'
)
OFFER_RE = re.compile(
    r'"offers"\s*:\s*\{[^{}]*?"price"\s*:\s*"(?P<price>[0-9]+(?:\.[0-9]+)?)"'
    r'[^{}]*?"priceCurrency"\s*:\s*"(?P<currency>[A-Z]+)"'
    r'[^{}]*?"priceValidUntil"\s*:\s*"(?P<valid>[^"]+)"',
    re.S,
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}: {url}")
        return body


def business_days_ago(as_of: date, today: date) -> int:
    if as_of > today:
        return 0
    d = as_of
    n = 0
    while d < today:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def parse_contracts(html: str, spec: dict) -> list[dict]:
    rows = []
    seen = set()
    for m in CONTRACT_RE.finditer(html):
        full = m.group("fullname")
        short = m.group("short")
        if not full.startswith(spec["exchange"] + ":") or not short.startswith(spec["root"]):
            continue
        # Continuous futures (e.g. FST31!) are not dated contracts and must
        # never enter the 3M/6M/12M curve. Only explicit listed expiries qualify.
        if "!" in short or "!" in full:
            continue
        if short in seen:
            continue
        seen.add(short)
        expiry = datetime.strptime(m.group("expiration"), "%Y%m%d").date()
        rows.append({
            "symbol": full,
            "contract": short,
            "expiration": expiry,
            "description": m.group("description"),
            "instrument_name": m.group("instrument"),
        })
    rows.sort(key=lambda x: x["expiration"])
    if len(rows) < 6:
        raise RuntimeError(f"{spec['exchange']}: only {len(rows)} dated contracts parsed")
    return rows


def saron_window(contract: str) -> tuple[date, date]:
    """ICE SA3 quarter names START the compounded SARON accrual window.

    Source: ICE Three Month SARON futures contract specifications and expiry
    calendar. This is not a spot 3M/6M/12M OIS or interpolation.
    """
    m = re.fullmatch(r"SA3([HMUZ])(\d{4})", contract)
    if m is None:
        raise ValueError("unrecognised ICE quarterly SARON listed contract")
    month = {"H": 3, "M": 6, "U": 9, "Z": 12}[m.group(1)]
    year = int(m.group(2))

    def third_wednesday(y: int, mo: int) -> date:
        first = date(y, mo, 1)
        return first + timedelta(days=(2 - first.weekday()) % 7 + 14)

    start = third_wednesday(year, month)
    end_month = month + 3
    end_year = year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    # Listed last trading/final-settlement day: Tuesday before next
    # quarterly contract's third Wednesday (holiday adjustments may exist).
    end = third_wednesday(end_year, end_month) - timedelta(days=1)
    return start, end


def recover_chf_ice_quarters(rows: list[dict]) -> list[dict]:
    """Recover missing *identity metadata* between two listed ICE SARON quarters.

    TradingView SSR can omit one contract from the strict name/expiry parser
    even when ICE lists the consecutive quarterly months. ICE defines the
    quarter code, accrual start and last trading day; no quote, level or
    timestamp is ever inferred here. The subsequently fetched dedicated
    contract page must independently supply a verified daily-bar price.
    Only one absent quarter between *two* good listed bookends is recovered.
    """
    eligible = {}
    month_code = {3: "H", 6: "M", 9: "U", 12: "Z"}
    for row in rows:
        code = str(row.get("contract") or "")
        try:
            start, end = saron_window(code)
        except ValueError:
            continue
        if row.get("symbol") != "ICEEUR:" + code or row.get("expiration") != end:
            continue
        eligible[(start.year, start.month)] = row
    recovered = dict(eligible)
    for year, month in sorted(eligible):
        next_month, next_year = (3, year + 1) if month == 12 else (month + 3, year)
        following_month, following_year = ((3, next_year + 1)
                                          if next_month == 12 else (next_month + 3, next_year))
        if (next_year, next_month) in eligible:
            continue
        # No extrapolation outside known ICE listings, nor over larger gaps.
        if (following_year, following_month) not in eligible:
            continue
        code = f"SA3{month_code[next_month]}{next_year}"
        start, expiry = saron_window(code)
        recovered[(next_year, next_month)] = {
            "symbol": "ICEEUR:" + code,
            "contract": code,
            "expiration": expiry,
            "description": f"ICE quarter {next_year}-{next_month:02d} (calendar-derived identity)",
            "instrument_name": "Three Month SARON",
            "roster_quality": "ICE_LISTED_QUARTER_CALENDAR_DERIVED_UNQUOTED",
        }
    return sorted(recovered.values(), key=lambda x: x["expiration"])


def select_contracts(rows: list[dict], today: date,
                     currency: str | None = None) -> dict[str, dict]:
    if currency == "CHF":
        rows = recover_chf_ice_quarters(rows)
        # Never map a SARON future by its END date: a Sep26 future ending
        # Dec15 was previously mislabeled 6M in late October, although its
        # interest-rate accrual already started in September.
        future = []
        for row in rows:
            start, end = saron_window(row["contract"])
            if row["expiration"] != end:
                # Neither an inconsistent vendor expiry nor a partial-rate
                # contract can become an operational CHF 6M quote.
                continue
            if start > today:
                future.append({**row, "accrual_start": start})
        selected = {}
        used = set()
        for horizon, days in TARGET_DAYS.items():
            target = today + timedelta(days=days)
            candidates = [r for r in future
                          if r["contract"] not in used
                          and abs((r["accrual_start"] - target).days) <= 50]
            if not candidates:
                raise RuntimeError(f"CHF: no dated future accrual period near {horizon}")
            row = min(candidates, key=lambda r:
                      (abs((r["accrual_start"] - target).days), r["accrual_start"]))
            selected[horizon] = row
            used.add(row["contract"])
        return selected

    future = [r for r in rows if r["expiration"] >= today]
    selected = {}
    used = set()
    for horizon, days in TARGET_DAYS.items():
        target = today + timedelta(days=days)
        candidates = [r for r in future if r["contract"] not in used]
        if not candidates:
            raise RuntimeError(f"No dated contract candidate for {horizon}")
        row = min(candidates, key=lambda r: (abs((r["expiration"] - target).days), r["expiration"]))
        if "!" in row["contract"] or "!" in row["symbol"]:
            raise RuntimeError(f"continuous contract rejected for {horizon}: {row}")
        selected[horizon] = row
        used.add(row["contract"])
    return selected


def parse_quote(html: str, expected_contract: str, today: date) -> dict:
    if expected_contract not in html:
        raise RuntimeError(f"contract page does not contain {expected_contract}")
    if "!" in expected_contract:
        raise RuntimeError(f"continuous contract forbidden: {expected_contract}")
    m = OFFER_RE.search(html)
    if not m:
        raise RuntimeError(f"no SSR Offer quote for {expected_contract}")
    price = float(m.group("price"))
    if not 80.0 < price < 105.0:
        raise RuntimeError(f"implausible futures price {price} for {expected_contract}")
    valid = datetime.fromisoformat(m.group("valid").replace("Z", "+00:00"))
    # priceValidUntil is NOT a quote observation time per Schema.org. Cross-
    # validate independent SSR daily_bar.data_update_time against this offer
    # and price before recording a timestamp. Never use validity alone.
    normalized = html.replace(chr(92) + '"', '"')
    matches = []
    for bar in SSR_BAR_RE.finditer(normalized):
        if abs(float(bar.group("close")) - price) > 0.0000001:
            continue
        observed = datetime.fromtimestamp(float(bar.group("updated")), tz=timezone.utc)
        if abs((observed - valid.astimezone(timezone.utc)).total_seconds()) <= 2.0:
            matches.append(observed)
    unique = {t.isoformat() for t in matches}
    verified = len(unique) == 1
    quote_dt = matches[0] if verified else None
    as_of = quote_dt.date() if quote_dt else None
    lag_bd = business_days_ago(as_of, today) if as_of else None
    # Even correctly timestamped quotes cannot be marked fresh after 3 sessions.
    if lag_bd is not None and lag_bd > 3:
        verified = False
        as_of = None
        lag_bd = None
    return {
        "price": price,
        "implied_rate": round(100.0 - price, 4),
        "currency": m.group("currency"),
        "quote_as_of": as_of.isoformat() if as_of else None,
        "quote_timestamp_verified": verified,
        "quote_timestamp_source": "SSR_DAILY_BAR_DATA_UPDATE_TIME" if verified else "UNVERIFIED",
        "price_valid_until": valid.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "business_day_lag": lag_bd,
    }


def collect(today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    out = {
        "schema": "GMFQ_CB_PRICING_ESTIMATED_LIVE_QUOTES_V1",
        "status": "INFORMATIONAL_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "official_ois_runtime_untouched": True,
        "currencies": {},
        "governance": {
            "informational_only": True,
            "dated_contracts_only": True,
            "continuous_contracts_allowed": False,
            "core_score_effect": "NONE",
            "bias_effect": "NONE",
            "sizing_effect": "NONE",
            "pair_engine_effect": "NONE",
            "backtest_eligible_as_official_ois": False,
        },
    }
    for ccy, spec in SPECS.items():
        contracts = parse_contracts(fetch(spec["chain_url"]), spec)
        selected = select_contracts(contracts, today, currency=ccy)
        horizons = {}
        # Collect only separately verified daily-bar observation dates.
        asofs = []
        for horizon, row in selected.items():
            url = spec["contract_url"].format(contract=row["contract"])
            q = parse_quote(fetch(url), row["contract"], today)
            if q["quote_timestamp_verified"]:
                asofs.append(q["quote_as_of"])
            horizons[horizon] = {
                "rate": q["implied_rate"],
                "futures_price": q["price"],
                "contract": row["contract"],
                "symbol": row["symbol"],
                "expiration": row["expiration"].isoformat(),
                "contract_description": row["description"],
                "quote_as_of": q["quote_as_of"],
                "quote_timestamp_verified": q["quote_timestamp_verified"],
                "quote_timestamp_source": q["quote_timestamp_source"],
                "price_valid_until": q["price_valid_until"],
                "business_day_lag": q["business_day_lag"],
                "mapping": (f"nearest ICE SARON accrual start to today+{TARGET_DAYS[horizon]}d; no interpolation"
                            if ccy == "CHF" else
                            f"nearest dated listed contract expiry to today+{TARGET_DAYS[horizon]}d; no interpolation"),
                **({"accrual_start": row["accrual_start"].isoformat()} if ccy == "CHF" else {}),
                **({"roster_quality": row["roster_quality"]} if row.get("roster_quality") else {}),
            }
        out["currencies"][ccy] = {
            "status": "LIVE_SECONDARY_READY" if len(asofs) == 3 else "LIVE_SECONDARY_INDICATIVE_ONLY",
            "confidence_grade": spec["confidence"],
            "as_of": min(asofs) if len(asofs) == 3 else None,
            "instrument": spec["instrument"],
            "source": "TradingView public server-rendered contract pages · exchange-labelled dated futures",
            "source_url": spec["chain_url"],
            "source_quality": "SECONDARY_PUBLIC_LIVE_PROXY",
            "freshness_status": "LIVE_OR_RECENT_SESSION" if len(asofs) == 3 else "QUOTE_TIMESTAMP_UNVERIFIED",
            "horizons": horizons,
            "note": "Indicative dated-futures quote levels only. TradingView Offer.priceValidUntil is not the quote observation timestamp; no freshness, synchronized curve, policy delta or repricing is certified. Never substitute this for OIS.",
        }
    return out


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
        "output": str(path),
        "currencies": {
            c: {h: {"rate": r["rate"], "contract": r["contract"]} for h, r in row["horizons"].items()}
            for c, row in data["currencies"].items()
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
