"""Research-only cross-quarter GDP vintage validation; not a source certification."""
from datetime import date, datetime, timedelta, timezone
import calendar
import math
from urllib.parse import urlsplit

CURRENCIES = set("USD EUR GBP JPY CHF CAD AUD NZD".split())
# Independently pinned government statistical publisher domains.
# The per-row host field alone is not sufficient issuer authentication.
PUBLISHER_HOSTS = {
    "USD": {"www.bea.gov", "bea.gov"},
    "EUR": {"ec.europa.eu"},
    "GBP": {"www.ons.gov.uk"},
    "JPY": {"www.esri.cao.go.jp", "www5.cao.go.jp"},
    "CHF": {"www.seco.admin.ch", "www.pfp.admin.ch", "www.efd.admin.ch"},
    "CAD": {"www150.statcan.gc.ca"},
    "AUD": {"www.abs.gov.au"},
    "NZD": {"www.stats.govt.nz"},
}


def visible_at(day):
    d = date.fromisoformat(day)
    return datetime.combine(d + timedelta(days=1), datetime.min.time(), timezone.utc)

def validate(rows):
    """Rows must be verified from dated publisher statements before entering."""
    if not isinstance(rows, list):
        raise ValueError("expected rows list")
    seen, groups, result = set(), {}, []
    for row in rows:
        c, q, day, stage = (row.get(k) for k in (
            "currency", "reference_quarter", "publisher_release_day", "stage_order"))
        if c not in CURRENCIES or not isinstance(q, str) or len(q) != 6 or not q[:4].isdigit() or q[4:] not in ("Q1", "Q2", "Q3", "Q4"):
            raise ValueError("invalid currency or quarter")
        if type(stage) is not int or stage < 0:
            raise ValueError("invalid revision sequence")
        release = visible_at(day)
        end_month = int(q[-1]) * 3
        quarter_end = date(int(q[:4]), end_month, calendar.monthrange(int(q[:4]), end_month)[1])
        if date.fromisoformat(day) <= quarter_end:
            raise ValueError("publication precedes end of reference quarter")
        value, unit = row.get("reported_value"), row.get("reported_unit")
        if type(value) not in (int, float) or not math.isfinite(value) or not (-100 < value < 1000):
            raise ValueError("invalid GDP reading")
        if not isinstance(unit, str) or not unit.startswith("PERCENT_"):
            raise ValueError("explicit original units required")
        url = row.get("source_url")
        if not isinstance(url, str):
            raise ValueError("source required")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or (parsed.hostname != row.get("verified_publisher_host") or
            parsed.hostname not in PUBLISHER_HOSTS[c]):
            raise ValueError("publisher host must be separately pinned")
        if row.get("eligible_for_macro_scoring") is not False or row.get("PIT_training_vintage_certified") is not False:
            raise ValueError("unapproved historical promotion")
        key = (c, q, stage)
        if key in seen:
            raise ValueError("duplicate release stage")
        seen.add(key)
        groups.setdefault((c, q), []).append((stage, release, unit))
        result.append({**row, "conservative_available_from_utc": release.isoformat()})
    for stages in groups.values():
        stages.sort()
        if [s[0] for s in stages] != list(range(len(stages))):
            raise ValueError("missing first release or revision")
        if len({s[2] for s in stages}) != 1:
            raise ValueError("incomparable revision definitions")
        if any(a[1] >= b[1] for a, b in zip(stages, stages[1:])):
            raise ValueError("revision cannot arrive before earlier release")
    return result

def snapshot(rows, cutoff_utc):
    cutoff = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
    if cutoff.utcoffset() != timedelta(0):
        raise ValueError("UTC cutoff required")
    selected = {}
    for r in validate(rows):
        if datetime.fromisoformat(r["conservative_available_from_utc"]) <= cutoff:
            key = (r["currency"], r["reference_quarter"])
            if key not in selected or r["stage_order"] > selected[key]["stage_order"]:
                selected[key] = r
    return {
        "visible_vintages": {f"{c}:{q}": selected[c, q] for c, q in sorted(selected)},
        "research_only": True, "safe_to_update_live_macro_D": False,
        "safe_to_use_for_beta": False, "safe_to_use_for_forward": False,
        "safe_to_change_28_pairs": False,
    }
