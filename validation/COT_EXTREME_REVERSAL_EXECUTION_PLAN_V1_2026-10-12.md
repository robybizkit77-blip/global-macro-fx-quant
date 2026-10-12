# COT Extreme Reversal V1 — Execution Plan

Execution is authorized only if the parent predeclaration contract is GREEN.

The one-shot implementation must reuse the already certified PIT-safe COT calendar and Federal Reserve H.10 FX return labels from the parent lineage. It must not modify the frozen percentile thresholds, horizon, split, currency universe, or edge gates.

Required outputs:
- pooled and weekly-panel OOS observation counts
- panel Sharpe, total log return, max drawdown and directional accuracy
- per-currency Sharpe and hit rate
- signal counts for >=80 and <=20 percentile sides
- concentration diagnostics
- explicit PASS/FAIL for every predeclared gate
- immutable audit receipt with engine/result hashes

No rerun after an economic result except for a purely mechanical failure proven not to have exposed a valid result.
