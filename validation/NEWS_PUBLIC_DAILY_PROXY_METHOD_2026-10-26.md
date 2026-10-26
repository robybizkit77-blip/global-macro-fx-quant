# Public-source fallback for Event → Market (research only, 26 October 2026)

## New policy

Do not buy data, request written licences, initiate Dukascopy automated acquisition, or present inferred intraday movements as actual data. Use **officially published, publicly accessible, already obtained daily series** when sufficient, and label numeric observations correctly. Models/estimated values must come from explicitly defined inputs and documented transformations: no automatic numerical fill-in from thin air. Missing historical event-window data may remain unavailable and must not be silently interpolated.

This shadow example uses the BLS 2 October 2026 08:30 New York scheduled report and (1) ECB G8 daily FX reference history, (2) U.S. Treasury 2Y dated official history, (3) an explicitly segregated daily OIS/futures 6M operational snapshot.

ECB reference method: https://www.ecb.europa.eu/stats/exchange_rates/html/index.pl.html
Treasury daily par yield method: https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics

## What we can compute without intraday vendor ticks

From data available in the repository at the time of the test:

| EUR/USD ECB fixing | Official observation |
|:--|--:|
| 1 October 2026 | 1.1298 |
| 2 October 2026 | 1.1225 |
| 5 October 2026 | 1.1204 |
| 1 Oct → 2 Oct | −73.0 pip |
| 2 Oct → 5 Oct | −21.0 pip |
| 2 Oct → 5 Oct period | Three calendar days; **weekend** |

These figures are **observed daily reference rate changes**, not intra-event estimates or the causal effect of the BLS announcement. ECB fixing quotes are generally assembled around 14:10 local Central European time, with publication around 16:00; individual record-level executable quote timestamps are not present in our history. Never claim exact intraday before/after from the fixing date.

For Treasury 2Y, the repository's existing dated history has an observed 2026-10-02 value (4.83%), but the preceding retained observation is 2026-09-28, a **four-calendar-day gap**. Therefore the gate explicitly **rejects a false one-day 2Y reaction**. It preserves the observed level/date and yields a null one-day change, not zero and not an interpolated rate. The OIS/futures current snapshot is dated weeks after BLS, so **no event-date market repricing** is computed from that quote.

## Separate layers

1. **Data osservato**: quoted official reference rate, source, date, unit and extraction method.
2. **Proxy descrittivo**: change between dated daily reference rates, with exact endpoints and weekend/gap caveats. No event impact claim.
3. **Stima quantitativa**: only if a separately validated historical regression or other explicit out-of-sample model exists; no such event-window point estimate is created here.
4. **Reazione evento → mercato**: unmeasured until source-aligned pre/post observations exist. Scheduled release time is not an independent trade dissemination timestamp.

Do not replace official 2Y yields with an OIS level, label exchange futures as OIS, or invent an equal historical value to fill missing rates. Test fixtures are not newly obtained real data.

## Repeat locally

```bash
python -m unittest validation.test_news_market_daily_proxy_v1 -v
python -m validation.news_market_daily_proxy_v1 \
  --as-of 2026-10-26 \
  --out /tmp/gmfq-public-daily-reference-proxy.json
```

The output stays under `/tmp`. The CI is triggered only on pull request or manually, not scheduled. The engine writes nothing to `live_data/`, current reports, site, alerts, original model scores, 28 pairs, Beta, Forward Test or backtests.

### Future extension

Connect dated daily snapshots to the research UI as **"Contesto giornaliero / Proxy"**, **not** as a market reaction signal. Only add a statistical expectation model once the features, PIT release calendars, surprise vs consensus and out-of-sample validation are confirmed. Preserve the original baseline and compare with forward test before trading implications.
