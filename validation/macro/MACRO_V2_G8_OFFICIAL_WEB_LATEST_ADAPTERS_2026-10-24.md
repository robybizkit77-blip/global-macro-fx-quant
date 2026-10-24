# Macro V2 — G8: nine additional official-web anchors and exact quarterly periods

**24 October 2026 · Source evidence only; no production Macro score.**

## Practical improvement

This change reuses the existing **reviewed** official-publisher web attestations instead of spending another cycle adding single EUR months. Nine new source-specific candidates can be onboarded simultaneously into the **same shared 24-slot G8 PIT control plane** from PR #589:

| Currency | Pillar | Registered or candidate series | Web-attested observation | Publisher | Important limitation |
| --- | --- | --- | --- | --- | --- |
| USD | Inflation | `CPIAUCSL` | Sep 2026, **336.298** CPI-U **SA index** | BLS | Annual rate ~3.7173% is a separate derived calculation: not the index value, and not headline NSA CPI |
| CAD | Inflation | `CA_CPI_HEADLINE_YOY` | Sep 2026, **3.0927835% derived** from 170.0/164.9 | Statistics Canada | First-web evidence for the underlying index pair; 3.1% is publisher-rounded annual inflation, derived precision is not directly reported as such |
| AUD | Labour | `AU_UNEMP_RATE` | Sep 2026, **4.7% SA** | ABS | One report; verified 15 Oct 11:30 **AEDT (+11)** |
| CAD | Labour | `CA_UNEMP_RATE` | Sep 2026, **6.5% SA** | Statistics Canada | Date only, no intraday UTC claim |
| JPY | Labour | `JP_UNEMP_RATE` | Aug 2026, **2.5% SA** | Statistics Bureau of Japan | Source URL is a mutable publisher index, not archived original-day HTML |
| GBP | Inflation | `D7G7` | Sep 2026, **3.5% CPI** | ONS | UK CPI, **not CPIH**; only one release |
| NZD | Inflation | `NZ_CPI_HEADLINE_YOY` | **2026Q3**, **3.7% YoY** | Stats NZ | Quarter-ending September, **not a monthly release** |
| AUD | Growth | `AU_REAL_GDP_QOQ_ABS_history_value` | **2026Q2**, **+0.4% QoQ** | ABS | Not yet selected as canonical Growth series; signed 2 Sep 11:30 AEST source clock |
| NZD | Growth | `NZ_REAL_GDP_Q_history_value` | **2026Q2**, **+2.6% same-quarter YoY** | Stats NZ | Not comparable to AUD GDP QoQ or NZD GDP four-quarter average (1.7%); unverified intraday clock |

The latest **GBP Labour** attestation is already represented by three ONS first-web report windows in PR #589. Its value, source URL and 20 Oct date are checked against the latest official anchor and **not double-counted**.

### Scientific rules

- Existing reviewed anchor fixtures are independently crosschecked against **hard-coded expected source IDs, reference periods, original publisher URLs, first-release dates, original source index pairs, numerical values and transformations**; changes fail CI.
- **Quarterly `YYYYQn` periods are first-class**: `2026Q3` for NZD CPI; `2026Q2` for the AUD/NZD GDP releases. The shared source validator uses the original quarterly period start rather than attempting to parse a nonexistent month.
- Original publisher local release clocks for BLS and ABS retain verified UTC offsets; sources with only a verified **date** use conservative **00:00 UTC the following calendar day**, *not* a guessed market-hour timestamp.
- Do not pretend data sourced from an index ratio were directly **reported** with all unrounded digits. Do not treat a source with matched canonical ID as score-ready.
- GDP Growth series **remain unselected** in the canonical registry. No replacement of any legacy `D.json` score or macro component is authorized.
- Source-specific first web attestations are **not** archived immutable initial-day bytes, complete revisions, OIS/2Y/FX event studies, or validated historical score data.

## New control-plane scope

| Measure | PR #589 | This PR |
| --- | ---: | ---: |
| Observed G8 currency/pillar slots inventoried | 24 | 24 |
| Source-specific research evidence streams connected | 4 | **13** |
| Slots still awaiting common adapter | 20 | **11** |
| Distinct source-specific initial-web reference periods | 49 | **58** |
| Dated first/detailed headline publication records in shared controller | 59 | **68** |
| Independently certified complete canonical PIT histories | 0 | **0** |
| Approved new Macro scores/FX pair updates | 0 | **0** |

The shared count **does not** count historical Eurostat subcomponent revisions/corrigenda or other detailed modules' retrospective statements as *extra first-release months*. Legacy current observations exist for all 24 slots; unconnected **does not mean missing macro data**.

## Reproduce

```bash
python -m unittest validation.macro.test_v2_pit_g8_control_plane_v1 -v
python -m unittest validation.macro.test_v2_pit_g8_latest_web_adapters_v1 -v
python -m validation.macro.v2_pit_g8_control_plane_v1 \
  --asof 2026-10-24T00:00:00Z \
  --json-out /tmp/macro-v2-shadow/g8-common-13-source-anchors.json \
  --markdown-out /tmp/macro-v2-shadow/g8-common-13-source-anchors.md
```

**No automatic downloader, cron, alert or new scheduler.** This is a reusable, isolated source gateway. All test receipts stay in `/tmp`. The Control Room, 28-pair rankings, live feeds, score formula, model baselines and trading logic are unchanged.
