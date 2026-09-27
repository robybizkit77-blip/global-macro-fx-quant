#!/usr/bin/env python3
"""Convert a self-contained GLOBAL MACRO FX QUANT dashboard into stable UI + JSON.

The script is deliberately source-agnostic: the daily refresh can pass the newly
validated HTML to it and only data/ changes afterwards.  It never recalculates or
alters a signal; it only relocates the two embedded data objects consumed by the UI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def extract_object_assignment(source: str, name: str) -> tuple[int, int, object]:
    """Return the source range and JSON value of `const NAME = {...};` safely."""
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*", source)
    if not match:
        raise ValueError(f"Assignment not found: {name}")
    start = match.start()
    cursor = match.end()
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor >= len(source) or source[cursor] != "{":
        raise ValueError(f"{name} is not an object literal")

    depth, quote, escaped = 0, None, False
    end = None
    for pos in range(cursor, len(source)):
        char = source[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = pos + 1
                break
    if end is None:
        raise ValueError(f"Unclosed object literal: {name}")
    semicolon = end
    while semicolon < len(source) and source[semicolon].isspace():
        semicolon += 1
    if semicolon < len(source) and source[semicolon] == ";":
        semicolon += 1
    return start, semicolon, json.loads(source[cursor:end])



def extract_json_assignment(source: str, name: str) -> object:
    """Extract a JSON object or array from a top-level const assignment."""
    match = re.search(rf"\\bconst\\s+{re.escape(name)}\\s*=\\s*", source)
    if not match:
        raise ValueError(f"Assignment not found: {name}")
    cursor = match.end()
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor >= len(source) or source[cursor] not in "[{":
        raise ValueError(f"{name} is not a JSON object/array literal")
    opener = source[cursor]
    closer = "}" if opener == "{" else "]"
    depth, quote, escaped = 0, None, False
    end = None
    for pos in range(cursor, len(source)):
        char = source[pos]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                end = pos + 1
                break
    if end is None:
        raise ValueError(f"Unclosed JSON literal: {name}")
    return json.loads(source[cursor:end])


def audit_price_pair_binding(dashboard: dict) -> list[dict]:
    """Catch clear stale Price votes when 1W and 4W price direction agree."""
    rows = dashboard.get("prices") or []
    pair_states = dashboard.get("pairStates") or {}
    if len(rows) < 21:
        return [{"error": "insufficient_price_history"}]
    last, w1, w4 = rows[-1], rows[-6], rows[-21]
    issues = []
    for pair, state in pair_states.items():
        try:
            a, b = pair.split("/")
            def cross(row):
                return float(row[b]) / float(row[a])
            r1 = (cross(last) / cross(w1) - 1.0) * 100.0
            r4 = (cross(last) / cross(w4) - 1.0) * 100.0
            def direction(x):
                if abs(x) < 0.20:
                    return "FLAT"
                return "UP" if x > 0 else "DOWN"
            d1, d4 = direction(r1), direction(r4)
            if d1 == d4 and d1 != "FLAT":
                expected = a if d1 == "UP" else b
                stored = ((state.get("layers") or {}).get("price"))
                if stored != expected:
                    issues.append({
                        "pair": pair,
                        "stored": stored,
                        "expected": expected,
                        "return_1w_pct": round(r1, 4),
                        "return_4w_pct": round(r4, 4),
                    })
        except Exception as exc:
            issues.append({"pair": pair, "error": str(exc)})
    return issues


def audit_pair_semantics(dashboard: dict) -> list[dict]:
    """Validate lead priority, confirms/diverges semantics and convergence counts."""
    pair_states = dashboard.get("pairStates") or {}
    issues = []
    label_to_key = {
        "Rates": "rates",
        "Banca centrale": "central_bank",
        "COT": "cot",
        "Macro": "macro",
        "Prezzo": "price",
    }
    priority = [("rates", "Rates"), ("central_bank", "Banca centrale"), ("cot", "COT"), ("macro", "Macro")]
    for pair, state in pair_states.items():
        layers = state.get("layers") or {}
        expected_lead = None
        for key, label in priority:
            value = layers.get(key)
            if value not in (None, "MISTO", "NON CONFRONTABILE"):
                expected_lead = label
                break
        actual_lead = ((state.get("lead") or [None])[0])
        if actual_lead != expected_lead:
            issues.append({"pair": pair, "type": "lead_priority", "stored": actual_lead, "expected": expected_lead})

        lead_key = label_to_key.get(actual_lead)
        lead_dir = layers.get(lead_key) if lead_key else None
        if actual_lead in ("Prezzo", "Price"):
            issues.append({"pair": pair, "type": "price_cannot_lead"})

        for label in state.get("confirms") or []:
            key = label_to_key.get(label)
            if key and layers.get(key) != lead_dir:
                issues.append({"pair": pair, "type": "confirm_semantics", "layer": label, "lead": actual_lead})
        for label in state.get("diverges") or []:
            key = label_to_key.get(label)
            if key and layers.get(key) == lead_dir:
                issues.append({"pair": pair, "type": "diverge_semantics", "layer": label, "lead": actual_lead})

        comparable = [
            layers.get(k) for k in ("macro", "rates", "central_bank", "cot", "price")
            if layers.get(k) not in (None, "MISTO", "NON CONFRONTABILE")
        ]
        winner = state.get("convergence_winner")
        if comparable:
            if winner == "MISTA":
                counts = {}
                for value in comparable:
                    counts[value] = counts.get(value, 0) + 1
                numerator = max(counts.values())
            else:
                numerator = sum(1 for value in comparable if value == winner)
            expected_count = f"{numerator}/{len(comparable)}"
            if state.get("convergence_count") != expected_count:
                issues.append({
                    "pair": pair,
                    "type": "convergence_count",
                    "stored": state.get("convergence_count"),
                    "expected": expected_count,
                })
    return issues


def audit_pair_monitor_guidance(dashboard: dict) -> list[dict]:
    """Reject obviously stale boilerplate monitoring text across heterogeneous leads."""
    pair_states = dashboard.get("pairStates") or {}
    leads = {((s.get("lead") or [None])[0]) for s in pair_states.values()}
    leads.discard(None)
    monitors = {(s.get("monitor") or "").strip() for s in pair_states.values() if (s.get("monitor") or "").strip()}
    issues = []
    if len(leads) > 1 and len(monitors) == 1 and len(pair_states) >= 8:
        issues.append({
            "type": "uniform_monitor_text_with_multiple_leads",
            "lead_count": len(leads),
            "monitor_count": len(monitors),
            "pair_count": len(pair_states),
        })
    return issues


def _find_canonical_2y_series(series_rows: list[dict]) -> dict | None:
    """Find the sovereign/front-end 2Y series, excluding mortgage/expectations proxies."""
    preferred = []
    for row in series_rows or []:
        ident = f"{row.get('id','')} {row.get('label','')} {row.get('category','')}".lower()
        if row.get("category") == "Rates" and ("2y" in ident or "2d" in ident or "rendimento 2y" in ident or "treasury 2y" in ident or "zc 2y" in ident or "spot 2y" in ident):
            preferred.append(row)
    if not preferred:
        for row in series_rows or []:
            ident = f"{row.get('id','')} {row.get('label','')}".lower()
            if ("rates" in ident or "dgs2" in ident or "zc_2y" in ident or "spot_2y" in ident) and ("2y" in ident or "2d" in ident):
                preferred.append(row)
    return preferred[0] if preferred else None


def _parse_series_date(value: object):
    """Parse the daily date formats used by Rates sources without trusting row order."""
    from datetime import datetime
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _chronological_points(series: dict, non_null_only: bool = True) -> list[tuple]:
    dates = series.get("dates") or []
    values = series.get("values") or []
    points = []
    for idx, (date, value) in enumerate(zip(dates, values)):
        parsed = _parse_series_date(date)
        if parsed is None or (non_null_only and value is None):
            continue
        points.append((parsed, idx, date, value))
    points.sort(key=lambda item: (item[0], item[1]))
    return points


def normalize_rate_series(all_series: dict) -> None:
    """Sort aligned Rates date/value pairs chronologically and refresh last_* metadata."""
    for rows in (all_series or {}).values():
        for row in rows or []:
            if row.get("category") != "Rates":
                continue
            dates = row.get("dates") or []
            values = row.get("values") or []
            if not dates or len(dates) != len(values):
                continue
            points = _chronological_points(row, non_null_only=False)
            if len(points) != len(dates):
                continue
            row["dates"] = [item[2] for item in points]
            row["values"] = [item[3] for item in points]
            non_null = [item for item in points if item[3] is not None]
            if non_null:
                row["last_date"] = non_null[-1][2]
                row["last_value"] = non_null[-1][3]


def audit_strict_canonical_rates_binding(native_rates: dict, all_series: dict) -> list[dict]:
    """JPY and AUD must use their canonical official-source series, never a cosmetic market-close patch."""
    issues = []
    for ccy in ("JPY", "AUD"):
        series = _find_canonical_2y_series(all_series.get(ccy, []))
        current = (native_rates or {}).get(ccy) or {}
        if not series:
            issues.append({"ccy": ccy, "type": "canonical_2y_series_missing"})
            continue
        points = _chronological_points(series)
        if not points:
            issues.append({"ccy": ccy, "type": "canonical_2y_history_empty"})
            continue
        _, _, expected_date, expected_value = points[-1]
        current_date = str(current.get("date") or "")
        current_value = current.get("2Y")
        if current_date != str(expected_date) or current_value is None or abs(float(current_value) - float(expected_value)) > 1e-9:
            issues.append({
                "ccy": ccy,
                "type": "native_rates_not_bound_to_canonical_2y",
                "stored_date": current_date,
                "stored_value": current_value,
                "expected_date": expected_date,
                "expected_value": expected_value,
                "series_id": series.get("id"),
            })
    return issues


def audit_what_changed_rates(what_changed: list[dict], all_series: dict) -> list[dict]:
    """Ensure What Changed uses the same homogeneous canonical 2Y history as the Rates engine."""
    issues = []
    by_ccy = {row.get("ccy"): row for row in (what_changed or [])}
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        wc = by_ccy.get(ccy)
        if not wc or wc.get("rate_move") is None:
            continue
        s = _find_canonical_2y_series(all_series.get(ccy, []))
        if not s:
            issues.append({"ccy": ccy, "type": "canonical_2y_series_missing"})
            continue
        points = _chronological_points(s)
        if len(points) < 6:
            issues.append({"ccy": ccy, "type": "insufficient_2y_history"})
            continue
        expected_bp = round((float(points[-1][3]) - float(points[-6][3])) * 100.0, 2)
        stored_bp = round(float(wc.get("rate_move")), 2)
        if abs(expected_bp - stored_bp) > 0.15:
            issues.append({
                "ccy": ccy,
                "type": "what_changed_rate_move_source_mismatch",
                "stored_bp": stored_bp,
                "expected_bp_from_canonical_2y": expected_bp,
                "series_id": s.get("id"),
                "last_date": points[-1][2],
            })
    return issues


def _numeric_forward_count(cb: dict) -> int:
    import re as _re
    count = 0
    for key in ("market_3m", "market_6m", "market_12m"):
        value = cb.get(key)
        if isinstance(value, (int, float)):
            count += 1
        elif isinstance(value, str) and _re.fullmatch(r"-?\d+(?:\.\d+)?%?", value.strip()):
            count += 1
    return count


def audit_market_pricing_prose(plain_market: dict, native_cb: dict) -> list[dict]:
    """Do not let unsupported directional market-pricing prose survive the quality gate."""
    issues = []
    directional_terms = (
        "sta prezzando", "orientato verso", "tassi più alti", "più restrittiv",
        "più hawkish", "accomodante", "ulteriori rialzi", "rialzo", "taglio"
    )
    for ccy, prose in (plain_market or {}).items():
        cb = (native_cb or {}).get(ccy) or {}
        numeric = _numeric_forward_count(cb)
        status = str(cb.get("pricing_status") or "")
        has_point_probability = "%" in status
        text = f"{prose.get('headline','')} {prose.get('detail','')}".lower()
        if numeric < 2 and not has_point_probability:
            matched = [term for term in directional_terms if term in text]
            if matched:
                issues.append({
                    "ccy": ccy,
                    "type": "unsupported_directional_market_pricing_prose",
                    "matched": matched,
                    "pricing_tier": cb.get("pricing_tier"),
                    "pricing_status": status,
                    "numeric_forward_points": numeric,
                })
    return issues


def audit_global_risk_binding(dashboard: dict) -> list[dict]:
    """Canonical WTI must retain its long history; Gold is intentionally context-only."""
    issues = []
    risk = dashboard.get("risk") or {}
    wti = risk.get("WTI") or {}
    dates = wti.get("dates") or []
    values = wti.get("values") or []
    if len(dates) != len(values):
        issues.append({"type": "wti_length_mismatch", "dates": len(dates), "values": len(values)})
    if len(dates) < 500:
        issues.append({"type": "wti_canonical_history_missing", "observations": len(dates), "required_min": 500})
    if dates and str(dates[0]) > "2016-01-31":
        issues.append({"type": "wti_history_start_too_late", "first_date": dates[0]})
    gold = risk.get("Gold") or {}
    if len(gold.get("dates") or []) > 60:
        issues.append({"type": "gold_should_remain_context_only", "observations": len(gold.get("dates") or [])})
    for pair, state in (dashboard.get("pairStates") or {}).items():
        layers = state.get("layers") or {}
        if "global_risk" in layers:
            issues.append({"pair": pair, "type": "global_risk_must_not_be_mechanical_pair_vote"})
    return issues


def audit_pair_universe_binding(dashboard: dict) -> list[dict]:
    """Ensure every executive/overview consumer sees the exact same 28-pair universe."""
    issues = []
    pairs = [row.get("pair") for row in (dashboard.get("pairs") or []) if row.get("pair")]
    states = list((dashboard.get("pairStates") or {}).keys())
    if len(pairs) != 28:
        issues.append({"type": "pair_list_count", "count": len(pairs), "expected": 28})
    if len(states) != 28:
        issues.append({"type": "pair_state_count", "count": len(states), "expected": 28})
    if set(pairs) != set(states):
        issues.append({
            "type": "pair_universe_mismatch",
            "only_in_pairs": sorted(set(pairs) - set(states)),
            "only_in_pairStates": sorted(set(states) - set(pairs)),
        })
    return issues


def audit_canonical_2y_freshness(dashboard: dict, all_series: dict) -> list[dict]:
    """Do not publish a current Rates impulse from a canonical 2Y series older than 7 calendar days."""
    from datetime import datetime
    issues = []
    as_of = str(dashboard.get("asOf") or "")
    try:
        ref = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    except Exception:
        return [{"type": "dashboard_asof_unparseable", "asOf": as_of}]
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        s = _find_canonical_2y_series(all_series.get(ccy, []))
        if not s:
            issues.append({"ccy": ccy, "type": "canonical_2y_series_missing"})
            continue
        points = _chronological_points(s)
        last_date = str(points[-1][2] if points else (s.get("last_date") or ""))
        parsed = None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(last_date, fmt)
                break
            except Exception:
                pass
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(last_date.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                issues.append({"ccy": ccy, "type": "canonical_2y_date_unparseable", "last_date": last_date})
                continue
        ref_naive = ref.replace(tzinfo=None)
        age = (ref_naive - parsed).days
        max_age_days = 10 if ccy == "AUD" else 7
        if age > max_age_days:
            issues.append({
                "ccy": ccy,
                "type": "canonical_2y_stale",
                "last_date": last_date,
                "dashboard_asof": as_of,
                "age_days": age,
                "max_age_days": max_age_days,
                "series_id": s.get("id"),
            })
    return issues

def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def write_json(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    path.write_bytes(raw + b"\n")
    return hashlib.sha256(raw).hexdigest()


LOADER = """<!doctype html>
<html lang=\"it\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>GLOBAL MACRO FX QUANT</title>
<style>html,body{margin:0;background:#06131f;color:#eef7ff;font:16px Arial,sans-serif}#loading{padding:24px}</style>
</head><body><div id=\"loading\">Caricamento GLOBAL MACRO FX QUANT…</div>
<script>
(async()=>{
  const suffix='?v='+Date.now();
  const [manifestResponse, appResponse] = await Promise.all([
    fetch('data/manifest.json'+suffix,{cache:'no-store'}),
    fetch('app.html'+suffix,{cache:'force-cache'})
  ]);
  if(!manifestResponse.ok) throw new Error('manifest '+manifestResponse.status);
  if(!appResponse.ok) throw new Error('frontend '+appResponse.status);
  const manifest=await manifestResponse.json();
  if(manifest.schema_version!==1 || !Array.isArray(manifest.sections) || !manifest.sections.length) throw new Error('manifest non valido');
  const sectionResponses=await Promise.all(manifest.sections.map(s=>fetch('data/sections/'+s.file+suffix,{cache:'no-store'})));
  if(sectionResponses.some(r=>!r.ok)) throw new Error('payload incompleto');
  const payload={};
  for(let i=0;i<manifest.sections.length;i++) payload[manifest.sections[i].key]=await sectionResponses[i].json();
  const serialised=JSON.stringify(payload).replace(/</g,'\\\\u003c').replace(/>/g,'\\\\u003e').replace(/&/g,'\\\\u0026');
  const app=await appResponse.text();
  // The marker lives inside the dashboard's first script block, so inject a
  // JavaScript statement (not a nested <script>, which would terminate it).
  const hydrated=app.replace('<!-- FX_PAYLOAD_BOOTSTRAP -->','window.__FX_PAYLOAD__='+serialised+';');
  if(hydrated===app) throw new Error('frontend non compatibile con il payload');
  document.open(); document.write(hydrated); document.close();
})().catch(e=>{document.body.innerHTML='<div style=\"padding:24px;font:16px Arial;color:#fff;background:#06131f\">Errore nel caricamento della dashboard. Riprova tra poco.<br><small>'+String(e)+'</small></div>';});
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="validated standalone dashboard HTML")
    parser.add_argument("--out", type=Path, default=Path("."), help="repository root")
    parser.add_argument("--refresh-only", action="store_true", help="update only data/ after the one-time frontend migration")
    args = parser.parse_args()
    root = args.out.resolve()
    source = args.source.read_text(encoding="utf-8")

    c_start, c_end, country_context = extract_object_assignment(source, "COUNTRY_CTX")
    d_start, d_end, dashboard = extract_object_assignment(source, "D")
    if d_start < c_end:
        raise ValueError("Unexpected assignment order")

    price_pair_binding_issues = audit_price_pair_binding(dashboard)
    if price_pair_binding_issues:
        raise ValueError("PRICE_PAIR_BINDING_MISMATCH: " + json.dumps(price_pair_binding_issues, ensure_ascii=False))

    pair_semantic_issues = audit_pair_semantics(dashboard)
    if pair_semantic_issues:
        raise ValueError("PAIR_NARRATIVE_BINDING_MISMATCH: " + json.dumps(pair_semantic_issues, ensure_ascii=False))

    pair_monitor_issues = audit_pair_monitor_guidance(dashboard)
    if pair_monitor_issues:
        raise ValueError("PAIR_MONITOR_STALE: " + json.dumps(pair_monitor_issues, ensure_ascii=False))

    pair_universe_issues = audit_pair_universe_binding(dashboard)
    if pair_universe_issues:
        raise ValueError("OVERVIEW_PAIR_UNIVERSE_MISMATCH: " + json.dumps(pair_universe_issues, ensure_ascii=False))

    payload = {"country_ctx": country_context, "dashboard": dashboard}

    # Runtime data used by the stable frontend must travel with every refresh.
    # These objects remain embedded in app.html as a safe fallback, but ui-patch.js
    # hydrates them in place from the current payload so they cannot stay frozen.
    extra_specs = [
        ("NATIVE_RATES_DATA", "native_rates", "native_rates.json"),
        ("NATIVE_CB_DATA", "native_cb", "native_cb.json"),
        ("NATIVE_LIQ_DATA", "native_liq", "native_liq.json"),
        ("CERT53", "cert53", "cert53.json"),
        ("V250_COT_CHART_DATA", "cot_charts", "cot_charts.json"),
        ("TOP_THEMES", "top_themes", "top_themes.json"),
        ("WHAT_CHANGED", "what_changed", "what_changed.json"),
        ("V247_COT_STORIES", "cot_stories", "cot_stories.json"),
        ("V241_PLAIN_MARKET", "plain_market", "plain_market.json"),
    ]
    for source_name, key, _filename in extra_specs:
        payload[key] = extract_json_assignment(source, source_name)

    market_pricing_prose_issues = audit_market_pricing_prose(
        payload.get("plain_market") or {}, payload.get("native_cb") or {}
    )
    if market_pricing_prose_issues:
        raise ValueError("MARKET_PRICING_PROSE_UNSUPPORTED: " + json.dumps(market_pricing_prose_issues, ensure_ascii=False))

    global_risk_issues = audit_global_risk_binding(dashboard)
    if global_risk_issues:
        raise ValueError("GLOBAL_RISK_BINDING_MISMATCH: " + json.dumps(global_risk_issues, ensure_ascii=False))

    # S is by far the largest live dataset. Split it by currency so no single
    # GitHub write is unnecessarily large.
    all_series = extract_json_assignment(source, "S")
    normalize_rate_series(all_series)

    strict_rates_issues = audit_strict_canonical_rates_binding(payload.get("native_rates") or {}, all_series)
    if strict_rates_issues:
        raise ValueError("STRICT_CANONICAL_RATES_BINDING_MISMATCH: " + json.dumps(strict_rates_issues, ensure_ascii=False))

    what_changed_rate_issues = audit_what_changed_rates(payload.get("what_changed") or [], all_series)
    if what_changed_rate_issues:
        raise ValueError("WHAT_CHANGED_RATES_SOURCE_MISMATCH: " + json.dumps(what_changed_rate_issues, ensure_ascii=False))

    canonical_2y_freshness_issues = audit_canonical_2y_freshness(dashboard, all_series)
    if canonical_2y_freshness_issues:
        raise ValueError("CANONICAL_RATES_STALE: " + json.dumps(canonical_2y_freshness_issues, ensure_ascii=False))

    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        payload[f"series_{ccy}"] = all_series.get(ccy, [])

    sections = []
    file_names = {
        "country_ctx": "country_ctx.json",
        "dashboard": "dashboard.json",
        "native_rates": "native_rates.json",
        "native_cb": "native_cb.json",
        "native_liq": "native_liq.json",
        "cert53": "cert53.json",
        "cot_charts": "cot_charts.json",
        "top_themes": "top_themes.json",
        "what_changed": "what_changed.json",
        "cot_stories": "cot_stories.json",
        "plain_market": "plain_market.json",
    }
    for ccy in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
        file_names[f"series_{ccy}"] = f"series_{ccy}.json"

    for key, value in payload.items():
        filename = file_names[key]
        digest = write_json(root / "data" / "sections" / filename, value)
        sections.append({"key": key, "file": filename, "sha256": digest, "bytes": (root / "data" / "sections" / filename).stat().st_size})

    country_stub = "<!-- FX_PAYLOAD_BOOTSTRAP -->\nconst COUNTRY_CTX=window.__FX_PAYLOAD__.country_ctx;"
    dashboard_stub = "const D=window.__FX_PAYLOAD__.dashboard;"
    app = source[:c_start] + country_stub + source[c_end:d_start] + dashboard_stub + source[d_end:]
    if "const D={" in app or "const COUNTRY_CTX={" in app:
        raise ValueError("Embedded payload remains in frontend")
    if args.refresh_only:
        if not (root / "app.html").is_file() or not (root / "index.html").is_file():
            raise ValueError("--refresh-only requires an already migrated frontend")
    else:
        (root / "app.html").write_text(app, encoding="utf-8", newline="\n")
        (root / "index.html").write_text(LOADER, encoding="utf-8", newline="\n")

    manifest = {
        "schema_version": 1,
        "release": args.source.stem,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "sections": sections,
    }
    write_json(root / "data" / "manifest.json", manifest)

    pair_count = len(dashboard.get("pairs", []))
    if pair_count != 28:
        raise ValueError(f"Expected 28 pairs, got {pair_count}")
    reconstructed = {}
    for section in sections:
        path = root / "data" / "sections" / section["file"]
        reconstructed[section["key"]] = json.loads(path.read_text(encoding="utf-8"))
    if canonical(payload) != canonical(reconstructed):
        raise ValueError("Payload reconstruction failed")
    qa = {
        "status": "PASS",
        "checks": {
            "source_preserved_as_stable_frontend": True,
            "embedded_payload_removed": True,
            "payload_round_trip_exact": True,
            "pair_count": pair_count,
            "loader_runtime_fetches_payload": True,
            "routine_refresh_is_payload_only": args.refresh_only,
            "full_runtime_data_externalized": True,
            "series_split_by_currency": True,
            "rates_runtime_externalized": True,
            "cb_runtime_externalized": True,
            "liquidity_runtime_externalized": True,
            "certified_pair_snapshot_runtime_externalized": True,
        },
        "sizes": {
            "source_html": len(source.encode("utf-8")),
            "stable_frontend_app_html": (root / "app.html").stat().st_size,
            "runtime_loader": (root / "index.html").stat().st_size,
            "payload_total": sum(section["bytes"] for section in sections),
        },
        "rollback": "git revert the architecture commit restores the previous atomic Base64/Gzip loader and payload release.",
    }
    write_json(root / "qa" / "architecture-report.json", qa)
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
