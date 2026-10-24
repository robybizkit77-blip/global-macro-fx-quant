# Macro V2 — Shared G8 PIT evidence control plane (all 24 currency × pillar slots)

**24 October 2026 · First common audit/replay infrastructure · research only.**

## What changes versus month-by-month EUR work

This is the common **audit interface** for all eight G8 FX currencies and all three pillars (Growth, Labour, Inflation). It reuses the canonical **24-slot source-readiness inventory**, the registered **16 Labour/Inflation series**, and the previously audited source-specific release pages instead of reimplementing a separate source/chronology/safety engine for every country.

**It is not a background data collector or a finished G8 historical PIT score model.** New source adapters must still be built for the missing slots, original source publication bytes acquired/archived, transformations reconciled and formal scoring review completed. The point is that **those adapters now produce a uniform contract** and the same generic 24-slot validation, chronological replay, unit/frequency checks and fail-closed review output.

### Four existing audited source streams onboarded first

| Slot | Candidate source contract | Source-specific evidence now replayable | Exact canonical identity? | Full PIT history certified? |
| --- | --- | --- | --- | --- |
| 🇪🇺 EUR · Inflation | Eurostat HICP YoY research history | **10 months** Dec 2025–Sep 2026 · **20 flash/detailed stage events** | Not yet: research ID differs from registry ID | **No** |
| 🇦🇺 AUD · Inflation | ABS complete **monthly** CPI headline YoY | **11 distinct monthly first-publisher web events** · Oct 2025–Aug 2026 | **No**: registry CPI is *quarterly*; new monthly candidate is not a drop-in replacement | **No** |
| 🇺🇸 USD · Labour | BLS `LNS14000000` official Employment Situation archives | **25 dated first-web-report months**, Sep 2023–Sep 2025 | **No**: registry is `UNRATE`; mapping requires evidence review | **No** |
| 🇬🇧 GBP · Labour | ONS `MGSX` unemployment/LFS 3-month windows | **3 period-specific official web statements**, canonical *end-of-window* months Jun–Aug 2026 | Exact ID/frequency, **but LFS rolling-window timestamp/method still under review** | **No** |

This is **49 candidate economic first-published reference periods / 59 initially+subsequently published headline-rate event records** across **four separate source streams**, not 49 canonical model-approved PIT rows and not 49 values of the *same* economic series. The remainder of the G8 still has the previously inventoried current observations; **20/24 research slots have no common published-source adapter yet** and are explicitly reported as such. *No observed economic data are deleted or hidden.*

The USD BLS 25-month window is **historical, not current**, and lacks complete original-day archived source bytes and historical revision matrix; the 2025 BLS shutdown also makes continuity toward 2026 nontrivial. AUD's retrospective pre-Oct-2025 complete CPI history must not be counted as individual first monthly releases from 2024.

### Universal source normalization contract

Every adapter returns an object containing:

- Currency, pillar, **exact publisher series ID**, frequency, units and **reference-period semantics**;
- Publisher and exact official release source URL with allowlisted hostname;
- Events with explicit `observation_period`, `FIRST_WEB` or `DETAILED_WEB`, `reported_value`, and offset-aware `visible_from_utc`;
- Evidence limitations, full revision lineage and release-day byte preservation marked **uncertified**, and canonical source mapping **not independently certified**.

The common evaluator validates all 24 slots, prevents duplicate source/period publication kinds, nonfinite values, publication-before-observation chronology, detailed-release-before-initial ordering, fictional/restricted publisher URL changes and future-data leaks in an as-of replay.

**Important:** `FIRST_WEB` denotes an *official web attestation of a reported first-release event*. It **does not** mean we captured immutable original-day release bytes or that we proved an exhaustive revision chain. Date-only Eurostat and ONS sources use conservative next-day-UTC visibility, explicitly not the actual intraday market-publication timestamp. The ABS and BLS records have original sourced local release clocks including daylight saving offsets.

### Two review layers must never be conflated

1. **Candidate research evidence**: publisher web events and revisions can be replayed with their established source caveats.
2. **Canonical model approval**: separately verify the registry series definition, geographic regime, observation frequency, source-to-model unit transformation, exact source timestamps, contiguous first releases (normally **25 monthly / 13 quarterly**), full revised-vintage trail, and independent historical PIT approval.

Even a matching candidate ID/frequency (e.g. GBP MGSX) is **not sufficient**: window labels and revisions must still be resolved. The controller has **zero** canonical source-certified PIT training histories and **zero** new score-eligible slots.

Current observed Macro V2 series are reviewed at 24 Oct 2026. When the controller replays earlier event cutoffs, **the registry/inventory layer remains explicitly identified as that later review snapshot**; we do **not** misrepresent today's observed histories as their historical content.

## Next structured onboarding (parallelizable)

- Implement adapters for remaining **20 slots**, starting with source combinations already in the official registry. Core Inflation/Labour candidates can reuse the existing adapter style; Growth must first select exact series, units and calendar semantics by country.
- Each adapter must independently validate publisher release dates, metric identities, observed values, revision distinctions and release vintage limitations, with no made-up historical releases or archival hashes.
- A future concurrent-source acquisition workflow may be implemented **after** source terms, first-release archive availability, clock precision and vendor limitations are reviewed. **No cron task/scheduler or new automation is created in this PR.**
- Once full PIT evidence exists, test the *separate* scoring pipeline; until then keep D.json, 28-pair ranking, website and live feeds untouched.

## Commands (read-only)

```bash
python -m unittest validation.macro.test_v2_pit_g8_control_plane_v1 -v
python -m validation.macro.v2_pit_g8_control_plane_v1 \
  --asof 2026-10-24T00:00:00Z \
  --json-out /tmp/macro-v2-shadow/g8-common-control-plane.json \
  --markdown-out /tmp/macro-v2-shadow/g8-common-control-plane.md
python -m validation.macro.v2_pit_g8_control_plane_v1 \
  --asof 2026-01-19T23:59:59Z \
  --json-out /tmp/macro-v2-shadow/g8-asof-december-before-detailed.json
```

All generated receipts are confined to `/tmp`. This creates **no new scheduled workflow** and modifies **no** `live_data/`, `site/`, `payload/`, `dashboard/`, `D.json`, 28 pair views, previous canonical source registry or past published research fixtures. The shared engine is currently an evidence **control plane**, not automated crawling or an operational Macro scoring engine.
