# EUR 2Y + 10Y source restoration: official ECB research candidate (26 Oct 2026)

**Status: SOURCE-PARITY VERIFIED, CANDIDATE ONLY. NOT applied to active Control Room.**

## Why a whole-series correction, not a few manual values

The active `NATIVE_RATES_DATA.json` EUR entry explicitly marks `history2_quality = LEGACY_NOT_SAME_BASIS_WITH_VALIDATED_25SEP` and `history_status = SEPARATE_BASIS_CURRENT_SNAPSHOT_NOT_SPLICED`. The current operational `validation/run_rates_audit.py` looks up the most recent official 2Y/10Y observations via `validation/fetch_rates_eur_gbp.py`; `validation/build_rates_candidate_from_audit.py` only appends an advancing latest observation. **Neither checks old historical value-by-value parity**. This procedural gap allows a legacy/non-equivalent history to coexist with a correct new source snapshot. The actual initial historical value construction or original curve transformation has not been conclusively located.

Independent original ECB API CSVs checked in [PR #642](https://github.com/robybizkit77-blip/global-macro-fx-quant/pull/642) both correspond to the ECB AAA Svensson spot curve: source keys
`YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y` and
`YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`,
from 2025-09-16 to 2026-10-22 (original first-release PIT timestamp not independently attested).

| | EUR 2Y | EUR 10Y |
|---|---:|---:|
| Mirror observations | 271 | 271 |
| Publisher original observations | 282 | 282 |
| Exactly same-day overlaps | 271 | 271 |
| **Mismatched existing observations** | **260** | **260** |
| Missing publisher days in the mirror | 11 | 11 |
| Largest absolute rate gap | 15.52485 bp | 48.29169 bp |
| Original ECB raw CSV SHA-256 | `2d5b0e884b0d3728c29d935e0982e761896102bd401f4ae406a17680f6079bab` | `c536410864ee8f873533509167ab350a189ed0987201b09b490f158aa85b9b4e` |

The eleven missing publication dates in **both** historical tenors: 2026-09-23, 09-24, 09-25, 09-28, 09-29, 09-30, 10-05, 10-07, 10-08, 10-09, and 10-12.

**Important: the 2026-10-22 latest official EUR levels already match the ECB original source.** Research candidate weekly changes remain 2Y **+1.5 bp**, 10Y **−0.6 bp**, with latest curve **+37.7 bp**. Existing EUR 5Y and 30Y tenors still have their own 2026-09-25 observation date and have **not** been made contemporaneous by this source repair.

## Implementation and source proof

`validation/rates/build_eur_full_2y_10y_ecb_history_candidate_v1.py` takes both **independent original ECB CSV byte files**, verifies explicit curve-series key, 2Y/10Y same-day complete date calendar, entire historical coverage, current source snapshot identity, units and numerical values. It constructs a full official **282-day pair of aligned historical yield series**, recomputes EUR weekly changes/curve on the same published basis, and updates only EUR history metadata in the research candidate. Every other G8 rate, the last official EUR 2Y/10Y, and EUR 5Y/30Y remain unchanged.

The two CSVs and source candidate/receipt live in `/tmp` on the GitHub Actions runner. Their SHA hashes and summary are printed to its immutable run logs. No original ECB publication bytes are committed into the site repo; no backdated market price is interpolated. **CI GREEN is a source/contract assertion, not a licence to change the active public site immediately.**

`validation/rates/audit_eur_2y_10y_site_consumer_impact_v1.py` checks five real downstream consumer classes against the **active** v10 code and a strictly scoped candidate:
- EUR historical government-yield charts;
- the CHF fallback `estimate(target,ref,which)` based on EUR 2Y/10Y (may change materially);
- FX G8 pair market-reaction diagnostics, including **the seven EUR crosses**;
- pair-level observed yield-change audit;
- legacy rates and homepage yield plots.

Those consumers read `history2/history10` directly. **They have not yet been browser/functional impact tested with the replacement feed**; no claim is made that their changes are harmless. The live EUR current rates and latest weekly changes do not move in the tested snapshot; historic charts and proxy estimates may.

## Why the active publication remains blocked

The automated impact gate reports `CONTROLLED_RELEASE_REQUIRED_NO_AUTO_PROMOTION`, `safe_to_publish_now=false`. Required prior steps:
1. Run actual derived CHF reference-beta sensitivity **old vs proposed**, and inspect estimates/threshold crossings; ensure empirical accuracy is not invented.
2. Run actual active 28-pair reaction and recent change comparison, not just static code search.
3. Validate active Control Room v10 **at 1440px and 390px**, including rates chart changes, labels and source dates.
4. Dry-run `update_live_direct_section`, rebuild manifest/payload and verify byte/semantic integrity in CI with a rollback candidate, **before** proposing source-controlled live promotion.
5. Ensure the persistent daily official Rates updater does not subsequently reintroduce non-equivalent historical values; its latest-only `run_rates_audit.py` validation is not an historic-source audit.
6. Add a future full-history parity gate or safe incremental consistency checks that do not hold the critical **08:00 website refresh** hostage to slow historical downloads.

Original model baseline, Beta promotion, trading P&L, 28-pair canonical scoring/rank, Forward results and 08:00 orchestration remain untouched. Full historical publisher values from today **do not independently prove first-release point-in-time availability**.

## Reproduce independent original ECB source validation

```bash
python -m unittest validation.rates.test_build_eur_full_2y_10y_ecb_history_candidate_v1 -v
python -m unittest validation.rates.test_audit_eur_2y_10y_site_consumer_impact_v1 -v
python -m validation.rates.build_eur_full_2y_10y_ecb_history_candidate_v1 \
 --ecb-2y-original /tmp/eur-aaa-2y-original.csv \
 --ecb-10y-original /tmp/eur-aaa-10y-original.csv \
 --candidate /tmp/gmfq-eur-full-history-source-candidate.json \
 --receipt /tmp/gmfq-eur-2y-10y-parity-receipt.json
python -m validation.rates.audit_eur_2y_10y_site_consumer_impact_v1 \
 --candidate /tmp/gmfq-eur-full-history-source-candidate.json \
 --out /tmp/gmfq-eur2y-10y-site-impact.json
```

The original ECB URLs are in `.github/workflows/eur-ecb-full-2y-10y-source-audit-v1.yml`. The CI remains **unscheduled** and does not modify the public mirror.

## Progress interpretation

The 28/28 Beta FX shadow coverage from PR #641 **only** establishes computability for a historical pseudo-OOS experiment on current original BCE/MoF histories. This candidate addresses **data-source consistency**, not the remaining B1/B2 rules, robust statistical sample-depth, benchmark comparability, actual trade performance, live publisher source repair, or the mandatory final end-to-end Control Room collaudo.
