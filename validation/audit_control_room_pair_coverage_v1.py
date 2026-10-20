#!/usr/bin/env python3
"""Read-only, point-in-time coverage audit for all 28 Control Room v10 FX pairs.

Only provenance and completeness are checked. No model views, prices, trade
levels, weights or official/estimated source statuses are changed.
"""
import argparse
import itertools
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

FX = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FILES = {
    "setup": "PAIR_SETUP_OPERATIONAL_VIEW.json",
    "history": "ECB_G8_PRICE_HISTORY.json",
    "rates": "NATIVE_RATES_DATA.json",
    "ois": "OIS_OPERATIONAL_VIEW.json",
    "cot": "V250_COT_CHART_DATA.json",
    "model": "D.json",
}
LIMITS = {"price": 5, "rates": 5, "ois": 4, "cot": 10, "macro": 10}


def observed_day(raw, today, name):
    if not isinstance(raw, str) or not ISO.fullmatch(raw):
        raise ValueError(f"{name}: missing/non-ISO as-of {raw!r}")
    try:
        day = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{name}: invalid as-of {raw}") from exc
    if day > today:
        raise ValueError(f"{name}: future observation {raw} > {today}")
    return (today - day).days


def metric(raw):
    return (isinstance(raw, (int, float)) and not isinstance(raw, bool)
            and math.isfinite(raw))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def analyze(feeds, asof):
    setup, history, rates, ois, cot, model = (feeds[k] for k in FILES)
    require(setup.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1", "setup schema")
    require(setup.get("status") == "CURRENT_CANONICAL_ENGINE", "setup status")
    require(setup.get("pair_count") == 28, "setup pair_count")
    require(setup.get("price_audit", {}).get("status") == "PASS", "ECB price audit")
    require(setup.get("price_audit", {}).get("no_lookahead") is True, "ECB no-lookahead")
    require(setup.get("price_audit", {}).get("complete_return_values") == 140,
            "28x5 ECB horizons incomplete")
    require(setup.get("price_asof") == setup.get("price_audit", {}).get("as_of"),
            "setup/price audit as-of mismatch")
    require(setup.get("thesis_is_not_entry") is True and
            setup.get("entry_level_published") is False,
            "thesis/entry separation contract")
    pairs = setup.get("pairs") or {}
    require(len(pairs) == 28, "28 pair records required")
    actual = set()
    for code, row in pairs.items():
        require(re.fullmatch(r"[A-Z]{6}", code) is not None, f"invalid pair key {code}")
        a, b = code[:3], code[3:]
        require(a != b and a in FX and b in FX, f"unknown FX leg in {code}")
        key = frozenset((a, b))
        require(key not in actual, f"reverse-duplicated pair {code}")
        actual.add(key)
        require(row.get("canonical_pair") == a + "/" + b, f"{code}: canonical pair mismatch")
        require(isinstance(row.get("setup"), dict) and
                isinstance(row.get("decision_frame"), dict), f"{code}: missing model fields")
    require(actual == {frozenset(x) for x in itertools.combinations(FX, 2)},
            "28 unordered combinations not complete")

    require(history.get("schema") == "GMFQ_ECB_G8_PRICE_HISTORY_V1" and
            history.get("status") == "CURRENT_OFFICIAL_HISTORY" and
            history.get("pair_count") == 28, "ECB historical feed contract")
    require(history.get("rows") and
            history["rows"][-1].get("Date") == history.get("last_as_of"),
            "ECB last row/as-of discrepancy")
    require(set(FX).issubset(rates) and set(FX).issubset(cot) and
            set(FX).issubset(ois.get("currencies", {})), "missing G8 source coverage")
    lag = {
        "pair_model_price": observed_day(setup["price_asof"], asof, "setup.price_asof"),
        "ecb_fixing": observed_day(history["last_as_of"], asof, "ECB.last_as_of"),
        "macro_baseline": observed_day(model.get("asOf"), asof, "D.asOf"),
    }
    require(setup.get("macro_baseline_asof") == model.get("asOf"),
            "published Macro baseline as-of must match D.asOf")
    require(setup["price_asof"] <= history["last_as_of"],
            "pair model Price is ahead of the official ECB history")
    required_rate = {}
    required_ois = {}
    required_cot = {}
    legs = {}
    for c in FX:
        r = rates[c]
        rd = r.get("date")
        rage = observed_day(rd, asof, f"{c}.2Y/10Y")
        rofficial = ("OFFICIAL" in str(r.get("quality") or "")
                     and metric(r.get("2Y")) and metric(r.get("10Y")))
        required_rate[c] = bool(rofficial and rage <= LIMITS["rates"])
        o = ois["currencies"][c]
        od = o.get("as_of")
        oage = observed_day(od, asof, f"{c}.OIS")
        status = o.get("operational_status")
        require(status in {"GREEN_OFFICIAL", "GREEN_ESTIMATED", "WITHHELD"},
                f"{c}: unexpected OIS status")
        official = (status == "GREEN_OFFICIAL" and
                    o.get("quality") == "OFFICIAL_CERTIFIED" and
                    o.get("official_status") == "ACTIVE" and
                    metric((o.get("horizons") or {}).get("6m", {}).get("policy_delta_bp")))
        if status == "GREEN_OFFICIAL":
            require(official, f"{c}: falsely promoted OIS official status")
        required_ois[c] = bool(official and oage <= LIMITS["ois"])
        chart = cot[c]
        dates = chart.get("dates") or []
        require(len(dates) >= 2 and len(dates) == len(chart.get("net") or []),
                f"{c}: broken COT history")
        cday = dates[-1]
        cage = observed_day(cday, asof, f"{c}.COT")
        require(dates[-2] < dates[-1], f"{c}: unordered COT last observations")
        required_cot[c] = cage <= LIMITS["cot"]
        legs[c] = {
            "rates": {"as_of": rd, "age_days": rage,
                      "status": "OFFICIAL_CURRENT" if required_rate[c] else "WITHHELD"},
            "pricing": {"as_of": od, "age_days": oage, "source_status": status,
                        "status": "OFFICIAL_CURRENT" if required_ois[c] else "NOT_OFFICIAL_CURRENT"},
            "cot": {"as_of": cday, "age_days": cage,
                    "status": "CURRENT_CONTEXT" if required_cot[c] else "STALE_CONTEXT"},
        }
    macro_current = lag["macro_baseline"] <= LIMITS["macro"]
    model_price_current = lag["pair_model_price"] <= LIMITS["price"]
    price_current = lag["ecb_fixing"] <= LIMITS["price"]
    coverage = {}
    complete = 0
    for code in sorted(pairs):
        a, b = code[:3], code[3:]
        gaps = []
        if not macro_current:
            gaps.append("MACRO_BASELINE_STALE")
        if not model_price_current:
            gaps.append("PAIR_MODEL_PRICE_STALE")
        if not price_current:
            gaps.append("ECB_FIXING_STALE")
        for c in (a, b):
            if not required_rate[c]:
                gaps.append(c + "_RATES_WITHHELD")
            if not required_ois[c]:
                gaps.append(c + "_OIS_NOT_OFFICIAL_CURRENT")
            if not required_cot[c]:
                gaps.append(c + "_COT_STALE")
        if not gaps:
            complete += 1
        coverage[code] = {"status": "COMPLETE" if not gaps else "PARTIAL", "gaps": gaps}
    return {
        "schema": "GMFQ_CONTROL_ROOM_28_PAIR_SOURCE_AUDIT_V1",
        "as_of": asof.isoformat(),
        "integrity": "PASS",
        "coverage": "COMPLETE" if complete == 28 else "PARTIAL",
        "pair_count": len(pairs),
        "fully_supported_pairs": complete,
        "source_as_of": {"macro_baseline": model["asOf"],
                         "model_price": setup["price_asof"],
                         "ecb_fixing": history["last_as_of"]},
        "source_age_days": lag,
        "current_source_counts": {
            "rates_official": sum(required_rate.values()),
            "ois_official": sum(required_ois.values()),
            "cot_context": sum(required_cot.values()),
        },
        "source_limits_days": LIMITS,
        "currency_sources": legs,
        "pairs": coverage,
        "warning": ("PASS validates structural integrity, not that all macro/rates/OIS/"
                    "COT inputs are current. Never promote WITHHELD or estimates."),
    }


def markdown(report):
    a = report
    lines = [
        "## Control Room v10 — audit delle 28 coppie",
        f"**Integrity:** {a['integrity']} · **Source coverage:** {a['coverage']} · "
        f"**Fully supported:** {a['fully_supported_pairs']}/28",
        "",
        "| Fonte | As-of | Age (calendar days) |",
        "|---|---|---:|",
    ]
    for key in ("macro_baseline", "model_price", "ecb_fixing"):
        lag_key = "pair_model_price" if key == "model_price" else key
        lines.append(f"| {key} | {a['source_as_of'][key]} | {a['source_age_days'][lag_key]} |")
    cnt = a["current_source_counts"]
    lines.extend([
        "",
        f"- Rates official and current: **{cnt['rates_official']}/8**",
        f"- OIS/futures official and current: **{cnt['ois_official']}/8**",
        f"- COT context within cutoff: **{cnt['cot_context']}/8**",
        "",
        "### Coppie con copertura parziale",
    ])
    for code, rec in a["pairs"].items():
        if rec["gaps"]:
            lines.append(f"- {code}: " + ", ".join(rec["gaps"]))
    lines.extend(["", "> L'integrità tecnica non certifica la freschezza della tesi. "
                  "Questo audit non genera segnali, livelli o promozioni di fonti.", ""])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path("live_data/sections"))
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args()
    today = date.fromisoformat(args.asof)
    feeds = {k: json.loads((args.data_dir / file).read_text(encoding="utf-8"))
             for k, file in FILES.items()}
    report = analyze(feeds, today)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("as_of", "integrity", "coverage", "pair_count",
                       "fully_supported_pairs", "current_source_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
