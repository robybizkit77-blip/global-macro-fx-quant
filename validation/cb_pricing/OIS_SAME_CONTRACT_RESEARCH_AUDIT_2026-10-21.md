# Same-contract futures changes — research-only contract (21 October 2026)

## Objective

Measure the observable change between **two verified close/day-bar quotes for exactly the same listed futures contract**. The project already collected three relevant historical snapshots: commit `e5a3cede0df` (captured 19 Oct), `a611277716c` (20 Oct) and `195ab3c45d9` (21 Oct). We have extracted **23 distinct, source-dated contract observations**. Each row records the original first-seen timestamp and source commit, contract identity, expiry, verified quote date and the 100-price conversion.

This archive **does not claim** to reconstruct full official market settlements, an actual 3/6/12-month cash OIS curve, or a daily risk-neutral monetary-policy repricing series. It is an **informational-only, secondary-source historical comparison**.

## Independently matched examples

| Market | Identical contract | From | To | Rates (%) | Observed difference |
|---|---|---|---|---|---:|
| USD | CBOT:ZQZ2026 | 19 Oct | 20 Oct | 4.080 → 4.070 | **−1.00 bp** |
| USD | CBOT:ZQV2027 | 19 Oct | 20 Oct | 4.660 → 4.685 | **+2.50 bp** |
| EUR | EUREX:FST3M2027 | 19 Oct | 20 Oct | 3.110 → 3.100 | **−1.00 bp** |
| EUR | EUREX:FST3V2026 | 16 Oct | 19 Oct | 2.5325 → 2.535 | **+0.25 bp** |
| CHF | ICEEUR:SA3M2027 | 19 Oct | 20 Oct | 0.320 → 0.335 | **+1.50 bp** |
| CHF | ICEEUR:SA3U2026 | 19 Oct | 20 Oct | −0.050 → −0.0475 | **+0.25 bp** |

**Example of what not to do:** USD selected 6m future was `ZQH2027` on one run and `ZQJ2027` later. The change between them is **contract roll, not a measured market repricing**. Do not subtract their prices, even if both were displayed under the approximate "6M" label.

## Persistent record and workflow

- `history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl`: immutable append-only observed bars keyed on `(currency, listed_contract, observation_date)`. Duplicate collection runs **do not** add rows.
- `ois_same_contract_history_v1.py`: validates exchange/symbol, expiry, source daily-bar quote date, rate = 100 − price (within 0.02bp), source age and informational/no-promotion governance. Contradictory same-contract quotes **on the same source day** refuse overwriting the archive.
- `test_ois_same_contract_history_v1.py`: real archival examples, no-roll comparison, duplicate idempotence, source timestamp/price/ticker negatives and explicit prevention of official-status claims.
- **Existing** `OIS Estimated Snapshot Repricing V1` and `OIS G8 History Persistent Daily V1` workflows execute the validator and append new observations when available. They already run on their current triggers; **no new schedule, workflow or ChatGPT automation**.
- `push_ois_refresh_with_lease_v1.py`: same pre-existing bounded main-writer lease, dependency protections, and no force-push semantics now includes the one append-only history file. Both OIS workflows already use the same protected writer group.

## User-facing reading

On the existing `#/tassi` research-only section, a **compact 3 × 3 matrix** may show the latest comparable previous quote for the same **3M, 6M and 12M-labeled contracts** (USD/EUR/CHF). Each cell has its own source dates, contract code and observed change in basis points. The nine labels correspond to selected dated futures, not spot OIS tenors; both dates are preserved even when not successive sessions. They are only displayed when the current validated listed contract, expiry, rate and source date match the latest archival observation, and the previous source observation is within seven calendar days. No matches or outdated archives produce an explicit unavailable/insufficient-data notice — **never simulated 1D/1W OIS changes**.

The general 'OIS 4/8 certified · 8/8 context' counter remains unchanged. The additional comparison is never used in Macro scores, bank stance, FX bias, sizing, 28 pair rankings, backtests, alerts or official OIS policy repricing.

## Nine held-out source-linked comparisons available on 21 October 2026

The source archive has two distinct valid observations for **all nine currently selected** indicative futures horizons:

| FX | 3M-labeled current contract | 6M-labeled current contract | 12M-labeled current contract |
|---|---|---|---|
| USD | ZQZ2026: **−1.00 bp** (19→20 Oct) | ZQJ2027: **0.00 bp** (19→20 Oct) | ZQV2027: **+2.50 bp** (19→20 Oct) |
| EUR | FST3V2026: **+0.25 bp** (16→19 Oct) | FST3G2027: **−1.00 bp** (16→19 Oct) | FST3M2027: **−1.00 bp** (19→20 Oct) |
| CHF | SA3U2026: **+0.25 bp** (19→20 Oct) | SA3Z2026: **0.00 bp** (19→20 Oct) | SA3M2027: **+1.50 bp** (19→20 Oct) |

A **zero** is an observed unchanged futures implied rate across two verified dates, not a missing quote. If a contract has rolled, one source date is missing, its expiry/price differs from the certified displayed quote, or the archive is stale, the cell is **— / non confrontabile**, never an inferred or interpolated number.

The tested app continues to show only the latest matching two market days for each exact contract and tenor, independent of job execution time. A source-date gap may include weekend or illiquid sessions; consequently these values are **observed multi-date differences**, not necessarily certified 1-day changes.

## Limitations

USD ZQ futures reference calendar-month average effective fed funds; EUR FST3 and CHF SA3 reference future three-month compounded overnight windows. Matching the identical contract resolves **contract-roll contamination** but does not resolve futures-versus-swap basis, settlement timing, exchange holidays, delivery accrual period or source usage rights. Even if source quote dates are consecutive, the new layer deliberately calls the result an **observed same-contract change**, not a certified T/T−1 OIS delta. It is not a trading signal.

More data will improve the descriptive archive automatically through existing executions. No backfill is performed from estimated 3/6/12M rows lacking precise contract identities.
