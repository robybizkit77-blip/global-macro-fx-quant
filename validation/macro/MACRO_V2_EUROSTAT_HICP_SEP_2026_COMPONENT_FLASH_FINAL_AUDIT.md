# Macro V2 — Eurostat HICP September 2026: flash vs detailed component audit

**24 October 2026 — research only; no live scoring.**

## Official pages and economic finding

- [Eurostat flash, 2 October 2026](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-02102026-ap)
- [Eurostat detailed, 16 October 2026](https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap)

September 2026 **EA21** all-items HICP annual rate remained **3.8%** between two official publications. Within the **same September reference month**, the published **energy** annual rate rose from **18.8% to 18.9% (+0.1 pp)**, while **food, alcohol & tobacco** fell from **1.4% to 1.3% (-0.1 pp)**. Headline, core (excluding energy, food, alcohol and tobacco) 2.5%, services 3.2%, and non-energy industrial goods 1.1% were unchanged at the displayed 0.1-pp precision.

### Comparison scope

The research fixture pins 10 **comparable annual-rate categories**, not ten independent releases; exactly two publication events and only one reference month are involved. Component rate changes are **not automatically additive**, because headline is a separately aggregated HICP and its constituent changes reflect weights, precision/rounding and source methodology. Do not infer an unreported headline revision or causal market effect.

The detailed page alone also reports **contributions to the headline annual inflation rate**, by component: energy **+1.71 pp**, services **+1.52 pp**, non-energy industrial goods **+0.29 pp**, and food, alcohol and tobacco **+0.25 pp**. These contributions are *not* the annual-rate observations and cannot be used as flash-to-detailed differences: the flash press release has no matching contributions in this restricted comparison.

## Temporal controls

- Eurostat source pages independently establish the *dates* (2 and 16 October), but do **not independently certify an intraday UTC release timestamp** in this dossier.
- Conservative shadow replay reveals flash from **3 October 2026 00:00 UTC** and detailed from **17 October 2026 00:00 UTC**, one UTC day after each stated publication date. This artificial gate is **not the actual market release time**.
- A replay on 16 October 23:59:59 UTC must still use flash values and must **not** reveal final contributions or component differences.
- The date-only gate **cannot be used to study same-day EUR/USD or OIS reactions**.

## PIT/provenance and model limitations

- Official period-specific HTML pages were reviewed on 24 October, but no independent original **publication-day preserved immutable bytes** have been certified. Published pages can change.
- The data are reported for the evolving composition of the euro area: **EA20 through December 2025, EA21 from January 2026**. A much longer PIT historical chain requires geography-aware selection and release-vintage source preservation.
- This is one month with two release stages, **not** a 25-month training window, a complete revision matrix, or a model backtest.
- No real-time score, no FX pair ranking, no publication to `D.json`, `live_data/`, `site/`, `payload/`, `dashboard/`. `safe_to_publish_new_D=false`, `safe_to_update_pair_theses=false`.

## Validation

```bash
python -m unittest validation.macro.test_v2_eurostat_hicp_component_event_replay_v1 -v
python -m validation.macro.v2_eurostat_hicp_component_event_replay_v1 --asof 2026-10-16T23:59:59Z --out /tmp/macro-v2-shadow/eur-hicp-before-detailed-safe-gate.json
python -m validation.macro.v2_eurostat_hicp_component_event_replay_v1 --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/eur-hicp-sep-components-audit.json
```

The CI runner creates receipts only under `/tmp` and enforces that no production or website files changed.
