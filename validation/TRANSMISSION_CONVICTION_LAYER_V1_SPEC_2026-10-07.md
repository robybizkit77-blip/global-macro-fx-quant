# Transmission & Conviction Layer V1 — Research Specification

Date: 2026-10-07
Status: RESEARCH_ONLY_NOT_PROMOTED

## Purpose

Define a deterministic cross-currency layer that explains whether a frozen macro bias is being transmitted through central-bank expectations, front-end rates, relative rate differentials and price.

This layer MUST NOT create, flip or veto the underlying macro bias. It is descriptive / conviction metadata only.

## Evidence behind the design

Cross-country diagnostics on JPY, EUR, USD, GBP and CAD show that front-end rate confirmation is economically meaningful but does not reliably improve FX outcomes out of sample when used as a mandatory gate. Therefore V1 treats rates as transmission evidence, not as a trading-rule filter.

## Frozen input contract

The layer receives already-computed states. It does not recompute macro, central-bank or rates models.

Required:
- `currency`: G8 currency code.
- `macro_direction`: `-1 | 0 | +1` where +1 is currency-supportive, -1 currency-negative, 0 neutral/withheld.

Optional evidence layers:
- `cb_direction`: expected central-bank impulse on the currency, `-1 | 0 | +1 | null`.
- `front_end_direction`: local 2Y / policy-sensitive front-end impulse, `-1 | 0 | +1 | null`.
- `relative_2y_direction`: relative 2Y differential impulse versus the relevant counterpart / USD benchmark, `-1 | 0 | +1 | null`.
- `price_direction`: observed price confirmation, `-1 | 0 | +1 | null`.

Every optional layer must carry provenance upstream. Missing data remain `null`; they are never imputed.

## Layer classification

For a non-neutral macro direction, each available evidence layer is classified relative to macro:
- `ALIGNED`: same sign as macro.
- `DIVERGENT`: opposite sign.
- `NEUTRAL`: explicit zero.
- `MISSING`: null / unavailable.

If `macro_direction == 0`, transmission state is `MACRO_NEUTRAL_OR_WITHHELD`; no conviction bucket is produced.

## Aggregate transmission state

No optimized weights are used. V1 reports counts only:
- `aligned_count`
- `divergent_count`
- `neutral_count`
- `available_count`
- `coverage_count` (non-missing optional layers)

The aggregate state is deterministic:
- `BROAD_CONFIRMATION`: aligned >= 3 and divergent == 0.
- `PARTIAL_CONFIRMATION`: aligned >= 2 and aligned > divergent.
- `MIXED`: aligned == divergent and both > 0, OR no side has dominance.
- `DIVERGENCE`: divergent >= 2 and divergent > aligned.
- `INSUFFICIENT_EVIDENCE`: fewer than 2 non-missing evidence layers.

These thresholds are predeclared design rules, not fitted to returns.

## Conviction label

The label is descriptive, not a position-sizing instruction:
- `HIGH`: `BROAD_CONFIRMATION`.
- `MEDIUM`: `PARTIAL_CONFIRMATION`.
- `LOW`: `MIXED` or `DIVERGENCE`.
- `WITHHELD`: `INSUFFICIENT_EVIDENCE` or neutral/withheld macro.

Crucially, `LOW` conviction does NOT invert the macro bias. It means the transmission chain is not confirming it.

## Human-readable causal output

The dashboard should show the chain in this order:
1. Macro state
2. Central-bank implication
3. Front-end reaction
4. Relative 2Y differential
5. Price confirmation
6. Transmission state
7. Conviction label

Example:

`Macro CAD: favorevole -> BoC implication: meno dovish -> 2Y: diverge -> relative 2Y: neutral -> price: conferma -> Transmission: MIXED -> Conviction: LOW`

## Guardrails

- No change to frozen engine commit `ff52198a75cc67f7dae96fc2bbf65623f170791c`.
- No change to rules fingerprint `3356baf0`.
- No live-data mutation.
- No OOS baseline mutation.
- No post-hoc optimization of counts, thresholds or weights.
- No rate layer can flip the macro direction.
- Missing data never become neutral data.
- `positive_share` from historical diagnostics must never be interpreted as direction-adjusted hit rate unless the signed-return convention explicitly makes positive = expected direction.

## Validation plan before promotion

V1 may be promoted only after:
1. deterministic unit tests pass;
2. the same classification contract is replayed on at least USD, JPY, GBP and CAD;
3. historical evaluation uses direction-adjusted FX returns (`signed_return > 0` = macro expected direction), not raw positive-return share;
4. walk-forward results are reported by currency and pooled, without threshold retuning;
5. promotion remains optional even if explanatory quality is good — the layer can remain dashboard-only metadata.

## Intended dashboard role

The layer should answer:

> “Il quadro macro dice X. La banca centrale, il front-end, il differenziale e il prezzo stanno davvero trasmettendo quel messaggio?”

It should never answer:

> “Il 2Y è salito, quindi compra la valuta.”
