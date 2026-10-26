# EUR 2Y/10Y source candidate — active v10 function impact & isolated rollback (26 October 2026)

**Verdict: candidate technically roundtrip/rollback safe; NOT READY for live publication pending explicit CHF 10Y estimate rebasing review and desktop/mobile post-data-change QA.**

## What was actually executed

The QA runs unmodified **real source code** extracted from `site/control-room-preview/home-navigation-v10.js`: `ratesAll`, `dateHistory`, `estimate`, `pairMarketReactionAudit`, `pairWhatChangedEvidence` plus their helper functions. Inputs are the repository's *published original* G8 Rates history and the official 2Y+10Y **282-date** ECB data candidate built independently from original publisher CSVs in PR #642. It also uses the existing ECB official FX G8 reference history. The local daypart/FX freshness clock is pinned to **2026-10-26** for reproducibility; the original production functions themselves are unchanged. No Core `D.json`, trading allocation or pair ranking is loaded or recomputed.

### Actual original v10 outputs: before vs after historical ECB EUR replacement

| Active v10 output | Before old EUR history | After original BCE historical source | Measured impact |
|---|---:|---:|---|
| **CHF 2Y proxy indicative yield** | **0.2416675%** | **0.2498098%** | **+0.8142 bp** |
| CHF 2Y beta | 0.266708 | 0.245196 | −0.021513 |
| CHF 2Y historical R² | 0.13996 | 0.11654 | LOW / **BASSA** |
| CHF 2Y latest matched anchor date | 2026-09-22 | 2026-09-30 | +8 calendar days |
| **CHF 10Y proxy indicative yield** | **0.3947256%** | **0.5102548%** | **+11.5529 bp** |
| CHF 10Y beta | 0.317909 | 0.383993 | +0.066085 |
| CHF 10Y historical R² | 0.25945 | 0.24602 | LOW / **BASSA** |
| CHF 10Y latest matched anchor date | 2026-09-22 | 2026-09-30 | +8 calendar days |
| 28 FX pair market-reaction snapshots | as published | equivalent in the fixed Oct 26 comparison window | **0 changed** |
| 28 FX pair observed 2Y change texts | as published | equivalent in the fixed Oct 26 comparison window | **0 changed** |
| EUR official latest 2Y/10Y and weekly changes | unchanged | unchanged | **0 bp** |
| Core weights, rankings, FX signals | **not loaded/altered** | **not loaded/altered** | **none** |

These CHF figures are **estimates produced by the site's historical proxy regression**, not an SNB yield observation. The official CHF source remains dated **2026-09-30**. R² levels are low and do not validate predictive accuracy or a trade. The **+11.55 bp CHF10Y proxy revision is a change in method/input history, not a market jump today**; it is material for display consistency. The research QA marks it `CHF_10Y_proxy_rebase_review_required=true` using a clearly labelled **5bp descriptive QA review threshold**, not a trading rule or new canonical scoring parameter.

## What was proven about the publication mechanics

In a **detached, temporary Git worktree** (never `main`, never production site), the job successfully performed:

1. The existing direct-section replacement preview followed by `--apply` for `NATIVE_RATES_DATA.json`.
2. Rebuilt `live_data/manifest.v2.json` using the original canonical builder.
3. Ran the original `check_live_update_contract.py` and `rebuild_live_data_runtime.py --verify-only`, both `PASS`; the runtime builder reported byte-identical no-op reconstruction.
4. Asserted the **only** changed files were `live_data/sections/NATIVE_RATES_DATA.json`, `live_data/manifest.v2.json`, `payload/part-00.txt`.
5. Restored the original files with `git restore`, verified the original Rates SHA-256, a completely clean worktree, and the original live-data contract passed again. Deleted the detached worktree.

The PR is **not a production deployment**, does not modify the active source, does not change schedules, never saves the ECB original sources to published files and does not update historical Core snapshots or Forward measurements.

## Release blockers still open

- Explicitly decide how to show the **CHF proxy recalibration +11.55bp** in v10: retain **BASSA / indicative estimate** label, prevent a false 'CHF yields jumped 11.55bp today' interpretation, and document the historical reference change.
- Exercise the **candidate** in a real Chrome/Playwright Control Room at **1440px desktop and 390px phone** using approved 32 v10 layout parts, including rate chart history and CHF proxy cards. Static data/functions and roundtrip are not full visual tests.
- Verify the permanent daily Rates generator can't silently reintroduce non-equivalent EUR old historic values; add publisher-parity or baseline-hash gates without interrupting normal 08:00 refresh.
- Perform controlled live-data release with explicit source date/rollback and after-publication browser recheck only when above are completed.

**Keep Beta separate:** 28/28 pseudo-out-of-sample historical computability does not equal historical point-in-time model validation or strategy performance.

## CI artifacts

- [PR #643 — active v10 code and isolated payload rollback](https://github.com/robybizkit77-blip/global-macro-fx-quant/pull/643)
- `validation/rates/audit_v10_eur_ecb_history_chf_pair_sensitivity_v1.cjs`
- `.github/workflows/eur-2y10y-v10-impact-rollback-v1.yml`

Run the standalone source-code implementation contract locally:

```bash
node validation/rates/audit_v10_eur_ecb_history_chf_pair_sensitivity_v1.cjs --self-test
```

The independent full source build and isolated release mechanics are only available in GitHub Actions (official ECB publisher data retrieved each QA run).
