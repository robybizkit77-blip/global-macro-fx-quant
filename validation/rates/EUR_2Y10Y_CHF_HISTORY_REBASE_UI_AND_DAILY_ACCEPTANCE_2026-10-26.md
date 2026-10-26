# EUR 2Y/10Y — source rebase notice, CHF beta transparency, and daily rate producer acceptance (26 October 2026)

**Status of this PR: NOT A LIVE PROMOTION.** We prepare a safe source-history release and honest display of CHF reference-model changes. The existing public CHF level cannot be treated as a current actual Swiss government bond observation when it is beta-estimated from EUR.

## User-facing CHF interpretation

The approved v10 Rates panel already labels CHF as `Scenario β informativo` and `BASSA`. When a complete original ECB EUR 2Y/10Y history candidate is prepared, it now carries a *structured, independently source-bound* `historical_curve_rebase` receipt. The Rates view detects this receipt only when its publisher and source-rebase invariants are verified and shows one compact note **within the CHF row**:

> ANTEPRIMA RICERCA · La stima CHF basata sui rendimenti EUR 2Y/10Y è stata ricalcolata sullo storico BCE omogeneo. Una differenza rispetto alla versione precedente è una revisione dello scenario β, non un movimento osservato oggi sui titoli svizzeri. Affidabilità BASSA; tasso CHF ufficiale e data restano separati.

For an explicitly approved publication receipt, the prefix changes to **STORICO BCE RICALIBRATO** without a false claim of market movement. No note appears with the *old* public EUR rates history. It is presentation and data-provenance metadata only, never Core signals or FX pair scoring. The preview's research status cannot impersonate an approved release.

## Evidence and daily update contract

The offline ECB original publisher history constructor computes a SHA-256 fingerprint from the exact ordered **282 paired ECB 2Y+10Y observations**. It retains original separate ECB API CSV SHA-256s, historical start/end and source identity in the candidate's `historical_curve_rebase` metadata and marks `RESEARCH_CANDIDATE_NOT_PUBLISHED`.

An eventual *separate, source-reviewed* publication may set `history_status=FULL_ECB_SAME_BASIS_2Y_10Y_OFFICIAL_PUBLISHED`, `historical_curve_rebase.status=PUBLISHED_AFTER_SOURCE_AND_BROWSER_QA`, `requires_explicit_release=false` and retain the original audited fingerprint. The daily source guard then independently checks:

- Source raw CSV SHA-256s equal the known checked ECB 2Y/10Y official snapshots from PR #642.
- Exactly **282** paired rates from 2025-09-16 through 2026-10-22 remain unchanged (SHA-256 rebuilt from the arrays **before any newer append**).
- Both historical tenor arrays have identical strictly chronological calendar dates, remain current as-of, preserve the eight known publisher-verified October tail values and never redate yield observations.
- Recorded false PIT claim, non-market-move distinction and explicit approved status.
- All independently certified future daily ECB observations can append without reintroducing legacy data; any disagreement quarantines EUR **only** and leaves other G8 updates operational.

Tests include accepted synthetic contract fixtures (NOT asserted as real market data), an adversarial changed historical yield rejecting a fake approval, and refusal of the research-only candidate status.

## Verification and remaining release conditions

GitHub workflow `.github/workflows/eur-2y10y-v10-candidate-browser-v1.yml` is triggered by either frontend change or data constructor change, and compares exactly the old and original ECB candidate site on **1440px desktop / 390px mobile**. It must verify no visual overflow, unchanged latest EUR official rates, CHF BASSA label and the *new* source-rebase note appearing only on candidate.

**Still no live data change.** PR #644 proved that an isolated apply/rollback can be byte-identical and the original candidate changes CHF10Y by approximately +11.55bp as model calibration, not a market jump. This PR does NOT change official CHF yield, historical Core scores, 28 pairs, FX Beta, Forward, alert schedules or the active market pricing. Separately source-reviewed release remains required, including adapting the public-history publication status and ensuring after-release roundtrip/rollback plus UI on both viewports. The independent general v10 A–Z browser/calendar freshness issue remains open.
