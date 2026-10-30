# Macro V2 — Regola preregistrata per dispersione robusta nulla

**ID:** `V2-ZERO-MAD-ORDINAL-QUALITY-V1`  
**Registrazione:** 30 ottobre 2026, versione bloccata nel commit merge della PR che introduce questo documento.  
**Primo giorno candidato per qualsiasi FUTURA acquisizione prospettica:** **2 novembre 2026, Europe/Rome**, subordinatamente a una futura approvazione tecnica della cattura. L'implementazione attuale **NON scrive alcun journal**.

## Domanda e ragione economica

Un dato osservato può essere al massimo degli ultimi 24 mesi pur avendo `MAD = 0` in una serie arrotondata (es.: tasso di disoccupazione Eurozona). Lo z-score robusto `(x_t - mediana_{t-1}) / (1.4826 * MAD_{t-1})` **non è definito** quando il denominatore è nullo. Il livello osservato resta informativo ma non è una misura numerica validata di forza FX, politica monetaria o regime.

## Regola deterministica e fail-closed

1. Usare esclusivamente la serie storica canonica nel registro Macro V2 già esistente, trasformazione identica, ID identico e valori finiti; nessuna fonte sostitutiva o interpolazione. Conservare la misura economica originale.
2. Richiedere **24 mesi** (12 trimestri per frequenza Q) di periodi economici precedenti consecutivi, escludendo sempre l'osservazione `t`. Le date con diversa precisione ma stesso valore sono **alias** e non aggiungono campioni. Fonti con periodi mancanti oppure incongruenze restano ineligible.
3. Quando lo status dell'attuale bridge è `NO_Z_ZERO_ROBUST_DISPERSION`, confermare che la MAD precedente è `<= 1e-9` (identico guard del bridge). In caso contrario rifiutare, anziché coprire una discrepanza.
4. **Non produrre un nuovo z-score**. `numeric_replacement_z = null` resta obbligatorio; non usare deviazione standard, IQR, epsilon, imputazione, winsorization o il percentile come scala numerica sostitutiva.
5. Riportare in modo **descrittivo** `current_minus_prior_median_original_units`, `ABOVE_ALL_PRIOR` / `BELOW_ALL_PRIOR` / `WITHIN_OR_TIED_PRIOR_RANGE`, osservazioni precedenti inferiori e pari all'attuale, e midrank percentile `(n_< + 0.5*n_=)/N`. Un valore 1 non è un 100% di probabilità di movimento FX.
6. Non inferire il segno valutario dal segno economico: disoccupazione alta è un deterioramento del mercato del lavoro, ma il FX dipende da sorpresa, repricing, pricing già incorporato e confronto internazionale.

## Prevenzione data snooping e PIT

- Il protocollo è una **descrizione di qualità delle feature**, non una nuova ipotesi predittiva H1. È stato scelto osservando il problema di scala nell'EUR ma **prima** di valutare la previsione FX; non scegliere un metodo alternativo sulla base dei futuri rendimenti.
- Le serie `MACRO_SERIES.json` sono **revisionate oggi**; periodi economici non equivalgono a timestamp di pubblicazione. Questo strumento non certifica point-in-time storico, sebbene i 24 periodi matematici siano precedenti al valore `t`. Per un futuro nuovo modello servono pubblicazioni origini registrate prima dell'evento, date e versioni.
- Nessun retrofitting al journal V2 28/29 ottobre, al Core `D.json`, ai ranking delle 28 coppie, a snapshot H1 o al benchmark momentum.
- `can_write_forward_v2_journal=false`, `can_feed_preregistered_H1=false`, `can_generate_legacy_D=false` restano immutabili. Il workflow serale può registrare l'originale Frozen Core, ma la cattura V2 reale **rimane bloccata** finché il proprio contratto non prevede e valida esplicitamente dati incompleti o nuova normalizzazione.

## Prove e promotion gate

Il modulo `validation/macro/v2_zero_mad_ordinal_quality_v1.py` legge soltanto il bridge Macro V2 e il registry, restituisce un receipt **solo in /tmp**. Test sintetici avversariali su valori ripetuti, date duplicate, storia incompleta, scale non degeneri, identity spoofing, assenza di mutazioni.

Per un'autentica nuova versione Forward è obbligatorio un **protocollo distinto**, con:
- versione e journal separati, orologio reale e append-only;
- elenco degli input economici missing, senza colmare artificiosamente il valore;
- validazione integrità di ECB T0, tassi e identità instrument;
- approvazione esplicita, QA GREEN e immutabilità dei journal V1 già registrati;
- nessuna promozione del modello o presunta validazione predittiva derivata dal solo dato EUR.

## Esito accettabile

Un GREEN di questi test certifica la **correttezza del trattamento delle anomalie statistiche**, non la completezza del V2 operativo e **non** un vantaggio predittivo rispetto al momentum FX.
