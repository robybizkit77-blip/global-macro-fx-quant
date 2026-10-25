# Event → market: first EUR/USD intraday research bridge (25 October 2026)

**Status: shadow research only. This is not a live price collector, data licence, production News Pulse integration, measured policy surprise, or causal event study.**

## Scope
The existing `validation/macro/v2_dukascopy_bi5_hour_probe_v1.py` can acquire and decode a bounded hour of EUR/USD quotes, with SHA-256, byte count, HTTP provenance and two minute-aligned pre/post quotes. Its recorded 2 October 2026 transport experiment was successful, but vendor usage/redistribution permission was **not independently certified**.

`validation/news_event_window_research_pilot_v1.py` is a separate **local research adapter** that consumes an **already existing** BI5 probe receipt. It validates:
- same canonical EURUSD BI5 hour (zero-based month) and expected event target;
- original acquisition receipt, source URL, SHA-256 string, byte count and positive tick count;
- timezone-aware pre/post bid/ask in that exact source hour and on opposite sides of the nominated BLS release time;
- quotes within two minutes of targets T−5 and T+5 minutes, sensible bid/ask/mid, and matching quoted pip delta;
- strict fail closed on missing, contradictory, stale or future-in-the-hour/out-of-hour evidence.

Passing this bridge means **descriptive change of the EUR/USD mid between two dated quotes** only. It does **not** independently re-download/rehash source bytes, audit whether these were the best quote selections, certify the actual market dissemination time, validate surprise vs pre-release consensus, establish causality, or prove vendor rights.

All outputs permanently preserve:
- `source_usage_rights_independently_verified=false`
- `independently_verified_release_instant=false`
- `intraday_ois=NOT_AVAILABLE` and `intraday_government_2y=NOT_AVAILABLE`
- `market_reaction=NOT_CERTIFIED`; `causal_attribution=NOT_ESTABLISHED`
- `eligible_for_backtest=false`, `safe_to_publish_live_data=false`, `writes_live_data=false`

## How to replay a previously acquired probe receipt

If a **real** `/tmp/eurusd-bi5-oct02-hour.json` probe receipt already exists from a separately authorized/reviewed research acquisition:

```bash
python -m validation.news_event_window_research_pilot_v1 \
  --probe /tmp/eurusd-bi5-oct02-hour.json \
  --release-utc 2026-10-02T12:30:00Z \
  --official-event-url https://www.bls.gov/news.release/empsit.toc.htm \
  --out /tmp/gmfq-news-event-window-eurusd-research.json
```

The specified BLS URL is a public source **locator**, not independent validation of the actual 2 October first-disclosure instant. Do not promote the nominated calendar time to a verified market-news timestamp. A missing or mismatched receipt causes a nonzero exit. The converter neither fetches from the vendor nor saves to `live_data/` or `site/`.

The 14 focused automated tests use **synthetic sample receipts** (even when shaped like the historical experiment), not real market acquisition. CI is PR/dispatch-only; no schedules, new alert automations or public display changes.

## Next evidence gates (not completed by this PR)
1. Independent authorization/usage terms for intraday tick data and permissible publication, with a documentable source.
2. Retain/re-hash permitted raw bytes and re-select best quotes at event windows to independently validate receipt claims.
3. Establish official **actual** announcement/public-dissemination time (RSS `published_at_utc` is not sufficient).
4. Source comparable, timestamped OIS/futures and sovereign 2Y **same-instrument pre/post** snapshots; no substitution with daily values.
5. Align clocks, trading sessions, competing headlines and expected rate/FX response. Label all valid estimates observational, not necessarily causal.
6. Run on the **active** Control Room v10 Preview, not the legacy `dashboard/` page, only after the evidence and browser 1440/390 gates are satisfied.

**Isolation:** no modifications to score, 28 FX pairs, Beta, Forward Test, OIS models, rates certification, News Pulse production feed, or schedules.
