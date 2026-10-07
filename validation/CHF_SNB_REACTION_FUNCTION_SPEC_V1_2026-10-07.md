# CHF / SNB Reaction Function Spec V1

Status: RESEARCH_ONLY_NOT_PROMOTED
Date: 2026-10-07
Frozen engine: ff52198a75cc67f7dae96fc2bbf65623f170791c
Rules fingerprint: 3356baf0

## Purpose
Define the CHF/SNB research contract without forcing CHF into the common G8 front-end-confirmation framework.

## Core principle
For CHF, the exchange rate is part of the monetary-policy transmission mechanism itself. A simple rule such as “Swiss 2Y confirms macro => higher conviction” is structurally incomplete and is forbidden in V1.

## Canonical causal order
1. Inflation state
2. Domestic economic / labour state
3. SNB policy implication
4. Swiss front-end / 2Y transmission
5. CHF exchange-rate pressure
6. Official SNB FX-transaction regime
7. Future CHF G8 basket outcome

## Official research inputs
- Inflation: SNB data portal / SFSO, cube `plkopr`, monthly headline CPI YoY.
- Labour: SNB data portal / SECO, cube `amarbma`, seasonally adjusted unemployment rate.
- Rates: SNB data portal, cube `rendoblid`, Swiss Confederation 2Y and 10Y yields. The 2Y is a transmission/context variable, never a standalone gate.
- FX price: CHF equal-weight basket versus the other 7 G8, using the already certified ECB G8 price-matrix convention where applicable.
- FX policy: official SNB foreign-exchange market transaction volumes disclosed for the previous quarter. This is the preferred intervention-policy layer.
- Sight deposits: context/liquidity only. They must NOT be interpreted mechanically as direct FX intervention.

## State design
### Macro state
Direction is inferred from inflation and domestic conditions. No numeric weights are fitted in V1.

### FX-pressure state
Use only price information known at the decision timestamp. Future CHF returns are outcome only and must never be reused as an input.

### Intervention-policy state
Official SNB FX-transaction data may classify the preceding quarter as:
- FX_PURCHASES_CHF_WEAKENING
- FX_SALES_CHF_STRENGTHENING
- LOW_OR_NO_REPORTED_ACTIVITY
- MISSING

The exact sign convention must be validated against the official series metadata before historical replay.

## Transmission output
Allowed dashboard states:
- TRANSMISSION_CLEAN
- TRANSMISSION_PARTIAL
- TRANSMISSION_DIVERGENT
- TRANSMISSION_WITHHELD

Forbidden:
- universal HIGH/MEDIUM/LOW score
- common G8 rates weight
- automatic macro-bias inversion from 2Y
- sight-deposit change treated as intervention
- future price used as contemporaneous confirmation

## Replay contract to validate before use
Primary horizon: signed 20-market-day CHF G8 basket return after the confirmation window.
Secondary horizons: 5d and 60d only if timing remains identical and no tuning is introduced.

Chronological split: first 40% initial sample, remaining 60% forward OOS.

Minimum evidence requirements before CHF leaves WITHHELD:
1. certified historical monthly CPI observations with release timing / PIT policy documented;
2. certified historical domestic-condition input with timing documented;
3. certified same-basis Swiss 2Y history;
4. official historical SNB FX-transaction series with sign semantics validated;
5. no event-time leakage in CHF basket outcome;
6. OOS results reported by macro regime and by intervention-policy regime.

## Current status
Macro source adapters already exist and are official-source based. A current official Swiss 2Y/10Y adapter also exists. The missing decisive block is a certified historical policy-FX layer plus PIT timing sufficient for a reaction replay. Until that is closed, CHF remains WITHHELD for empirical reaction-function promotion.

## Guardrails
changes_engine_rules = false
changes_live_data = false
changes_oos_baseline = false
production_rule = WITHHELD
