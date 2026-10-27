# Macro V2 — riconciliazione delle quattro fonti non equivalenti (27 ottobre 2026)

## Perché non sono tutte lo stesso problema

La pipeline corrente produce **12/16 source ID + frequenza uguali**, ma le altre **4/16** vanno qualificate con prove specifiche. Il controllo `v2_g8_source_semantic_reconciliation_v1.py` confronta rigorosamente **identificatore, frequenza, publisher, dossier originale** e impedisce ogni promozione automatica.

| Valuta | Canonical Core | Candidato web attuale | Decisione vincolante |
|---|---|---|---|
| 🇺🇸 USD Labour | `UNRATE` mensile | `LNS14000000` mensile | **Stessa genealogia statistica**, provata da FRED: UNRATE è il tasso U-3 BLS fonte LNS14000000. *Non* prova l'equivalenza dei **vintage values** e non ricostruisce ottobre 2025 mancante |
| 🇪🇺 EUR Inflation | `EA_HICP_HEADLINE_YOY` mensile | `EA_HICP_HEADLINE_YOY_history_value` mensile | **Alias del dossier di ricerca** per il medesimo HICP headline YoY first-flash Eurostat; verificata anche una ricevuta separata di 105 mesi (2018-01–2026-09), ma i 105 eventi non sono materializzati nel ledger corrente. EA20→EA21/ECOICOP resta discontinuità da controllare |
| 🇦🇺 AUD Inflation | `AU_CPI_HEADLINE_Q_YOY` trimestrale | `AU_CPI_HEADLINE_M_YOY_context_value` mensile | **NON EQUIVALENTI**. Esiste una ricevuta trimestrale di **34 quarterly initial releases** (2018Q1–2026Q2, evidenza separata) da acquisire come stream canonico. Il mensile resterà contesto economico, mai sostituto |
| 🇨🇭 CHF Labour | `CH_UNEMP_RATE` mensile SNB | `CH_SECO_SA_REGISTERED_UNEMP_RATE_ONE_DECIMAL` mensile SECO | **NON EQUIVALENTI al livello di precisione**. Il comunicato ufficiale mostra 3,1%, la serie SNB retrospettiva ~3,124988%. L'arrotondamento perde informazione: non si può inventare il valore esatto first release né assumere che l'ultimo ETag SNB certificasse il valore alla pubblicazione |

Fonti e file audit:
- USD <https://fred.stlouisfed.org/series/UNRATE>, e `validation/macro/MACRO_V2_US_BLS_25_FIRST_RELEASE_PILOT_2026-10-23.md`; una lineage verificata **non** equivale a first-day immutable HTML.
- EUR `validation/macro/eur_inflation_strict_pit_evidence_v1_2026-10-10.json`, pubblicazioni ufficiali Eurostat, senza trattare 105 mesi riassunti nel *receipt* come 105 eventi già importati.
- AUD `validation/macro/aud_inflation_strict_pit_evidence_v1_2026-10-09.json`; distinta dal dossier di 11 comunicati monthly ABS post ott-2025.
- CHF `validation/macro/CHF_LABOUR_SECO_SNB_TEMPORAL_PROVENANCE_2026-10-22.md`.

## Cosa è stato realmente risolto

- **2 identificazioni concettuali documentate** (USD, EUR). Nessun nuovo indice economico creato per esse.
- **2 impedimenti numerici veri, non aggirabili per alias** (AUD, CHF), ora bloccati esplicitamente dal codice con remediation specifica.
- **0 catene PIT sincronizzate nuove**, **0 import dei 105/34 periodi** dai ricevuti nel ledger giornaliero, **0 score Macro FX certificati**.

## Lavoro successivo, reale e misurabile

1. **AUD:** importare nel nuovo ledger gli originali delle 34 uscite trimestrali documentate, con date, metrica e proof bytes/hash, e validare Q→Q senza alcuna interpolazione mensile.
2. **EUR:** riconciliare i 105 record flash già attestati con l'attuale stream di 10 mesi e la transizione di Eurozona, senza raddoppiarne i periodi o rivedere retroattivamente le date.
3. **USD:** mantenere il documento FRED di genealogia ma ricostruire il primo valore BLS mese per mese, inclusi gli effetti dello shutdown 2025 e le revisioni.
4. **CHF:** acquisire davvero snapshot SNB originali con timestamp/provenienza puntuali oppure usare solo il dato SECO arrotondato **esplicitamente come metrica alternativa, mai come core SNB esatto**.

Il sistema resta read-only. `D.json` 25 settembre, 28 coppie, Beta, Forward e sito NON vengono cambiati.
