from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "validation/ui/DASHBOARD_UI_OWNERSHIP_REGISTRY_V1_2026-10-15.json"
EXPECTED = [
    "overview","wow","themes","calendar","news","risk","currencies","pairs",
    "macro","inflationlabour","ratesdesk","cbdesk","liquiditydesk","cot","method","forwarddesk"
]

def must(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)

def main() -> None:
    d = json.loads(REG.read_text())
    must(d["schema"] == "GMFQ_DASHBOARD_UI_OWNERSHIP_REGISTRY_V1", "schema")
    must(d["policy"]["one_visible_owner_per_view"] is True, "single-owner policy")
    must(d["policy"]["desktop_mobile_owner_parity"] is True, "viewport parity")
    views = d["views"]
    must(list(views.keys()) == EXPECTED, f"view order/coverage drift: {list(views.keys())}")
    must(len(views) == 16, "must cover 16 views")

    index = (ROOT / "index.html").read_text()
    cal = (ROOT / "dashboard/calendar-news-operational-v1.js").read_text()
    themes = (ROOT / "dashboard/top-themes-operational-v1.js").read_text()
    wow = (ROOT / "dashboard/what-changed-operational-v1.js").read_text()
    risk = (ROOT / "dashboard/risk-operational-v1.js").read_text()
    pairs = (ROOT / "dashboard/pairs-operational-v1.js").read_text()
    currencies = (ROOT / "dashboard/currencies-operational-v1.js").read_text()
    overview_asof = (ROOT / "dashboard/overview-asof-operational-v1.js").read_text()
    ois = (ROOT / "dashboard/ois-operational-monitor-v1.js").read_text()
    cbdesk = (ROOT / "dashboard/cbdesk-operational-v1.js").read_text()
    liquidity = (ROOT / "dashboard/liquiditydesk-operational-v1.js").read_text()
    cotdesk = (ROOT / "dashboard/cotdesk-operational-v1.js").read_text()
    forward = (ROOT / "dashboard/forwarddesk-operational-v1.js").read_text()
    freshness = (ROOT / "dashboard/editorial-freshness-guard-v1.js").read_text()

    for src in [
        "dashboard/calendar-news-operational-v1.js",
        "dashboard/top-themes-operational-v1.js",
        "dashboard/what-changed-operational-v1.js",
        "dashboard/risk-operational-v1.js",
        "dashboard/cotdesk-operational-v1.js",
        "dashboard/pairs-operational-v1.js",
        "dashboard/currencies-operational-v1.js",
        "dashboard/overview-asof-operational-v1.js",
        "dashboard/ois-operational-monitor-v1.js",
        "dashboard/cbdesk-operational-v1.js",
        "dashboard/liquiditydesk-operational-v1.js",
        "dashboard/forwarddesk-operational-v1.js",
        "dashboard/editorial-freshness-guard-v1.js",
    ]:
        must(src in index, f"index missing dynamic module {src}")

    must("GMFQ_OVERVIEW_ASOF_OPERATIONAL_V1" in overview_asof, "overview as-of schema missing")
    must("GMFQ_ECB_PRICE_AUDIT" in overview_asof, "overview as-of must read current price authority")
    must("SNB_LAST_VALIDATED" in overview_asof, "overview must label CHF source state truthfully")
    must("core_effect:'NONE'" in overview_asof, "overview as-of must declare zero core effect")

    must("GMFQ_CURRENCIES_OPERATIONAL_UI_V1" in currencies, "currencies operational schema missing")
    must("deriveCurrencyState" in currencies, "currencies must read canonical runtime state")
    must("renderCurrency" in currencies, "currencies must retain canonical renderer")
    must("currencyUiIntegrity" in currencies, "currencies must enforce existing integrity guard")
    must("core_effect:'NONE'" in currencies, "currencies must declare zero core effect")
    must("CURRENCIES_OPERATIONAL_BOOT_TIMEOUT" in currencies, "currencies must fail closed on boot timeout")

    must('data-gmfq-operational="wow"' in wow, "what changed owner marker missing")
    must("NEWS_PULSE_OPERATIONAL.json" in wow, "what changed missing operational source")
    must("core_effect:'NONE'" in wow, "what changed must declare zero core effect")
    must("GMFQ_WHAT_CHANGED_OPERATIONAL_UI_V1" in wow, "what changed operational schema missing")

    must('data-gmfq-operational="risk"' in risk, "risk owner marker missing")
    for source in ["live_data/sections/D.json","ESTIMATED_RESIDUAL_GAPS.json"]:
        must(source in risk, f"risk missing operational source {source}")
    must("GMFQ_RISK_OPERATIONAL_UI_V1" in risk, "risk operational schema missing")
    must("brent_official_status:'WITHHELD'" in risk, "Brent official status must remain WITHHELD")
    must("core_effect:'NONE'" in risk, "risk must declare zero core effect")

    must('data-gmfq-operational="themes"' in themes, "themes owner marker missing")
    for source in ["NEWS_PULSE_OPERATIONAL.json","MACRO_THERMOMETER_DATA.json","OIS_OPERATIONAL_VIEW.json"]:
        must(source in themes, f"themes missing operational source {source}")
    must("core_effect:'NONE'" in themes, "themes must declare zero core effect")
    must("GMFQ_TOP_THEMES_OPERATIONAL_UI_V1" in themes, "themes operational schema missing")

    must('data-gmfq-operational="pairs"' in pairs, "pairs owner marker missing")
    must("derivePairDecisionFrame" in pairs, "pairs must read canonical runtime engine")
    must("D.prices" in pairs, "pairs must derive price from current runtime prices")
    must("GMFQ_PAIRS_OPERATIONAL_UI_V1" in pairs, "pairs operational schema missing")
    must("core_effect:'NONE'" in pairs, "pairs must declare zero core effect")
    must("PAIR_COVERAGE_INCOMPLETE" in pairs, "pairs must fail closed on incomplete coverage")

    must("GMFQ_CBDESK_OPERATIONAL_UI_V1" in cbdesk, "CB Desk operational schema missing")
    must("OIS_OPERATIONAL_VIEW.json" in cbdesk, "CB Desk must read operational OIS authority")
    must("corePolicyIntegrity" in cbdesk, "CB Desk must protect canonical policy integrity")
    must("rate2YSeries" in cbdesk, "CB Desk must keep 2Y confirmation separate")
    must("core_effect:'NONE'" in cbdesk, "CB Desk must declare zero core effect")
    must("NON OIS" in cbdesk, "CB Desk must label NZD proxy as NON OIS")
    must("GREEN_OFFICIAL" in cbdesk and "GREEN_ESTIMATED" in cbdesk, "CB Desk must preserve official/estimated distinction")

    must("GMFQ_LIQUIDITYDESK_OPERATIONAL_UI_V1" in liquidity, "Liquidity Desk operational schema missing")
    must("NATIVE_LIQ_DATA" in liquidity, "Liquidity Desk must read canonical native liquidity data")
    must("liquidityStructuralChangeCandidate" in liquidity, "Liquidity Desk must use canonical structural candidate")
    must("live_freshness_integrity" in liquidity, "Liquidity Desk must enforce source-native freshness integrity")
    must("overlay_isolation_integrity" in liquidity, "Liquidity Desk must enforce overlay isolation")
    must("SOURCE_NATIVE_CADENCE_HOLD_LAST_VALID_COMPONENT" in liquidity, "Liquidity freshness policy missing")
    must("core_effect:'NONE'" in liquidity, "Liquidity Desk must declare zero core effect")

    must("GMFQ_COTDESK_OPERATIONAL_UI_V1" in cotdesk, "COT Desk operational schema missing")
    must("V250_COT_CHART_DATA" in cotdesk and "V247_COT_STORIES" in cotdesk, "COT Desk must use canonical V250/V247 authority")
    must("overlayIsolationIntegrity" in cotdesk, "COT Desk must enforce overlay isolation")
    must("COT_OVERLAY_CHANGED_STRUCTURAL_OUTPUT" in cotdesk, "COT Desk must fail closed on structural drift")
    must("price_confirmation_policy:'WITHHELD_UNLESS_SEPARATELY_VALIDATED'" in cotdesk, "COT price confirmation policy missing")
    must("preserved_legacy_fields:['open_interest','oi_series']" in cotdesk, "COT must preserve non-reconstructible legacy OI fields")
    must("core_effect:'NONE'" in cotdesk, "COT Desk must declare zero core effect")

    must("GMFQ_FORWARDDESK_OPERATIONAL_UI_V1" in forward, "Forward Desk operational schema missing")
    must("forwardValidationSummary" in forward, "Forward Desk must read validation summary")
    must("forwardLedgerIntegrity" in forward, "Forward Desk must enforce ledger integrity")
    must("gmfqForwardPathRiskStats" in forward and "gmfqForwardSnapshotBasketSeries" in forward and "gmfqForwardPairedOverlayStats" in forward, "Forward helper chain missing")
    must("OBSERVATIONAL_FORWARD_VALIDATION_ONLY" in forward, "Forward Desk scope must remain observational")
    must("core_effect:'NONE'" in forward, "Forward Desk must declare zero core effect")

    must("cal.innerHTML=calendarHtml(c)" in cal, "calendar is not explicit dynamic owner")
    must("news.innerHTML=newsHtml(n)" in cal, "news is not explicit dynamic owner")
    must('data-gmfq-operational="calendar"' in cal, "calendar owner marker missing")
    must('data-gmfq-operational="news"' in cal, "news owner marker missing")
    must("GMFQ_OIS_OPERATIONAL_UI_V1" in ois, "OIS owner marker missing")
    must("v401OisBlock" in ois, "OIS mount missing")

    must("GMFQ_EDITORIAL_FRESHNESS_GUARD_V3_OPERATIONAL_AUTHORITY" in freshness, "freshness V3 schema missing")
    for source in ["CALENDAR_OPERATIONAL_VIEW.json","NEWS_PULSE_OPERATIONAL.json","live_data/sections/D.json","ESTIMATED_RESIDUAL_GAPS.json"]:
        must(source in freshness, f"freshness operational source missing: {source}")
    for marker in [
        "CALENDAR_OPERATIONAL_VIEW.last_checked_at_utc",
        "NEWS_PULSE_OPERATIONAL.content_as_of",
        "OLDEST_REQUIRED(D.risk.VIX.last_date,D.risk.WTI.last_date,ESTIMATED_RESIDUAL_GAPS.BRENT.proxy_as_of)"
    ]:
        must(marker in freshness, f"freshness authority marker missing: {marker}")
    must("riskLaneCoverage" in freshness, "risk freshness must audit every required lane")
    must("entries.sort((a,b)=>a.date-b.date)" in freshness, "risk freshness must use oldest date")
    must("if(missing.length)return {date:null" in freshness, "risk missing lane must fail closed")
    must("legacy_authority:'NONE'" in freshness, "legacy freshness authority must be NONE")
    must("AUXILIARY_FEED_FRESHNESS" not in freshness, "freshness guard must not read legacy AUXILIARY_FEED_FRESHNESS")
    must("REAL_CALENDAR" not in freshness, "freshness guard must not read legacy REAL_CALENDAR")
    must("NEWS_PULSE_STRUCT" not in freshness, "freshness guard must not read legacy NEWS_PULSE_STRUCT")

    dynamic = ("wow","themes","calendar","news","risk","pairs")
    for view in dynamic:
        must(views[view]["owner_type"] == "DYNAMIC_REPLACE", f"{view} owner type")
        must(views[view]["legacy_payload_state"] == "SOURCE_PRESENT_NON_OWNER", f"{view} legacy state")
    hybrid = ("overview","currencies","macro","inflationlabour","ratesdesk","cbdesk","liquiditydesk","cot","forwarddesk")
    for view in hybrid:
        must(views[view]["owner_type"] == "HYBRID", f"{view} owner type")
    for view, spec in views.items():
        if spec["owner_type"] == "PAYLOAD": must(spec.get("migration_state") == "KEEP", f"payload owner migration state {view}")

    print(json.dumps({
        "status":"PASS","schema":d["schema"],"views":len(views),
        "dynamic_replace":list(dynamic),"hybrid":list(hybrid),
        "freshness_authority":{
            "overview_asof":"GMFQ_ECB_PRICE_AUDIT.as_of; CHF rates keeps SNB last validated snapshot",
            "currencies":"deriveCurrencyState + canonical renderCurrency + current runtime layers",
            "cbdesk":"NATIVE_CB_DATA policy + OIS_OPERATIONAL_VIEW pricing + rate2YSeries confirmation",
            "liquiditydesk":"NATIVE_LIQ_DATA + source-native cadence freshness + structural candidate; overlay only",
            "cot":"V250_COT_CHART_DATA + V247_COT_STORIES; D.cot certified context fields synchronized; overlay only",
            "forwarddesk":"forwardValidationSummary + forwardLedgerIntegrity + helper chain; observational only",
            "wow":"NEWS_PULSE_OPERATIONAL.content_as_of",
            "themes":"NEWS_PULSE_OPERATIONAL.content_as_of",
            "calendar":"CALENDAR_OPERATIONAL_VIEW.last_checked_at_utc",
            "news":"NEWS_PULSE_OPERATIONAL.content_as_of",
            "risk":"OLDEST_REQUIRED_RISK_DATE",
            "pairs":"D.prices latest official ECB fixing + derivePairDecisionFrame runtime",
            "legacy":"NONE"
        },
        "legacy_payload_policy":"PRESENT_BUT_NON_OWNER_UNTIL_MIGRATED"
    }, sort_keys=True))

if __name__ == "__main__":
    main()
