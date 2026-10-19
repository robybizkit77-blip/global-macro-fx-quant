#!/usr/bin/env python3
"""Official SNB 10Y spot *context*, isolated from canonical paired 2Y/10Y rates.

A dated observation from the public SNB current-rates page. No SARON/BFIX
capture, no 2Y interpolation, no OIS/policy repricing, no trading/backtesting.
Fail closed on missing, ambiguous or stale observations.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
import ssl
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = "https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates"
SCHEMA = "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1"
# Require exact tenor identity and the date immediately after the quoted yield.
LINE = re.compile(
    r"Yield\s+on\s+Swiss\s+Confederation\s+bonds\s+"
    r"(?P<value>[+-]?\d{1,2}\.\d{1,4})\s*%\s*"
    r"(?P<day>\d{2}\.\d{2}\.\d{4})\s*"
    r"\(\s*Spot\s+interest\s+rate\s+for\s+10-year\s+maturities\s*\)",
    re.IGNORECASE,
)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript"):
            self.skip = max(0, self.skip-1)

    def handle_data(self, text):
        if not self.skip and text.strip():
            self.parts.append(text.strip())


def parse_official_html(raw: bytes, today: date | None = None) -> dict:
    if len(raw) < 300 or len(raw) > 2_500_000:
        raise ValueError("not a credible official HTML document size")
    decoder = VisibleText()
    decoder.feed(raw.decode("utf-8", "strict"))
    visible = " ".join(decoder.parts).replace("\u00a0", " ")
    matches = list(LINE.finditer(visible))
    if len(matches) != 1:
        raise ValueError(f"missing/ambiguous exact Swiss Confederation 10Y spot quote: {len(matches)}")
    m = matches[0]
    value = float(m.group("value"))
    day = datetime.strptime(m.group("day"), "%d.%m.%Y").date()
    now = today or datetime.now(timezone.utc).date()
    age = (now-day).days
    if not (-3.0 <= value <= 18.0):
        raise ValueError("SNB 10Y spot quote outside bounded range")
    if age < 0 or age > 5:
        raise ValueError(f"SNB 10Y quote not current: age_days={age}")
    return {"as_of": day.isoformat(), "value_percent": value, "age_calendar_days": age}


def build(quote: dict, evidence_sha256: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", evidence_sha256):
        raise ValueError("missing exact SHA256 evidence")
    return {
        "schema": SCHEMA, "status": "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL",
        "currency": "CHF", "tenor": "10Y",
        "yield_type": "SWISS_CONFEDERATION_ZERO_COUPON_SPOT",
        "as_of": quote["as_of"], "value_percent": quote["value_percent"],
        "source": "Swiss National Bank · Current interest rates · Confederation 10Y spot",
        "source_url": SOURCE,
        "provenance": "SNB_PUBLIC_PAGE_DATED_EXACT_10Y",
        "source_html_sha256": evidence_sha256,
        "capture_method": "AUTOMATED_PINNED_OFFICIAL_WEBPAGE",
        "operational_rates_2y10y_untouched": True,
        "has_current_2y": False,
        "eligible_for_curve_spreads": False,
        "eligible_for_core_signals": False,
        "eligible_for_backtests": False,
        "ois_or_saron": False,
        "note": "Separate official 10Y context only. Never join with stale 2Y or OIS.",
    }


def fetch() -> bytes:
    req = Request(SOURCE, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GMFQ-SNB-Official-10Y-Context/1.0)",
        "Accept": "text/html",
    })
    with urlopen(req, timeout=22, context=ssl.create_default_context()) as res:
        if res.status != 200 or "text/html" not in res.headers.get("content-type", "").lower():
            raise ValueError("unexpected SNB page HTTP or content-type")
        raw = res.read(2_500_001)
        if len(raw) > 2_500_000:
            raise ValueError("SNB HTML over size limit")
        return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-html", help="Local official-page fixture for tests")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = Path(args.source_html).read_bytes() if args.source_html else fetch()
    quote = parse_official_html(raw)
    candidate = build(quote, hashlib.sha256(raw).hexdigest())
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(candidate, indent=2, ensure_ascii=False, sort_keys=True)+"\n")
    print(json.dumps({"status":"SNB_10Y_INFO_ONLY", "as_of":quote["as_of"],"value_percent":quote["value_percent"],
                      "core_unchanged":True,"has_current_2y":False}))


if __name__ == "__main__":
    main()
