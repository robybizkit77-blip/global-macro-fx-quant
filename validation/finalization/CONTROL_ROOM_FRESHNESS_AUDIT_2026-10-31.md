# Control Room v10 — audit di freschezza e coerenza (31 ottobre 2026)

**Modalità:** osservazionale/read-only, riferimento a `main` e al branch `gh-pages` controllati il 31/10/2026. Questo documento è un'istantanea dell'audit, non un certificato della consegna HTTP pubblica né un nuovo modello FX.

## 1. Risultato della catena dati

- **16/16 file chiave** confrontati tra le directory `live_data/sections` di `main` e `gh-pages`: **Git blob SHA identici** in entrambi i branch. Elenco: `D`, `MACRO_SERIES`, `MACRO_THERMOMETER_DATA`, `NATIVE_RATES_DATA`, `OIS_OPERATIONAL_VIEW`, `OIS_DATA`, `NATIVE_CB_DATA`, `PAIR_SETUP_OPERATIONAL_VIEW`, `ECB_G8_PRICE_HISTORY`, `V250_COT_CHART_DATA`, `V247_COT_STORIES`, `OIS_SOURCE_READINESS_VIEW`, `RATES_AUDIT_METADATA`, `ESTIMATED_RESIDUAL_GAPS`, `WHAT_CHANGED`, `NZD_CB_PRICING_DIRECTIONAL_PROXY`.
- Questo dimostra soltanto la **parità dei blob del repository**: non prova disponibilità via CDN, corretta esecuzione JavaScript in browser, SLA delle 08:00, né timing di aggiornamento.
- Il controllo HTTP esterno del sito non è stato completato in questa sessione: **NON CERTIFICATO**.
- `PAIR_SETUP_OPERATIONAL_VIEW.json`: `price_asof=2026-10-30`, `macro_baseline_asof=2026-09-25`; 28/28 coppie, audit prezzi PASS. `D.json` conferma `asOf=2026-09-25`.
- **Nessun aggiornamento del Core**: lo scostamento Macro/prezzi va mostrato come storico, non nascosto o interpretato come un errore di sincronizzazione dei fixing.

## 2. Matrice G8 — data dell'informazione, non data di pubblicazione del sito

| Valuta | Macro inflazione (periodo) | Macro lavoro (periodo) | 2Y/10Y ufficiale, ultima data in feed | Pricing 3/6/12M per ricerca |
|---|---|---|---|---|
| USD | 2026-09 | 2026-09 | 2026-10-29 | Futures stimato, 2026-10-30 |
| EUR | 2026-09 | 2026-09 | 2026-10-29 | Futures indicativi **misti 29/30 ottobre**, NON curva OIS sincronizzata |
| GBP | 2026-09 | 2026-08 | 2026-10-29 | Fonte monetaria certificata, 2026-10-29 |
| JPY | 2026-09 | 2026-09 | 2026-10-29 | Fonte monetaria certificata, 2026-10-30 |
| CHF | 2026-09 | 2026-09 | **2026-09-30, storico** | Futures stimato, 2026-10-30 |
| CAD | 2026-09 | 2026-09 | 2026-10-29 | Fonte monetaria certificata, 2026-10-29 |
| AUD | 2026-09 | 2026-09 | 2026-10-28 (cadence RBA F2) | Fonte monetaria certificata, 2026-10-29 |
| NZD | 2026-09 | **2026-06** | **2026-10-16, storico / review manuale** | Bank-bill 2026-10-30 + scenario empirico, NON OCR OIS ufficiale |

Le date Macro sono **periodi economici** (non primo timestamp di pubblicazione, né vintage storiche PIT certificate). Il termometro `MACRO_THERMOMETER_DATA` è un layer separato dal Core strutturale, da non promuovere automaticamente.

## 3. Differenze di qualità che devono restare esplicite

1. **Rates CHF/NZD:** `NATIVE_RATES_DATA` conserva `freshness_status` terminante in `CURRENT_OFFICIAL_SAME_BASIS` anche su date storiche 30/09 e 16/10. `RATES_AUDIT_METADATA` distingue correttamente `VALIDATED_HISTORICAL_OFFICIAL_SNAPSHOT` (CHF) e `MANUAL_REVIEWED_LAGGING` (NZD). Verificare i consumer e, in un intervento separato con regressioni, eliminare l'ambiguità nominale se può propagarsi a UI o downstream. Non riscrivere date o tassi.
2. **OIS:** `OIS_OPERATIONAL_VIEW` ha 4 G8 `GREEN_OFFICIAL` (GBP/JPY/CAD/AUD), 2 `GREEN_ESTIMATED` (USD/CHF), EUR e NZD `WITHHELD` come **curve ufficiali**. La UI di ricerca ha percorsi distinti per contratti EUR datati non sincronizzati e scenario NZD bank-bill con banda; questi **non** equivalgono a OIS ufficiali né consentono policy delta o H1. Non proclamare 8/8 OIS ufficiali.
3. **COT:** 8/8 serie CFTC con ultima osservazione **martedì 27/10**, 104 settimane; data fisiologicamente diversa dal fixing BCE **venerdì 30/10**. `V247_COT_STORIES` conserva `price=WITHHELD` per tutte le 8 valute perché il refresh CFTC non ha certificato la conferma prezzo. È **contesto prezzo non valutato**, non assenza di storico FX. Miglioria da valutare: contesto FX BCE read-only **separato** per data, senza attribuire causalità o validare segnali.
4. **CB:** `NATIVE_CB_DATA` conserva le date delle **ultime decisioni**, non necessariamente la data di refresh giornaliero dei tassi; per esempio GBP 17/09 e AUD 29/09 non sono da soli indizi di feed rotto.
5. **Storia Macro V2:** il precedente triage documenta 22/24 finestre first-web numericamente continue, ma **0/24 PIT storici completi certificati**. USD CPI/labour ottobre 2025 non pubblicati non devono essere interpolati; SECO CHF arrotondato non sostituisce vintage SNB precisa.

## 4. Azioni ordinate per evidenza (senza nuove funzioni)

| Priorità | Azione | Condizione di chiusura |
|---|---|---|
| P0 · lunedì 2/11 ore 08:00 | SLA autonomo, fonte → main → gh-pages → HTTP/browser pubblico, data/ora reali e JPY/CB se rilevanti | Run effettivo e pagina raggiungibile **entro** 08:00; un run GREEN tardivo non vale |
| P0 · lunedì 2/11 dopo 19:00 | Prima osservazione prospettica Quality-Aware Macro V2 | ECB fixing T0 **2/11**, 28 cross, dati/qualità G8, hash e commit append-only realmente presenti; nessuna promozione Core |
| P1 | Controllo semantico labels Rates CHF/NZD | Nessun `CURRENT` interpretato come data recente da UI, export o ricerca; test conservativo |
| P1 | Coverage OIS stimati vs ufficiali | 8 righe visibili con 3M/6M/12M quando supportato; date non sincronizzate mostrate come punti, NZD scenario con banda, nessuna falsa certificazione |
| P1 | COT prezzo read-only | Aggiungere contesto BCE distinto dalla validazione COT/prezzo, solo con timestamp e data corretti; senza segnali |
| P1 | Nuova candidatura Macro strutturale | Scoring versionato e confronto G8/28 con il 25/09, analisi sensibilità e provenienza; **non** applicare `D.json` finché non passa il gate PIT |

## 5. Limiti e governance

Questo audit non ha testato l'HTML realmente eseguito nel browser, non attesta aggiornamenti delle fonti ufficiali oltre le date archiviate e non ha eseguito nuovi backtest. Non modificare automaticamente `D.json`, score, ranking 28 coppie, forward H1, Cron o provider-derived currentness sulla sola base di questo report. Nessun `WITHHELD` deve essere sostituito da un numero inventato: un riferimento stimato rimane etichettato e datato.
