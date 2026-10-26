# Beta PDF vs Forward Test — end-to-end signoff inventory (26 October 2026)

**Verdict: NOT READY FOR FINAL LAUNCH SIGNOFF. No existing 28-pair decision baseline or live signal is changed.**

## Beta: do not confuse mathematical reference with implementation

Reviewed the user-provided **Il_beta_dalla_A_alla_Z.pdf** (October 2026, 100 PDF pages), including its detailed contents, chapter 23.3 ten-step working procedure (PDF page 95), and chapter 23.4 strict out-of-sample hedge-variance evaluation (PDF page 96). The educational document contains **24 chapters**, many optional method families for different tasks (high-frequency equities, pair cointegration, implicit option beta, GARCH). Those methods are **not automatically mandatory production features of an FX-vs-2Y beta** unless its goal and data actually warrant them.

The actual repository beta implementation:
- `validation/beta/rate_beta_observational_v1.py` computes a **rolling OLS with intercept** from **52 already-aligned weekly observations** for each nominated pair, `fx_return` on `delta_rel_2y`.
- It does **not** generate an official, historically point-in-time weekly input panel; the CSV is caller supplied.
- Output correctly labels `RESEARCH_NOT_VALIDATED` and B1/B2 **NOT_EVALUATED** (canonical definitions absent). No production promotion, historical proof, beta regime, score or backtest.
- The 10-point procedure: (1) purpose/reference **partly chosen**; (2) PIT panel **not certified**; (3) frequency sensitivity **not tested**; (4) OLS and HC3 robust standard error **implemented in research only**, no HAC or certified PIT; (5) Huber plus leave-one-out sensitivity **implemented in research only**; (6) one-week Dimson lead/lag **retrospective-only diagnostic**, no future x(t+1) permitted in a signal; (7) four consecutive 52W rolling estimates **research only**, EWMA/Kalman not added or calibrated; (8) shrinkage when relevant **not tested**; (9) symmetric two-asset estimator suitability **not evaluated**; (10) strict OOS variance reduction **not demonstrated**.
- Steps 4–7 above were expanded on 26 October through PR #656 (HC3 / Huber) and PR #657 (Dimson / rolling); observational gates, historical panel limitations, and performance certification remain blocked.
- **Do not invent B1/B2 rules** to produce a superficial PASS. Later gate the meaningful minimum for our FX use case and explicitly justify any method exclusions.

## Forward: preserve real-time observations, never retrospective pseudo evidence

Repository facts as of 26 October:
- `validation/forward/decision_snapshots/CORE_DECISION_SNAPSHOTS_V1.jsonl` contains **28 snapshots for 28 pairs**, all one `real-main-smoke-20261014` run at **2026-10-14T21:01:45Z**.
- No `validation/forward/outcomes/` folder or completed realized-outcome file is present.
- `CORE_FORWARD_DECISION_LOGGER_V1_SCHEMA.json` requires an `inputs` object, but the archived smoke entries instead have decomposed input sections; this **contract mismatch** is identified and **not** rewritten retroactively. The original immutable snapshot receipts and hashes remain unchanged.
- No multiple-date repeat of the 28-pair decision set or OOS P&L analysis is evidenced by the archived ledger.
- `HISTORICAL_WALKFORWARD_V93_2026-10-01.json` explicitly says **PSEUDO_OOS_RECONSTRUCTIBLE_CORE_ONLY**. This is not real forward observation or an executable Core portfolio.
- `.github/workflows/forward-monitor-ui-gate-v1.yml` tests the **legacy root dashboard** `index.html` and `dashboard/forwarddesk-operational-v1.js`, not the approved active Preview `site/control-room-preview/`. Browser-green on that workflow alone cannot certify active UI.

`validation/forward/audit_beta_forward_launch_readiness_v1.py` produces a read-only truth receipt: SHA integrity, duplicate IDs, distinct decision timestamps, output presence, snapshot contract-field coverage, and explicit blocked state. The gate stays non-promoting irrespective of local test success.

## Outcome safety hardening

`validation/forward/attach_core_outcomes_v1.py` now:
- rejects timezone-naive/forward-dated price `available_at` relative to evaluation day;
- requires the outcome source time to be **strictly after decision** and after the complete horizon relative to the **decision instant**;
- rejects unknown snapshots, duplicate keys within a batch, nonfinite or nonnumeric returns, missing/negative transaction costs and missing source reference;
- validates the entire supplied batch *before* append; duplicate previously logged horizons are idempotent;
- labels any ingested price `CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED` and `performance_certified=false`.

This only prevents false acceptance. It does **not** supply independent event-price/cost audit, performance analytics, historic PIT, or actual outcomes. No artificial forward returns have been generated. No automated capture workflow or trade execution was enabled.

## Remaining real launch work (mandatory before claiming a fully validated trading model)

1. Reconstruct the canonical Beta B1/B2 specification and its intended economic use, obtain genuine PIT weekly FX + 2Y panel, measure uncertainty/stability and OOS hedge-effectiveness. Do not equate the whole mathematical textbook with a one-size-fits-all implementation requirement.
2. Fix the **new** Forward logger snapshot schema to match the canonical `required_snapshot_fields` contract with versioning and immutable legacy treatment. Do not mutate the October 14 archived rows.
3. Establish independently dated **recurring forward snapshots** *only once point-in-time capture is valid*; outcome ingestion must use comparable future prices with source/clock evidence and costs.
4. Verify real outcomes at 1D/3D/1W/2W/1M/3M after horizons mature; compute performance and uncertainty, no ex-post exclusion of failed picks and no backfill of decisions.
5. Validate the *active Preview* browser at 1440 px / 390 px and run final Morning 08:00 delivery + system QA gates.

**Release distinction:** A **display-only research Control Room** may continue to function with disabled Beta/OOS performance claims, but an advertised **quantitatively certified model / forward track record** is **not** ready.

Run without network or model writes:
```bash
python -m unittest validation.forward.test_audit_beta_forward_launch_readiness_v1 -v
python -m unittest validation.forward.test_attach_core_outcomes_safety_v1 -v
python -m validation.forward.audit_beta_forward_launch_readiness_v1 --out /tmp/gmfq-beta-forward-launch-readiness.json
```
