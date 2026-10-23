# Macro V2 — EUR/USD intraday acquisition gate (23 October 2026)

This is a research-only, **offline** importer, not a scheduled downloader or a claim that any real tick records have been acquired. It prepares a safe next step after the BLS nine-event evidence gate.

## Candidate sources

- [Dukascopy historical export](https://www.dukascopy.com/swiss/english/marketwatch/historical/) provides historical Forex data. An independent community-supported downloader documents tick bid/ask exports and milliseconds timestamps at [dukascopy-node](https://www.dukascopy-node.app/downloading-tick-data). Check current permissions and authenticity before importing.
- [CME DataMine](https://www.cmegroup.com/datamine.html) includes historical BrokerTec Treasury and EBS Spot FX datasets but requires appropriate access and licenses. **No CME historical tick data is included.**
- No BLS-surprise consensus nor same-contract USD OIS intraday quotes have been sourced or certified.

## Verified one-hour transport path (not a licence certification)

The direct public BI5 path for **EUR/USD, 2 October 2026, 12:00–12:59 UTC** is:

`https://datafeed.dukascopy.com/datafeed/EURUSD/2026/09/02/12h_ticks.bi5`

The `09` is Dukascopy's zero-based October month index; it must not be read as 2 September. On 23 October 2026 the endpoint returned HTTP 200 with `Content-Type: application/octet-stream`, `Content-Length: 58963`, `ETag: "6abfab26-e653"`, and `Last-Modified: Fri, 02 Oct 2026 13:01:26 GMT`. This is an auditable transport observation, not a price assertion.

`v2_dukascopy_bi5_hour_probe_v1.py` is the alternative bounded route: it obtains one exact binary hour, verifies the HTTP byte count, decodes the documented 20-byte BI5 records, derives timestamps from the URL rather than a hard-coded date, hashes the bytes, and selects only the last quote no more than two minutes before 12:25 and 12:35 UTC. Its receipt includes the HTTP metadata and byte hash. It remains read-only and never stores source ticks in the repository.

Public reachability, a response hash, and an HTTP receipt do **not** establish redistribution rights or a research/trading licence. The module therefore records `source_license_independently_certified: false` and `usage_authorization_not_established: true`; it does not convert the decoded observations into an approved historical dataset.

```bash
python -m validation.macro.v2_dukascopy_bi5_hour_probe_v1 \
  --source-url https://datafeed.dukascopy.com/datafeed/EURUSD/2026/09/02/12h_ticks.bi5 \
  --timeout-s 45 --out /tmp/macro-v2-shadow/eurusd-bi5-oct02-hour.json
```

## Import gate

`validation/macro/v2_eurusd_intraday_csv_research_v1.py` accepts a caller-provided CSV with `timestamp,bidPrice,askPrice`, original UTC time or timestamp with explicit offset (or Unix milliseconds). It **does not download anything**. Each release is mapped to exactly 08:30 New York on the original BLS announcement, and a pre/post reference is taken no more than two minutes before each target at 08:25/08:35.

Reject non-finite prices, inverted spreads, unsorted timestamps, timestamps without timezone, unsupported sources, or files outside a bounded single-day size. Record SHA-256 of supplied bytes and the exact time/price/spread. An author assertion that the data are licensed and time-stamped **is not independently verified authorization or evidence**.

Even with an accepted FX-only window, OIS, Treasury 2Y intraday and pre-release consensus remain unavailable. The output cannot certify causal impact, FX signals, scoring, production ingestion, or backtests.

Example after separately and lawfully acquiring **real** CSV:

```bash
python -m validation.macro.v2_eurusd_intraday_csv_research_v1 \
  --csv /tmp/eurusd-event-day.csv \
  --source-url https://www.dukascopy.com/swiss/english/marketwatch/historical/ \
  --usage-authorized --original-timestamps-reviewed \
  --out /tmp/macro-v2-shadow/eurusd-event-receipt.json
```

Only `/tmp` is a permitted output destination. No edits to `live_data`, `site`, `D.json`, the 28 pairs, current reports, or schedulers. Synthetic fixtures test the parser; **currently zero real EUR/USD event windows have been certified**.
