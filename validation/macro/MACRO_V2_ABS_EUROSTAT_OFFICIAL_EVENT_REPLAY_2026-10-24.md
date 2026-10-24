# Macro V2 — ABS & Eurostat: bounded official publication-event replay

**24 ottobre 2026 · Shadow research, non produzione**

## Economic interpretation

The release date, not the reference-period end, gates information availability. The pilot covers **three series**, **three different reference periods**, and **six published metric-event records** across **four distinct publisher release events**: ABS 26 August / 30 September 2026 and Eurostat 2 / 16 October 2026.

- **AUD CPI headline**: July 3.5% YoY (26 Aug at 11:30 AEST), August 4.0% YoY (30 Sep at 11:30 AEST). Two period-specific first web releases; the latest observation alone must not be visible at a 26 August cutoff.
- **AUD CPI trimmed mean**: July 3.6% YoY (26 Aug), August 3.6% YoY (30 Sep), no change in the *reported* annual rate. Preserve the seasonally-adjusted contextual series identity.
- **EUR HICP headline**: September flash 3.8% (2 Oct), detailed publication 3.8% (16 Oct). The later publication is **not** a demonstrated numerical revision of the headline, because the same metric stayed 3.8%.

## Temporal and provenance controls

1. For ABS, the original official local timestamp is included as `+10:00`; 11:30 AEST is 01:30 UTC. The event is visible at its exact official release timestamp, never before.
2. For Eurostat, the official date but not an independently verified **clock time** is stored. To prevent lookahead, the pilot conservatively delays availability until **00:00 UTC on the following day**. That is an analysis gate, **not** the actual Eurostat publication hour. Not suitable for a same-day event study.
3. The `kind` is kept as publication stage (initial/flash/detailed), **not** an assumption that a data revision took place. To verify revised vintages for old periods, original releases listing those periods must be compared directly.
4. Each original source URL is period-specific and restricted to ABS or Eurostat. Values, periods, units, URLs, and timestamps are independently pinned in the validator, not simply trusted from the JSON.
5. These source web pages may be changed after initial publication and **no original release-day source bytes were captured**. The current observation history is not a historical point-in-time repository.

## Research-gate status

This proves a **small, web-attested event-ordering/replay mechanic**, not complete PIT training. We have 2 consecutive initial months for the AUD CPI headline/trimmed mean and 1 reference month with a flash/detailed sequence for EUR HICP. At least **25 monthly first releases** per selected monthly series, source preservation, missing-value/revision checks, and independent PIT review are needed before considering normalization/backtests; there is no approval to compute macro/currency strength scores.

### Read-only audit

```bash
python -m unittest validation.macro.test_v2_abs_eurostat_publication_event_replay_v1 -v
python -m validation.macro.v2_abs_eurostat_publication_event_replay_v1 --asof 2026-10-02T23:59:59Z --out /tmp/macro-v2-shadow/abs-eurostat-before-flash-gate.json
python -m validation.macro.v2_abs_eurostat_publication_event_replay_v1 --asof 2026-10-24T00:00:00Z --out /tmp/macro-v2-shadow/abs-eurostat-event-replay.json
```

The code never writes `live_data/`, `site/`, `payload/`, or `dashboard/`. No scheduled automation, feed substitution, 28-pair change, new score or trading signal. No silent fabricated `WITHHELD` estimation: **missing historical releases remain a scientific limitation of the model**, not missing current market observations.

## Official sources

- ABS July 2026 CPI: https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jul-2026
- ABS August 2026 CPI: https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/aug-2026
- Eurostat September flash: https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-02102026-ap
- Eurostat September detailed: https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-16102026-ap

## Next evidence

- Archive/recheck a continuous first-release chain for AUD headline + trimmed mean **without bridging the monthly/quarterly methodology transition blindly**.
- Eurostat: obtain more month-specific flash and detailed pages, compare detailed release revisions to prior months, verify any intraday time source independently.
- Add independent offline source artifacts with acquisition timestamps and hashes; *a hash acquired today does not turn an HTML page into a release-day PIT copy*.
