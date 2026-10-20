# CHF / SIX SARON — historical context, licensing and OIS source separation

Research-desk audit: **20 October 2026**. Sources: SIX Swiss Reference Rates official product index and the **FAQ as revised 1 July 2026**. This is a technical source-contract assessment, not legal advice or a SIX licence grant.

## Verified from the official SIX source
- SIX lists `SARON` (ISIN `CH0049613687`) as the CHF **overnight** reference fixing.
- SIX lists `SAR3MC` (`CH0477123902`), `SAR6MC` (`CH0477123910`) and `SAR12MC` (`CH0477123936`) as **SARON compound rates calculated in arrears**. Their 3/6/12-month labels denote the *past lookback period*, not a 3/6/12-month expected SNB policy path.
- SIX states that historical SARON is available free of charge, compound time series with a delay of at least **one CHF business day**.
- SIX FAQ Q9 permits redistribution of delayed historic SARON/compound observations subject to the relevant delay. This is a different question from what a user may create as a derivative research product or how automated retrieval is permitted.
- **Q10/Q11/Q14, revised 1 July 2026:** derived-data examples include yield curves and interest-rate analytics; separate conditions/licensing apply to derivative creation and external redistribution, even where the underlying reference rate is delayed. The precise application to a private, non-professional researcher using cloud scripts and a publicly accessible indicator-only GitHub Pages dashboard is **not independently cleared**. Do not assert that making output coarse/non-reversible is a sufficient exemption.
- SIX public pages document the product tickers, but this audit has NOT resolved an authenticated/unauthenticated bulk data endpoint, a complete timestamped CSV history, machine-download consent or a valid numeric as-of snapshot.

Official references:
- https://www.six-group.com/en/market-data/indices/switzerland/saron.html
- https://www.six-group.com/dam/download/market-data/indices/swiss-reference-rates/six-saron-faq-en.pdf

## Strict project taxonomy

| Item | Economic meaning | May substitute for OIS forward? |
|---|---|---|
| SARON daily overnight historical fixing | Realized CHF secured money-market overnight reference | **No** |
| SAR3MC / SAR6MC / SAR12MC | Backward-looking realized compounded financing rate | **No** |
| ICE SA3 **dated-contract** futures | Forward-looking, exchange-traded 3-month compounded SARON futures; contract-window proxy | Only after separate dated-contract and source-licensing certification; **not the same as spot OIS** |
| Real CHF OIS 3/6/12M curve | Market forward pricing for future funding/policy | Requires authorized and dated first-party OIS prices; **not present in this audit** |

A valid historical SARON fixing or compound value can be useful as **context**, but MUST NOT turn `CHF.official_status` to active, create a 1D/1W OIS repricing, or change pair preferences.

## Implemented gate
Files:
- `CHF_SIX_SARON_HISTORICAL_CONTEXT_SOURCE_CONTRACT_V1_2026-10-20.json`: official identifiers and documentary licensing/source status. **Contains no market rates.**
- `audit_chf_six_saron_context_v1.py`: fail-closed checker that only emits a non-numeric review receipt and rejects forward labels, changed ISINs, invented licensing rights, additional numeric fields, live-data writes and approval flags.
- `test_audit_chf_six_saron_context_v1.py`: 19 deterministic positive/negative tests.

Execute:
```bash
python -m unittest validation.cb_pricing.test_audit_chf_six_saron_context_v1 -v
python -m validation.cb_pricing.audit_chf_six_saron_context_v1 --out /tmp/chf-six-saron-context-audit.json
```

The audit is also tested in the **existing PR/manual-only**, unscheduled `Probe CHF SARON Public Sources V1` workflow. Its source state is **WITHHELD** and cannot be promoted by a GREEN workflow.

**No data acquisition, scraping, price download, backtest, new daily refresh, report feed, Production OIS_DATA, `OIS_OPERATIONAL_VIEW.json`, active or legacy website, Macro scoring or FX pair states changed. No ChatGPT automations created.**

## Required next evidence
1. Obtain precise SIX terms for *private personal* use of delayed compound history in internal scripts (including GitHub cloud execution) and publication of direction-only research descriptions/derived figures.
2. Identify and verify an official historical download path, dates, release times and content hashes without circumventing login/access controls.
3. Keep historical rate context clearly labeled with its actual observation and publication lag; do not silently create a future policy path.
4. Continue **independent** ICE SA3 free-access and non-reversible output licensing inquiry, and never use a one-day sample to fabricate T−1/T−5.

Do not create automatic ingestion or display until applicable source rights and complete as-of data are documented.
