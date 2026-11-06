# Global Macro FX Quant — operational target (6 November 2026)

## One canonical website: FX Quant V2

**Approved public URL:** https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/

**Approved source:** `site/fx-quant-v2/` with 12 pages. **Public validation:** `validation/qa_fx_quant_v2_browser.cjs`; scheduled QA `.github/workflows/fx-quant-v2-browser-daily-qa.yml`.

### Preserve

1. Do not restyle V2 without the owner's explicit request. Preserve its page structure and the 28-pair FX engine and Core.
2. Keep distinct official and estimated OIS/futures/proxy/historical observations, original as-of, contract and source dates; no proxy promotion or invented policy repricing.
3. Preserve `live_data/`, `validation/`, historical `payload/`, `dashboard/`, `site/website-v1/` and `site/control-room-preview/` until dependency analysis and staged deactivation verify they are unused. Legacy is **not** the default interface but may still supply shared feeds or audit contracts.
4. Publication `main` -> `gh-pages` must be checked for the requested path; do not confuse a successful workflow with fresh underlying source observations.
5. For V2 changes, check `publish-fx-quant-v2.yml`, `fx-quant-v2-browser-daily-qa.yml` and `fxv2-morning-public-proof.yml`. Quote exact outcomes and remaining gaps. Do not change FX signals in UI-only PRs.
6. Do not delete or disable a GitHub workflow without checking references by workflow name (workflow_run triggers), producer/consumer data paths, schedules, secrets, publication, tests and rollback.

### Legacy entrances

`index.html` and `site/website-v1/index.html` navigate to V2; they keep their legacy fallback payload for compatibility. Direct URLs to old dashboards may remain accessible but are no longer the reference for new UI work.

For the staged cleanup boundary, see `MAINTENANCE_V2.md`.
