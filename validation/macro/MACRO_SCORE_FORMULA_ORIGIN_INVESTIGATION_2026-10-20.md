# Macro score formula — historical origin investigation (2026-10-20)

## Evidence established
- The earliest `live_data/sections/D.json` commit visible in the GitHub path history is [`529acdd6026c88ecee8451e2e5bc36c740eece7d`](https://github.com/robybizkit77-blip/global-macro-fx-quant/commit/529acdd6026c88ecee8451e2e5bc36c740eece7d), committed 2026-10-05. Its `asOf` field is **2026-09-25**.
- The 8 × 3 Growth/Labour/Inflation numbers, and 8 `cycle` classifications in that snapshot match the currently committed D.json (checked 2026-10-20).
- `validation/build_macro_candidate.py` implements time-series update, historical percentiles, qualitative temperature/direction/acceleration for inflation and labour. These are **not** the original source-to-number equations behind `D.macro[ccy].growth/labour/inflation`.
- `validation/macro/rebase_readiness_v1.py` explicitly marks historic scalar scores as not recalculated and source-to-score mapping unspecified.
- `validation/macro/score_formula_provenance_v1.py` proves browser numeric-score **reading** is separate from currency structural directional rule replay. This update pins all 24 numeric scores and 8 cycles to the earliest repository snapshot and rejects changed-but-finite scalars.

## What this does *not* prove
The original formula's selected data series, normalizations (including lookback and missing-data rules), feature transforms, weights, sign conventions, aggregation, cycle thresholds and contemporaneously available publication timestamps are **not certified**. Only one dated output vector (24 scores) is not enough to identify a unique generating model. A formula that merely fits these 24 numbers can be overfit and cannot authorize refreshed signals.

## Evidence required before a model release
1. Identify an independently documented original generator (code/formula/specification), including fixed inputs, transforms, weights and cycle regime mapping.
2. Reconstruct source values **as they were released and observable by the baseline date**; distinguish observation date, first release and subsequent revision.
3. Replay the 24 values to a predefined numerical tolerance *without* fitting those same 24 outputs to choose the formula.
4. Add more than one independent dated replay and an out-of-sample check; confirm uncertainty and missing inputs fail closed.
5. Independently review the transition to a new baseline; only then consider rebuilding structural pair preferences.

## Safety / scope
Read-only audit and tests under `validation/macro/` only. Frozen historical Macro as-of stays 2026-09-25. Neither `D.json` nor the 28 pairs, live data, active Control Room, GitHub schedules or ChatGPT tasks are changed. The **economic generator remains NOT CERTIFIED**.
