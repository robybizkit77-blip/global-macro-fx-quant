# Forward V2 quality-aware — Contract indipendente, futuro-only

**Protocollo:** `GMFQ_V2_QUALITY_AWARE_OBSERVATIONAL_FREEZE_V1`  
**Preregistrato:** venerdì 30 ottobre 2026; **prima osservazione reale ammissibile:** lunedì **2 novembre 2026**, dopo le **19:00 Europe/Rome**.  
**Journal nuovo, separato:** `validation/forward/candidate_shadow_snapshots/V2_QUALITY_AWARE_PROSPECTIVE_SNAPSHOTS_V1.jsonl`. Non importare o riscrivere il journal `V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl`.

## Problema di misurazione

L'EUR disoccupazione 6,5% di settembre 2026 è sopra tutti i 24 valori mensili precedenti, ma `MAD=0` quando gli ultimi 24 valori sono tutti 6,3% o 6,4%. Lo z-score robusto non è definito, per cui il contratto numerico V2 originale **deve rifiutare** il candidato, come ha fatto. Non sostituire la scala con deviazione standard, IQR, epsilon, numero arbitrario o percentili.

**Nuovo obiettivo:** raccogliere *evidenza economica descrittiva* prospettica, non costruire un diverso modello di valuta.

## Dati congelati solo al vero cutoff

1. Il gate preesistente `assess` richiede prezzo ufficiale ECB **della stessa data**, tutte le **28 coppie** e l'audit dei prezzi/G8 coerente con il Core già esistente. Il tempo è verificato con clock UTC-aware, cutoff locale Roma da lunedì a venerdì dopo le 19:00, non più di cinque minuti fra cutoff/ora.
2. Ricalcola contestualmente `GMFQ_MACRO_V2_OBSERVED_G8_FEATURE_BRIDGE_V1` direttamente dai dati correnti. Conserva **8 Growth QGDP publisher-web**, **8 inflazione**, **8 lavoro**, senza interpolare status negativi e senza usare informazioni successive per costruire rendimenti futuri.
3. Se `research_robust_z=null` il campo rimane **null**. Se lo status è `NO_Z_ZERO_ROBUST_DISPERSION` registra a parte i descrittori del protocollo `V2-ZERO-MAD-ORDINAL-QUALITY-V1`, incluse ampiezza in unità economiche e rango; questi non diventano z, FX score, crescita in classi né input H1.
4. Registra **28 ECB T0 cross non eseguibili**, la data e l'orientamento. Non registra il rendimento futuro, non converte le osservazioni in side o PnL. I dati `MACRO_SERIES` sono archivi **revised** e i periodi economici non sono timestamp di rilascio. Non rivendicare PIT storico.
5. Registra sha256 dei sei file sorgente (ECB, Pair Setup, Core, Macro Series, thermometer, registry), fingerprint del bridge e del protocollo ordinal, timestamp UTC di osservazione, `snapshot_sha256` e `snapshot_id`. Stesso giorno: **idempotenza senza overwrite**; journal preesistente viene autenticato prima di append.
6. `can_feed_preregistered_H1=false`, `V2_numeric_model_computed=false`, `V2_FX_signal_computed=false`, `eligible_for_beta_forward_trading=false`. È un nuovo **cohort** di qualità, non può essere trattato come una continuazione identica del V2 originario.

## Esecuzione con job già esistente

Si riutilizza `Forward Frozen Core Prospective Daily V1`, senza creare pianificazioni o automazioni aggiuntive. Ordine:
- Frozen Core primario scritto;
- tentativo del V2 **originale** immutato, che può rimanere RED su MAD zero;
- tentativo del nuovo quality-aware V2, **solo dal 02/11**;
- audit dei soli journal permessi, commit append-only su `main`;
- certificazione nuova osservazione (errore visibile dopo il commit se manca);
- certificazione del V2 originale **indipendente e invariata** (può restare RED: un nuovo quality-aware non lo rende valido).

Un run scheduled/cadence positivo non attesta il giornale se il T0 non è stato pubblicato. L'orario è quello vero dell'azione, non uno snapshot inventato o backfill. Nessuna autorizzazione a generare report pubblici o nuovi signals.

## Validazione e falsificazione

- Test sintetico futuro **in memoria e in cartella temporanea** su 8 G8 × 3 dimensioni, 28 fixing, z nullo, idempotenza, tampering, spoofing, ECB T0 stale, weekend/pre-registrazione e niente H1.
- Test della lettura effettiva Macro V2 dal repository, ma non una cattura storica reale.
- Solo dopo il primo run futuro reale con ECB T0 corrente e commit verificato possiamo affermare che la **raccolta prospettica** funziona; non che il modello predice FX.
- 120 giorni distinti e benchmark H1 si applicano **solo al vecchio protocollo H1**, che non importa questo journal. Nuove ipotesi quantitative su questo cohort richiederanno nuova preregistrazione senza selezionare pesi ex-post.

**Protezione:** nessuna modifica a `D.json`, alle 28 coppie, a `V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl`, alla soglia H1 o ai workflow delle 08:00.

## Addendum — congelamento congiunto Macro → Rates (30 ottobre, prima del primo T0)

Il cohort futuro-only **dal 2 novembre** acquisisce anche un *market context* verificabile, distinto da un Core FX:

- 8 valute: policy rate e data della banca centrale, rendimenti sovrani 2Y/10Y con data e qualità, e orizzonte monetario 6M con fonte, data e tier **ufficiale / futures stimato / futures secondario / bank-bill NZD / non disponibile**. Dati vecchi rimangono esplicitamente storici; mai rinfrescarli modificandone la data.
- 28 orientamenti canonici: spread 2Y descrittivo **solo** se le due quotazioni ufficiali condividono il medesimo giorno. Un confronto 6M tra differenti indici, futures o bank bill viene lasciato **null**, non finto spread OIS. Il 2Y non è una previsione FX.
- Quattro input aggiuntivi ricevono SHA256: `NATIVE_RATES_DATA`, `OIS_OPERATIONAL_VIEW`, `NATIVE_CB_DATA`, `NZD_CB_PRICING_DIRECTIONAL_PROXY`. Il digest del market context e tutti questi input sono nel `snapshot_id`; il validatore impedisce di risigillare un differenziale su date non corrispondenti o una stima come OIS ufficiale.
- **Zero nuovi bias, zero segnali, zero rendimenti futuri, zero modifica a D.json/Beta/Forward H1.** È un snapshot delle informazioni osservabili *al momento della cattura*, non un database storico point-in-time.
- Le quattro fonti sono congelate nel medesimo cutoff dell'ECB T0; la cattura resta esclusivamente futura e il vecchio journal V2 numerico rimane indipendente, anche se RED per MAD=0. Non aggiunge cron o automazioni.

Questo addendum è preregistrato prima del primo snapshot ammissibile. Non usare tali colonne per ottimizzare pesi a posteriori. Un eventuale modello relativo Macro→Rates→FX richiederà una successiva ipotesi versionata, osservazioni indipendenti maturate e verifica OOS.
