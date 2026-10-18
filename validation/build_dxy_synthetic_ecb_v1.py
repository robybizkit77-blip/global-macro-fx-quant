#!/usr/bin/env python3
"""Construct an ICE-formula DXY *synthetic* from same-day official ECB fixings.

A public analytical approximation, NOT an ICE-supplied or intraday DXY quote.
Runs independently of the canonical G8 FX and pair engine.
"""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

SOURCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
WEIGHTS = {"EUR": -.576, "JPY": .136, "GBP": -.119,
           "CAD": .091, "SEK": .042, "CHF": .036}
CONSTANT = 50.14348112
REQUIRED = ("USD", "JPY", "GBP", "CAD", "CHF", "SEK")


def compute(r):
    if any(not isinstance(r.get(k), (float, int)) or r[k] <= 0 for k in REQUIRED):
        raise ValueError("complete, positive six-currency ECB reference set required")
    usd = r["USD"]
    quotes = {"EUR": usd, "JPY": r["JPY"] / usd,
              "GBP": usd / r["GBP"], "CAD": r["CAD"] / usd,
              "SEK": r["SEK"] / usd, "CHF": r["CHF"] / usd}
    value = CONSTANT * math.prod(quotes[k] ** w for k, w in WEIGHTS.items())
    if not math.isfinite(value) or not 40 < value < 200:
        raise ValueError("DXY synthetic out of plausible range")
    return round(value, 4)


def parse_ecb(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rows = {}
    for item in root.iter():
        date = item.get("time")
        if not date:
            continue
        dt.date.fromisoformat(date)
        rates = {}
        for child in item:
            ccy, raw = child.get("currency"), child.get("rate")
            if ccy and raw:
                rates[ccy] = float(raw)
        if all(k in rates for k in REQUIRED):
            rows[date] = rates
    if not rows:
        raise ValueError("ECB XML has no complete DXY basket reference rows")
    return rows


def build(fx, ecb):
    if fx.get("schema") != "GMFQ_ECB_G8_PRICE_HISTORY_V1" or fx.get("status") != "CURRENT_OFFICIAL_HISTORY":
        raise ValueError("canonical ECB G8 price feed not certified")
    overlaps = []
    for row in fx["rows"]:
        date = row.get("Date")
        if date not in ecb:
            continue
        source = ecb[date]
        # Same-day FX G8 feed must match ECB independently retrieved source
        for key in ("USD", "JPY", "GBP", "CAD", "CHF"):
            if abs(source[key] - row[key]) > 0.0000001:
                raise ValueError(f"ECB source mismatch on {date} {key}")
        overlaps.append({"date": date, "value": compute(source)})
    overlaps.sort(key=lambda x:x["date"])
    if len(overlaps) < 3:
        raise ValueError("insufficient official same-day ECB overlap for DXY history")
    as_of = overlaps[-1]["date"]
    if as_of != fx["last_as_of"]:
        raise ValueError("ECB SEK or G8 history lag mismatch; no synthetic publication")
    return {
        "schema": "GMFQ_DXY_SYNTHETIC_ECB_V1",
        "status": "ESTIMATED_INFORMATIONAL",
        "index_name": "DXY sintetico ECB (ICE-formula proxy)",
        "not_official_ice": True,
        "not_intraday": True,
        "as_of": as_of,
        "value": overlaps[-1]["value"],
        "previous_value": overlaps[-2]["value"],
        "history": overlaps,
        "method": "ICE six-currency geometric weights/constant, ECB matched-date reference FX incl SEK",
        "weights": WEIGHTS,
        "constant": CONSTANT,
        "source": "ECB euro foreign exchange reference rates; official FX fixings used as inputs, derived index is not ICE official",
        "source_url": SOURCE,
        "independent_from_core_engine": True,
        "usable_as_official_ice_or_trade_signal": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--price-file",default="live_data/sections/ECB_G8_PRICE_HISTORY.json")
    ap.add_argument("--output",default="live_data/sections/DXY_SYNTHETIC_ECB.json")
    ap.add_argument("--fixture",help="Optional local ECB XML fixture for offline QA")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        r={"USD":1.1253,"JPY":177.82,"GBP":.84385,"CAD":1.5935,"CHF":.9272,"SEK":11.145}
        assert abs(compute(r)-101.714) < .001, compute(r)
        try:
            compute({**r,"SEK":None})
            raise AssertionError("missing SEK was accepted")
        except ValueError:
            pass
        print("DXY_SYNTHETIC_ECB_FORMULA_PASS")
        return
    fx=json.loads(Path(args.price_file).read_text(encoding="utf-8"))
    if args.fixture:
        xml=Path(args.fixture).read_bytes()
    else:
        request=Request(SOURCE,headers={"User-Agent":"GMFQ-ResearchDesk-DXY-ECB/1.0"})
        with urlopen(request,timeout=35) as response:
            xml=response.read(8_000_000)
    rows=parse_ecb(xml)
    result=build(fx,rows)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DXY_SYNTHETIC_ECB_SOURCE_PASS",result["as_of"],len(result["history"]),result["value"])

if __name__=="__main__":
    main()
