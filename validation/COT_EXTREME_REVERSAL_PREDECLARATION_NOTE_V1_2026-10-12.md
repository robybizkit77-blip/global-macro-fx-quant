# COT Extreme Reversal V1 — Predeclaration Note

This branch intentionally starts a new, economically distinct COT hypothesis after the weekly-flow continuation experiment failed its predeclared gate.

## Frozen question
Does an extreme 104-week percentile of CFTC Legacy Non-Commercial Net/Open Interest predict short-horizon FX reversal?

## Frozen signal
- percentile >= 80: short local currency vs USD
- percentile <= 20: long local currency vs USD
- otherwise: no position
- 104-week lookback only
- PIT-safe COT availability only
- 5 FX trading-day horizon
- same seven currencies

The 80/20 thresholds are inherited from the project's existing COT interpretation standard and are not selected from predictive performance.

## Explicitly forbidden
- searching alternate percentile cutoffs
- excluding weak currencies after result
- changing the 5-day horizon after result
- adding price divergence or flow filters to rescue failure
- converting a failed result into a production score

No predictive result has been observed on this branch.
