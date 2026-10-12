#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path

ALLOWED_STATUS = {"GREEN", "STALE", "WITHHELD", "ERROR"}
REQUIRED_FIELDS = {"layer", "key", "source", "updater", "cadence", "as_of", "max_lag_days", "status", "reason", "provenance"}
CORE_LAYERS = {"PRICE", "RATES", "COT", "MACRO", "CB_PRICING", "LIQUIDITY", "RISK", "EVENT_CALENDAR"}


def parse_date(value):
    if value is None:
        return None
    return dt.date.fromisoformat(value)


def runtime_price_overlay_as_of(path=Path("payload/part-15.txt")):
    if not path.exists():
        return None, ["Price runtime payload/part-15.txt is missing"]
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r'<script id="gmfq-price-ecb-(\d{8})">', text)
    if len(matches) != 1:
        return None, [f"expected exactly one ECB Price runtime overlay, got {len(matches)}"]
    raw = matches[0]
    value = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    try:
        parse_date(value)
    except Exception as exc:
        return None, [f"invalid ECB Price runtime overlay date: {exc}"]
    return value, []


def validate(data, runtime_d=None, price_runtime_as_of=None):
    errors = []
    if data.get("schema") != "GMFQ_FRESHNESS_REGISTRY_V1":
        errors.append("invalid schema")
    try:
        registry_date = parse_date(data.get("as_of"))
    except Exception as exc:
        errors.append(f"invalid registry as_of: {exc}")
        registry_date = None

    policy = data.get("policy") or {}
    if policy.get("fail_closed") is not True:
        errors.append("policy.fail_closed must be true")
    if policy.get("registry_is_observability_only") is not True:
        errors.append("registry must remain observability-only")
    if policy.get("must_not_change_bias_score_or_sizing") is not True:
        errors.append("registry must not change bias/score/sizing")

    records = data.get("records")
    if not isinstance(records, list) or not records:
        return errors + ["records must be a non-empty list"]

    seen = set()
    present_layers = set()
    by_ident = {}
    for i, record in enumerate(records):
        prefix = f"records[{i}]"
        missing = REQUIRED_FIELDS - set(record)
        if missing:
            errors.append(f"{prefix}: missing fields {sorted(missing)}")
            continue
        ident = (record["layer"], record["key"])
        if ident in seen:
            errors.append(f"{prefix}: duplicate identity {ident}")
        seen.add(ident)
        by_ident[ident] = record
        present_layers.add(record["layer"])

        status = record["status"]
        if status not in ALLOWED_STATUS:
            errors.append(f"{prefix}: invalid status {status}")
        if not isinstance(record["reason"], str) or not record["reason"].strip():
            errors.append(f"{prefix}: reason is required")
        if not isinstance(record["source"], str) or not record["source"].strip():
            errors.append(f"{prefix}: source is required")
        if not isinstance(record["updater"], str) or not record["updater"].strip():
            errors.append(f"{prefix}: updater is required")
        if not isinstance(record["cadence"], str) or not record["cadence"].strip():
            errors.append(f"{prefix}: cadence is required")

        try:
            as_of = parse_date(record["as_of"])
        except Exception as exc:
            errors.append(f"{prefix}: invalid as_of: {exc}")
            as_of = None

        max_lag = record["max_lag_days"]
        if max_lag is not None and (not isinstance(max_lag, int) or max_lag < 0):
            errors.append(f"{prefix}: max_lag_days must be null or non-negative integer")

        provenance = record["provenance"]
        has_proof = bool(as_of) or bool(provenance)
        if status == "GREEN" and not has_proof:
            errors.append(f"{prefix}: GREEN without as_of or provenance proof")
        if status in {"WITHHELD", "ERROR"} and len(record["reason"].strip()) < 8:
            errors.append(f"{prefix}: {status} requires an explicit blocker/reason")

        if registry_date and as_of and isinstance(max_lag, int):
            age = (registry_date - as_of).days
            if age < 0:
                errors.append(f"{prefix}: future as_of date")
            if status == "GREEN" and age > max_lag:
                errors.append(f"{prefix}: GREEN but age {age}d exceeds max lag {max_lag}d")
            if status == "STALE" and age <= max_lag:
                errors.append(f"{prefix}: STALE but age {age}d is within max lag {max_lag}d")

        if status == "WITHHELD" and record["layer"] == "CB_PRICING" and record["updater"] != "NONE":
            errors.append(f"{prefix}: withheld CB pricing must not claim an active updater")

    missing_layers = CORE_LAYERS - present_layers
    if missing_layers:
        errors.append(f"missing core layers: {sorted(missing_layers)}")

    required_rates = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
    got_rates = {k for layer, k in seen if layer == "RATES"}
    if got_rates != required_rates:
        errors.append(f"RATES G8 mismatch: expected={sorted(required_rates)} got={sorted(got_rates)}")

    got_cb = {k for layer, k in seen if layer == "CB_PRICING"}
    if got_cb != required_rates:
        errors.append(f"CB_PRICING G8 mismatch: expected={sorted(required_rates)} got={sorted(got_cb)}")

    macro_expected = {f"{ccy}_{dim}" for ccy in required_rates for dim in ("INFLATION", "LABOUR")}
    got_macro = {k for layer, k in seen if layer == "MACRO"}
    if got_macro != macro_expected:
        errors.append(f"MACRO 16-core mismatch: expected={sorted(macro_expected)} got={sorted(got_macro)}")

    price = by_ident.get(("PRICE", "FX_G8"))
    if not price:
        errors.append("PRICE/FX_G8 record missing")
    else:
        if runtime_d is not None:
            pairs = runtime_d.get("pairs") or []
            if len(pairs) != 28:
                errors.append(f"runtime D expected 28 pairs, got {len(pairs)}")
        if not price_runtime_as_of:
            errors.append("effective ECB Price runtime as_of is unavailable")
        else:
            if price.get("as_of") != price_runtime_as_of:
                errors.append(f"PRICE registry as_of {price.get('as_of')} differs from effective ECB runtime overlay {price_runtime_as_of}")
            if price.get("provenance") != "payload/part-15.txt":
                errors.append("PRICE provenance must point to payload/part-15.txt effective runtime overlay")
            if registry_date and isinstance(price.get("max_lag_days"), int):
                age = (registry_date - parse_date(price_runtime_as_of)).days
                expected_status = "GREEN" if age <= price["max_lag_days"] else "STALE"
                if price.get("status") != expected_status:
                    errors.append(f"PRICE runtime age {age}d requires {expected_status}, got {price.get('status')}")

    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="validation/FRESHNESS_REGISTRY_V1_2026-10-12.json")
    args = ap.parse_args()
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    runtime_path = Path("live_data/sections/D.json")
    runtime_d = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.exists() else None
    price_as_of, price_errors = runtime_price_overlay_as_of()
    errors = price_errors + validate(data, runtime_d=runtime_d, price_runtime_as_of=price_as_of)
    out = {"schema": data.get("schema"), "status": "PASS" if not errors else "FAIL", "record_count": len(data.get("records", [])), "effective_price_as_of": price_as_of, "errors": errors}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
