# Reaction Function Evidence Matrix — G8

**Date:** 2026-10-06  
**Engine:** frozen `ff52198a75cc67f7dae96fc2bbf65623f170791c`  
**Rules fingerprint:** `3356baf0`  
**Status:** research roadmap only — no engine/live-data changes.

## Core rule

The reaction-function layer is **bank-specific**. The architecture is:

**Data importance → Central-bank interpretation → Market repricing → FX response**

Rates are an **observed repricing layer**, not a binary confirmation gate. Divergences are information states, not automatic invalidations.

## G8 matrix

| Bank / FX | Reaction function | PIT readiness | What we tested | What survived OOS | Current verdict | Next priority |
|---|---|---|---|---|---|---|
| **Fed / USD** | Dual mandate: inflation + labour primary | Growth partial; Labour WITHHELD; inflation/front-end not yet certified for reaction replay | None admissible yet | — | **NOT TESTABLE YET** | Unlock USD Labour PIT + coherent US 2Y/front-end history |
| **ECB / EUR** | Price stability; wages/services central, labour mostly mediated | Growth/Labour partial; wages conservative PIT; services 2024–26; EUR2Y ready | Labour direct, wages, services, wages+2Y, robustness/WF | 20d wages+2Y remained positive but weakened OOS | **PROMISING, NOT LOCKED** | Improve wage timestamps; extend services PIT |
| **BoE / GBP** | Price stability via domestic pressure: wages + services; labour context | Labour, AWE, services CPI, 2Y OIS all ready | Labour replay, AWE, AWE+OIS, paired OIS, full reaction-state + WF | Mechanical aligned state failed OOS | **MECHANICAL RULE REJECTED** | Stop ad-hoc combinations; future work only with predeclared policy-regime/consensus layer |
| **BoC / CAD** | Flexible inflation target + employment consideration | Growth, Labour, core CPI, headline CPI, 2Y, FX ready | Labour attribution, rates filter, state replay, full core/headline reaction-state + WF | Aligned macro/core/headline retained some 20d coherence but weakened OOS | **BEST PROOF-OF-CONCEPT, NOT LOCKED** | Freeze architecture; wait for genuinely new OOS evidence |
| **RBA / AUD** | Dual mandate | Live certified; historical reaction inputs/rates WITHHELD | None | — | **NOT TESTABLE YET** | Historical first-release labour + inflation + front-end |
| **RBNZ / NZD** | Price stability primary post-2023 remit | Live certified; historical reaction inputs/rates WITHHELD | None | — | **NOT TESTABLE YET** | Historical inflation-first PIT; no synthetic OIS |
| **SNB / CHF** | Price stability + FX monetary conditions | Live certified; historical reaction inputs/rates WITHHELD | None | — | **NOT TESTABLE YET** | Historical inflation + explicit FX-conditions architecture |
| **BoJ / JPY** | Price stability through wage-price cycle | Labour structurally feasible but not activated; wages/inflation/rates pending | Labour PIT feasibility audit | — | **FEASIBLE, PENDING ACTIVATION** | Resolve event-time policy; certify wages + inflation |

## What the completed tests taught us

### 1. There is no universal `Macro → 2Y confirmation → FX` rule

That simple confirmation filter failed in both **GBP** and **CAD**, and even in EUR the apparent improvement remains too weak and sample-limited to promote.

### 2. CAD validates the architecture more than it validates a trading edge

When Growth/Labour and persistent inflation were coherent, the state became more interpretable and the 20-day FX response improved in-sample. But walk-forward weakened enough that it remains a **descriptive state**, not an engine rule.

### 3. GBP proves that economically correct inputs can still be insufficient

Wages and services are clearly central to BoE policy, but their mechanical alignment with Labour did not translate reliably into GBP. The missing context is likely the **starting inflation level, policy path already priced, growth trade-off, MPC regime, and surprise vs consensus**.

### 4. EUR remains the most interesting unfinished case

The wage → front-end → EUR channel is economically coherent and showed some 20-day OOS persistence, but historical wage dates are conservative checkpoints and services PIT is still short. It is **promising research evidence, not a locked signal**.

## Research order

1. **USD / Fed** — unlock Labour PIT and coherent US front-end history.
2. **EUR / ECB** — improve timestamp quality and extend services PIT.
3. **JPY / BoJ** — activate Labour event timing and add wages/inflation PIT.
4. **AUD / RBA** — build dual-mandate historical PIT blocks.
5. **CHF / SNB** — inflation plus explicit FX-conditions architecture.
6. **NZD / RBNZ** — inflation-first historical architecture.
7. **CAD / BoC** — freeze; no more combination hunting.
8. **GBP / BoE** — freeze current evidence; no more ad-hoc combinations.

## Dashboard implication

The future dashboard should not show one opaque reaction-function score. It should expose:

**1. DATA IMPORTANCE** — which release matters for this central bank?  
**2. CB INTERPRETATION** — hawkish / dovish / mixed / neutral in that mandate.  
**3. MARKET REPRICING** — what front-end rates actually did.  
**4. DIVERGENCE STATE** — aligned, divergent, or unresolved.  
**5. FX RESPONSE** — whether price confirms, lags, or contradicts the macro/rates picture.

No layer should automatically override the others without separate evidence.
