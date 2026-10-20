#!/usr/bin/env python3
"""Read-only SIX CHF retrospective SARON source/right-classification audit.

Never ingest prices, download SIX data, issue trading signals, or promote CHF OIS.
This is a contractual/source SEMANTIC guard, not a formal legal opinion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "validation/cb_pricing/CHF_SIX_SARON_HISTORICAL_CONTEXT_SOURCE_CONTRACT_V1_2026-10-20.json"
SYMBOLS = {
    "SARON": ("CH0049613687", "ON", "OVERNIGHT_PAST_FIXING", "REALIZED"),
    "SAR3MC": ("CH0477123902", "3M", "SARON_COMPOUND_IN_ARREARS", "BACKWARD_LOOKING"),
    "SAR6MC": ("CH0477123910", "6M", "SARON_COMPOUND_IN_ARREARS", "BACKWARD_LOOKING"),
    "SAR12MC": ("CH0477123936", "12M", "SARON_COMPOUND_IN_ARREARS", "BACKWARD_LOOKING"),
}
BLOCKED_RIGHTS = {
    "internal_derived_data_right": "WITHHELD_PENDING_APPLICATION_OF_SIX_FAQ_Q11_TO_PERSONAL_RESEARCH",
    "external_derived_data_right": "WITHHELD_LICENSE_OR_WRITTEN_CLEARANCE_REQUIRED",
    "automated_download_right": "WITHHELD_NOT_ESTABLISHED",
}
FALSE_USAGE = (
    "copyrighted_bulk_data_download_proven",
    "official_numeric_snapshot_attested",
    "public_dashboard_permission_certified",
)
TRUE_DEPLOYMENT = (
    "sidecar_only", "read_only", "no_numeric_rates_in_receipt",
    "no_ois_curve_substitution", "no_policy_repricing_signal",
    "no_automatic_official_promotion", "no_new_live_data_snapshot",
    "no_dashboard_change", "no_new_scheduled_workflow",
    "no_new_chatgpt_automation",
)
ALLOWED_KEYS = frozenset({
    "schema", "reviewed_as_of", "source", "currency", "usage",
    "instruments", "deployment", "verdict", "note",
})


def require(ok, reason):
    if not ok:
        raise ValueError("CHF_SIX_CONTEXT_FAIL_CLOSED: " + reason)


def valid_six_url(url):
    try:
        x = urlsplit(url)
    except ValueError:
        return False
    return (x.scheme == "https" and x.hostname == "www.six-group.com"
            and x.username is None and x.password is None
            and not x.query and not x.fragment)


def audit(contract: dict) -> dict:
    require(isinstance(contract, dict) and set(contract) == ALLOWED_KEYS,
            "unexpected source contract shape or quote payload")
    require(contract["schema"] == "GMFQ_CHF_SIX_SARON_CONTEXT_CONTRACT_V1",
            "unexpected source schema")
    require(contract["reviewed_as_of"] == "2026-10-20" and
            contract["currency"] == "CHF", "unapproved jurisdiction/date")
    src = contract["source"]
    require(isinstance(src, dict) and
            set(src) == {"authority", "benchmark", "official_page",
                         "licensing_faq", "licensing_faq_revision"},
            "source identity or URL payload drift")
    require(src["authority"] == "SIX Swiss Exchange / SIX Index AG"
            and src["benchmark"] == "Swiss Reference Rates"
            and src["licensing_faq_revision"] == "2026-07-01",
            "source/2026 licensing revision mismatch")
    require(valid_six_url(src["official_page"]) and
            src["official_page"].endswith("/indices/switzerland/saron.html")
            and valid_six_url(src["licensing_faq"]) and
            src["licensing_faq"].endswith("/six-saron-faq-en.pdf"),
            "source must be public SIX issuer/FAQ only")
    entries = contract["instruments"]
    require(isinstance(entries, dict) and set(entries) == set(SYMBOLS),
            "benchmark coverage or identifier unknown")
    for symbol, expected in SYMBOLS.items():
        row = entries[symbol]
        isin, tenor, typ, direction = expected
        require(isinstance(row, dict) and
                set(row) == {"symbol", "isin", "tenor", "type", "direction",
                             "forward_looking"}, symbol+": unexpected numeric or trading field")
        require((row["symbol"], row["isin"], row["tenor"], row["type"],
                 row["direction"]) == (symbol, isin, tenor, typ, direction),
                symbol+": source identity or retrospection drift")
        require(row["forward_looking"] is False, symbol+": retrospective data promoted forward")
    usage = contract["usage"]
    require(isinstance(usage, dict) and
            set(usage) == {"context_class", "release_latency", "raw_historical_display_right"}
            | set(BLOCKED_RIGHTS) | set(FALSE_USAGE),
            "usage rights must be explicit and not contain hidden numeric values")
    require(usage["context_class"] == "HISTORICAL_REALIZED_MONEY_MARKET_ONLY",
            "realized benchmark mislabeled as expected policy path")
    require(usage["release_latency"] ==
            "AT_LEAST_ONE_CHF_BUSINESS_DAY_FOR_COMPOUND_HISTORY",
            "delayed compound benchmark must not be treated as live")
    require(usage["raw_historical_display_right"] ==
            "CONDITIONAL_DELAYED_REDISTRIBUTION_PER_SIX_FAQ_Q9",
            "historical display is conditional, not a blanket data product licence")
    for key, state in BLOCKED_RIGHTS.items():
        require(usage[key] == state, key+": licence clearance missing")
    for key in FALSE_USAGE:
        require(usage[key] is False, key+": rights or source data not established")
    deployment = contract["deployment"]
    require(isinstance(deployment, dict) and set(deployment) == set(TRUE_DEPLOYMENT),
            "unexpected deployment capability")
    for key in TRUE_DEPLOYMENT:
        require(deployment[key] is True, key+": forbidden promotion or schedule")
    require(contract["verdict"] ==
            "DOCUMENTED_SOURCE_WITHHELD_PENDING_NUMERIC_ACCESS_AND_LICENSE_CLEARANCE",
            "licence/source assurance must remain withheld")
    require(isinstance(contract["note"], str) and len(contract["note"]) >= 75,
            "research limitations must be recorded")
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True,
                                  separators=(",", ":")).encode()).hexdigest()
    return {
        "schema": "GMFQ_CHF_SIX_SARON_CONTEXT_AUDIT_V1",
        "reviewed_as_of": "2026-10-20",
        "currency": "CHF",
        "status": "PASS_SOURCE_SEMANTICS__WITHHELD_LICENSE_AND_FETCH",
        "authoritative_symbols": sorted(SYMBOLS),
        "retrospective_only": True,
        "forward_policy_curve_available": False,
        "ois_forward_level_available": False,
        "policy_repricing_1d_1w_available": False,
        "official_chf_ois_promotion_eligible": False,
        "published_market_rates": None,
        "derived_data_rights_certified": False,
        "automated_ingestion_authorized": False,
        "numeric_source_pit_snapshot_certified": False,
        "safe_to_update_live_ois": False,
        "safe_to_change_control_room": False,
        "writes_live_data": False,
        "source_contract_fingerprint_sha256": digest,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, default=FILE)
    p.add_argument("--out", type=Path,
                   help="Optional receipt path outside versioned live_data")
    a = p.parse_args()
    receipt = audit(json.loads(a.contract.read_text(encoding="utf-8")))
    if a.out:
        require(a.out.resolve() != a.contract.resolve() and
                ROOT / "live_data" not in a.out.resolve().parents,
                "never overwrite source or production data")
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        k: receipt[k] for k in ("currency", "status", "authoritative_symbols",
                               "official_chf_ois_promotion_eligible",
                               "derived_data_rights_certified",
                               "writes_live_data")
    }, sort_keys=True))


if __name__ == "__main__":
    main()
