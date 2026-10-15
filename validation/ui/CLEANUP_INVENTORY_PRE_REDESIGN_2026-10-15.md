# GMFQ — Cleanup inventory pre-redesign (2026-10-15)

Status: **SAFE CLEANUP PLANNING — NO PHYSICAL LEGACY PAYLOAD DELETION**

This inventory is created after `OPERATIONAL_OWNERSHIP_COMPLETE_PRE_REDESIGN` was reached. Its purpose is to separate production/runtime requirements from migration-only diagnostics before the visual/language redesign.

## A. Keep — production/runtime essential

- `index.html` and `payload/part-00.txt` … `payload/part-15.txt`
- `dashboard/*-operational-v1.js` modules currently registered as DYNAMIC/HYBRID owners
- `live_data/sections/*` canonical operational sources
- `validation/ui/DASHBOARD_UI_OWNERSHIP_REGISTRY_V1_2026-10-15.json`
- `validation/ui/check_dashboard_ui_ownership_v1.py`
- publication, freshness, final visual QA, per-surface operational browser gates
- persistent Macro / Rates / CB pricing / Price / COT / Liquidity / risk-market refresh workflows

Reason: these files actively enforce or publish the certified dashboard state.

## B. Keep until legacy physical-removal gate becomes GREEN

- `validation/ui/audit_calendar_news_legacy_dependencies_v2.py`
- `validation/ui/check_legacy_runtime_quarantine_v1.py`
- `validation/ui/inventory_runtime_legacy_script_blocks_v1.py`
- corresponding quarantine / legacy dependency workflows
- quarantined September-era legacy script source retained inside the immutable payload

Reason: V2 is runtime-aware and is the authority that decides whether physical removal can be planned. Source quarantine is intentionally safer than deletion until compatibility consumers are gone.

## C. Superseded, but NOT deletable yet

### `validation/ui/audit_calendar_news_legacy_dependencies_v1.py`

State: **SUPERSEDED_BY_V2 / STILL_REFERENCED**

- Superseded by `audit_calendar_news_legacy_dependencies_v2.py`, which models the actual runtime-equivalent payload after quarantine.
- Still referenced by `.github/workflows/dashboard-ui-ownership-v1.yml`.
- Safe removal sequence:
  1. switch Dashboard UI Ownership to V2;
  2. certify Ownership desktop/mobile GREEN;
  3. confirm the dedicated V2 audit remains GREEN;
  4. only then delete V1.

Do not delete V1 before step 1.

## D. Keep through redesign, review after visual freeze

- `validation/ui/audit_payload_owner_currentness_v1.js` and its workflow
- current ownership/currentness evidence tooling
- Final Visual QA and individual operational UI gates

Reason: these are highly useful during the upcoming premium redesign to prove that presentation changes do not silently reconnect stale payload owners or stale dates. Review them for consolidation only after the redesigned UI is frozen and has a stable regression suite.

## E. Historical / PIT / source-contract workflows

Default classification: **DO NOT DELETE DURING UI CLEANUP**.

Examples include strict PIT materializers, source contracts, rates temporal PIT jobs, and provider readiness probes. They belong to data provenance/backtest certification rather than UI ownership. They may look old or numerous but can still be required to reproduce certified history. Any later removal requires a separate data-pipeline inventory proving that a newer contract fully supersedes the old one.

## F. Physical legacy payload deletion policy

Current rule remains: **quarantine first; physical deletion only after the V2 runtime-equivalent audit reports that no remaining compatibility consumer requires the legacy blocks.**

The redesign must not be used as an excuse to remove source history or compatibility code whose replacement has not been independently certified.

## Next cleanup action

Migrate `.github/workflows/dashboard-ui-ownership-v1.yml` from `audit_calendar_news_legacy_dependencies_v1.py` to V2 in a small dedicated PR. If all ownership/quarantine/visual gates are GREEN, remove the V1 audit file in that same cleanup lane or immediately after it.
