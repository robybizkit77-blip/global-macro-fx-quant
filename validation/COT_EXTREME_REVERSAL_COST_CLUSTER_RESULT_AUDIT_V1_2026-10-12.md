# COT 104W Extreme-Reversal — Cost & Clustering Stress Audit

Execution run: `38203350334`
Artifact: `cot-extreme-reversal-cost-cluster-38203350334`
Artifact id: `11726291610`
Artifact digest: `sha256:d759b086485bce4ee93f0ee5b546cd6b9944b08dea6654fddd021d3718e3275e`

## Replication

- pooled frozen OOS observations: 410
- weekly panel observations: 117
- panel annualized Sharpe: +1.47275

The stress suite therefore replicated the frozen PR #142 sample exactly to rounding before applying costs/clustering diagnostics.

## Transaction-cost stress

Fixed round-trip cost deducted from each signal return before weekly panel aggregation:

- 2 bps: Sharpe +1.2735; panel total log return +14.954%
- 5 bps: Sharpe +0.9746; panel total log return +11.444%
- 10 bps: Sharpe +0.4764; panel total log return +5.594%

Predeclared cost gates:
- 5 bps Sharpe >= 0.50: PASS
- 10 bps Sharpe > 0: PASS

## Persistent-extreme episode clustering

Consecutive same-direction extreme observations within 14 calendar days were collapsed into a single episode, retaining only the first observation.

- independent-ish episode observations: 44
- episode weeks: 40
- episode-only panel Sharpe: +1.2524
- episode-only panel total log return: +6.544%

Predeclared clustering gates:
- episode-only Sharpe >= 0.50: PASS
- minimum episode observations >=100: FAIL (44)

## Final verdict

`FAIL_PREDECLARED_COST_CLUSTER_GATE`

The failure is informative rather than economically negative. The candidate remains profitable under conservative fixed cost assumptions and the first observation of each persistent extreme episode still shows a strong positive Sharpe. However, the effective number of distinct positioning episodes is much smaller than the raw 410 weekly signal observations. The predeclared minimum of 100 episodes was not met and is not relaxed after observing the result.

Research implication: the historical evidence is stronger than a naive 410-observation count suggests, but the amount of independent regime/event evidence is still limited. PR #143 forward unseen validation remains decisive. No production signal or sizing authorization. No rescue tuning. No direct main. No auto-merge.
