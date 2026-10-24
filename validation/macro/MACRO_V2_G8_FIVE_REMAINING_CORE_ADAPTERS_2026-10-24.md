# Macro V2 — Five remaining G8 Labour/Inflation source adapters

**24 October 2026 · Shared first-web evidence control plane only · No new model scores.**

## Why this change

PR #590 onboarded 13 of 24 currency/pillar research source streams. Existing source-specific Swiss, Japanese, euro-area and NZ web/archival research files were not yet part of the shared dashboard. This change connects **the last five non-Growth slots**, retains explicit original-publisher limitations, and leaves **six Growth source selections** for USD/EUR/GBP/JPY/CHF/CAD.

| G8 slot | Candidate evidence onboarded | First web-release observations | Special controls |
| --- | --- | ---: | --- |
| 🇪🇺 EUR Labour | Eurostat July/August 2026 EA21 unemployment **6.4%, 6.4%** | 2 | Date-only official publications, original Eurostat 104-month archival PASS receipt separately preserved |
| 🇯🇵 JPY Inflation | Japanese all-items CPI July/August **1.9%, 1.9% YoY** | 2 | Japanese official release **08:30 JST**, e-Stat archive `stat_inf_id` and SHA256 pinned; mutable Statistics Bureau index page not treated as frozen |
| 🇨🇭 CHF Inflation | FSO July **0.4%** / September **1.0%** | 2 | Source FSO original assets and embargo **06:30 UTC** anchored; 105-month archival PASS exists separately but is NOT declared onboarded as 105 current-controller rows |
| 🇨🇭 CHF Labour | SECO July/August/September **3.1% SA rounded** | 3 | **Different candidate ID** from exact SNB `CH_UNEMP_RATE`; official SECO rate at one decimal is NOT exact 3.1249882357461% canonical cube value |
| 🇳🇿 NZD Labour | March Q1 **5.3%**, June Q2 **5.6%** | 2 | June 2026 bulletin **re-reports March at 5.4%** in a separate `REVISION_WEB` event, without creating a third first-release economic quarter |

**11 new first-web economic reference observations, plus one later revised quarter**, for **18/24** active research source streams in total. Before this change, source streams covered **58 first-web reports and 68 regular source-stage statements**; the new total is **69 first web events, 80 publisher first/detailed/revised web statements**. These counts are descriptive **across different economic measures**, not model training length for a single series.

### Exact CHF Labour problem: separate reported and transported precision

On **6 October 2026**, [SECO's September press release](https://www.seco.admin.ch/it/newnsb/Cdju9-o8WGML) reports a **seasonally adjusted registered unemployment rate of 3.1%** at one decimal (the unadjusted rate is **3.0%**). The exact canonical SNB transported rate reported by an earlier audit is **3.1249882357461%**. **No source artifact certifies that precise SNB number was distributed on the SECO official press day.**

The candidate is explicitly named `CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL`, so its series ID **does not equal** the canonical `CH_UNEMP_RATE`; the gateway disallows a silent replacement. SECO's August SA unemployed *count* changed **147,970 → 147,886** in the following report, despite published SA rate staying rounded **3.1%**. This is a revision hazard, not a backtest signal or exact-value first-day attestation. The prior detailed [CHF SECO/SNB provenance note](./CHF_LABOUR_SECO_SNB_TEMPORAL_PROVENANCE_2026-10-22.md) retains `WITHHELD_EXACT_PERIOD_EVIDENCE`.

### Archival claim boundaries

Other reports in the repository previously demonstrated a **PASS** strict direct archival materialization for CHF inflation (105 monthly source artifacts), JPY inflation (104), EUR labour (104) and NZD labour (34 quarters), with source hashes. This control-plane adapter **does not ingest or reverify all those original documents or cryptographic archive bytes on this CI run**. It checks the upstream evidence schemas/anchors and imports only clearly pinned individual web release records. Thus a shared summary of 2 source periods for Swiss CPI does not negate the separate prior archival work, and a prior PASS does not automatically supply all revisions/series transformations required for a new canonical Macro V2 score. **No promotional claims** on original release-day bytes, certified full historical revisions or model readiness.

The Japan CPI official web URL is a **mutable publisher index**; source-specific e-Stat original-statistic file identifiers and source hashes remain pinned in the archival receipt. Similarly, the FSO press PDF assets use original official publisher DAM asset IDs with archived SHA claims in the independent prior strict receipt, not fabricated new release timestamps.

### Proper NZD quarterly revision timing

From [Stats NZ March-quarter release](https://www.stats.govt.nz/information-releases/labour-market-statistics-march-2026-quarter/), Q1 unemployment **5.3%** becomes visible at a conservative gate of **7 May 2026 00:00 UTC**. The [June-quarter release](https://www.stats.govt.nz/information-releases/labour-market-statistics-june-2026-quarter/) first reports Q2 **5.6%** and the retrospectively revised Q1 value **5.4%**, both conservatively visible at **6 August 00:00 UTC**. The latter is a `REVISION_WEB` record **for 2026Q1**, not a third economic quarter. Publication days are confirmed but true intraday release UTC is not independently certified for this adapter.

### Generic controller extension

The shared `normalize` now allows `REVISION_WEB` as a stage in addition to `FIRST_WEB` and `DETAILED_WEB`, and enforces:
- one first event per actual economic reference period, even for true quarterly `YYYYQn` periods;
- strictly ordered stages within a reference period (no revised record dated before its source first publication);
- original publisher allowlists for Swiss FSO and SECO;
- separate counts for **documented first releases** versus **revised historical reference periods**;
- no source promotion even when canonical series ID matches;
- conservative next-UTC-day cutoffs only for official release-date-only publishers; true e-Stat/FSO clock offsets are retained from archived metadata.

## G8 footprint after this milestone

| Scope | Count |
| --- | ---: |
| All observed currency × pillar slots inventoried | 24 |
| Research source candidate adapters | **18** |
| Labour + Inflation slots with bounded official-source attestations | **16/16** |
| Growth source candidate streams | **2/8** (AUD, NZD) |
| Growth slots without a canonical series selected | **8/8** |
| Missing research adapters | **6** (USD, EUR, GBP, JPY, CHF, CAD Growth) |
| Fully certified new Macro V2 historical PIT scores | **0** |

**Next step:** select Growth metrics by exact economic semantics (GDP QoQ/YoY vs annualized quarter, GDP vs industrial output, reference-period end vs publication date), then attach *historical first release/source archives* using the same generic adapter. The remaining six missing adapters must not be reported as six missing current macro observations.

### Run tests / reproducible CI

```bash
python -m unittest validation.macro.test_v2_pit_g8_control_plane_v1 -v
python -m unittest validation.macro.test_v2_pit_g8_latest_web_adapters_v1 -v
python -m unittest validation.macro.test_v2_pit_g8_remaining_core_adapters_v1 -v
python -m validation.macro.v2_pit_g8_control_plane_v1 \
  --asof 2026-10-24T00:00:00Z \
  --json-out /tmp/macro-v2-shadow/g8-18-source-control-plane.json \
  --markdown-out /tmp/macro-v2-shadow/g8-18-source-control-plane.md
```

No new cron/automation. No D.json, Macro score, backtest, website, 28-pair state, live_data, data-source registry or scheduler changed. The only outputs are read-only **research receipts under /tmp**.
