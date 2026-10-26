# Forward outcome bridge: ECB reference observations only (26 October 2026)

**Purpose:** close the factual chain **immutable decision receipt → recorded initial ECB fixing → future dated ECB fixing**, for dates that genuinely occur after the observation and its registered horizon. Do not claim strategy results yet.

## Source and precise limits

Source: existing repository mirror of the [ECB euro foreign exchange reference-rate history](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml). All G8 non-EUR crosses use (quoted currency per EUR) / (base currency per EUR), with JPY standard 0.01 and others 0.0001 pip unit. The initial reference rate was stored *at the genuine 19:30 Rome capture*, if admitted, and the reference history is hashed in that original snapshot.

The six research horizons are **1D, 3D, 1W=7, 2W=14, 1M=30 and 3M=90 calendar days**, preserving the existing forward schema. They are **not** automatically business days or exact calendar-month roll dates.

On each eligible future observation:
1. Read only prospective `GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0` snapshots labelled `FROZEN_CORE_BASELINE_OBSERVATION`, with the frozen **25 September 2026** baseline. Ignore the 14 October smoke records (legacy 1.0).
2. Verify the snapshot SHA, its pair direction, original official fixing date, unchanged t0 historical rate, and the original source-hash *consistency* (not independent market licence or raw data replay). If the ECB historical t0 rate was revised, **fail closed**, no silent overwrite.
3. Verify that the full elapsed UTC horizon has passed. Because an ECB fixing normally occurs well **before** a 19:30 Rome decision time, and per-fixing intraday timestamps are not certified here, conservatively use the **first fixing date strictly later than the horizon maturity calendar date**. This intentionally overshoots the nominal horizon; the exact resulting dates and gap length are always recorded. Do not select a price just before a full horizon matured.
4. At runtime, never consume a fixing dated after the local evaluation day, nor the current-day fixing before **19:00 Rome**; never interpolate weekends/holidays. A source gap of over four calendar days or a missing currency rate is **not estimated** and produces no observation.
5. Preserve the pair and official source URLs, observed FX fixing dates, change in pips and percent. Explicitly leave `trade_gross_return`, `trade_cost_bps`, `trade_net_return`, `trade_pnl` as **null** and `model_out_of_sample_performance_certified=false`. This is a **price-reference comparison**, not an executable buy/sell decision, backtest, validated forward P&L or causal surprise.
6. Append observations in a separate, hash-checked journal `validation/forward/reference_observations/ECB_REFERENCE_COMPARISONS_V1.jsonl`. Never write actual Core outcomes to the 1.0 outcome journal or alter prior snapshot hashes.
7. Schedule independent Rome **21:15 weekday** checks, with DST paired cron and local clock guard. PR checks are read-only. A scheduled run without real prospective T0 or matured horizon reports zero observations, not fake success. GitHub cron may be delayed; a failed non-fast-forward push requires later naturally eligible retry, never retroactive snapshot creation.

**Owner:** `validation/forward/observe_official_ecb_reference_outcomes_v1.py` and `.github/workflows/forward-ecb-reference-outcomes-v1.yml`. No new vendor data purchases, automated scraping, site UI, scoring, 28-pair rank changes, Beta promotion, trading signal, or 08:00 schedule changes.

### Verification
```bash
python -m unittest validation.forward.test_observe_official_ecb_reference_outcomes_v1 -v
python -m validation.forward.observe_official_ecb_reference_outcomes_v1 \
  --receipt /tmp/gmfq-ecb-reference-outcomes.json
```

**Not done:** independent executable intraday FX quotes, spreads, financing, custody, trading costs, position sizing, true PIT macro vintage, genuinely refreshed Core daily scores, statistically meaningful OOS performance. These remain required before calling any future price-reference change a *trade return* or *predictive model edge*.

The first archived after-T0 comparisons can only exist **after** a complete real forward snapshot and one of the required future horizons. On 26 October morning, those have not yet occurred.
