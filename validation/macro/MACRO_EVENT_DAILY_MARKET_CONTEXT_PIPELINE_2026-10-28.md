# Macro → consenso → actual → tassi/FX: fotografia prima e contesto successivo
**28 ottobre 2026 · pipeline Calendar/News reale · test noncausale**

## Cosa cambia oggi concretamente

Le precedenti PR hanno realmente archiviato due consensi prima
delle pubblicazioni previste **venerdì 30 ottobre 2026
alle 13:30 Europe/Rome (12:30 UTC)**:
- USD Employment Cost Index, costo totale trimestrale q/q
  destagionalizzato: consenso provider **+0,8%**;
- CAD PIL reale per industria, agosto 2026 m/m:
  consenso provider **+0,2%**.

La PR #733 ha già aggiunto il recupero dell'**actual ufficiale
post-annuncio**, senza inventare cifre prima della pubblicazione.

La nuova parte cattura una **fotografia di mercato precedente
alla notizia** alla prima verifica disponibile nel runner.
Serve a non perdere le osservazioni precedenti quando il
repository conserva soltanto gli ultimi snapshot e i
contratti futures scadono o cambiano.

### Segnali davvero disponibili

| Valuta | 2Y/10Y | ECB fixing | 6M repricing |
|---|---|---|---|
| USD | Serie giornaliere del Tesoro, fino al 27/10 nello snapshot | EUR/USD fixing BCE del 27/10 | Indicazione futures/TradingView, **NON OIS ufficiale**; nessun benchmark 6M promosso |
| CAD | Serie governativa BoC, ultimo 26/10 nello snapshot | EUR/CAD fixing BCE del 27/10 | Futures CORRA Montréal Exchange ufficiali, ultimo 27/10; **futures, non OIS** |

La fotografia conserva la **data e il valore realmente presenti**
nel repository e una ricevuta della cattura GitHub:
- \`2Y\`: livello del rendimento governativo, non tasso
  di policy senza premio/term structure;
- \`10Y\`: titolo governativo, influenzato anche da
  reali, breakeven e premi a termine;
- \`ECB_FX\`: EUR/USD o EUR/CAD da fixing BCE
  giornaliero — non prezzi tick a ridosso dell'annuncio;
- \`SIX_MONTH\`: per CAD futures con mappatura
  del bucket a 6 mesi e identità della fonte;
  per USD **nessun 6M ufficiale attribuito**.

L'archivio è append-only con fingerprint SHA256:
\`validation/macro/MACRO_EVENT_PRE_RELEASE_MARKET_ANCHORS_V1.jsonl\`.
Nessuna osservazione può essere retrodatata dopo il comunicato
per simulare una fonte pre-release. La prima fotografia, anche
se due giorni prima dell'annuncio, resta **early baseline**,
non \"l'ultimo tick prima dei dati\".

### Come si comporta dopo l'annuncio

Il nuovo campo \`NEWS_PULSE_OPERATIONAL.macro_event_market_context\`
presenta:
1. **PENDING_OFFICIAL_RELEASE** — attesa della pubblicazione;
2. **PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION** — evento
   scaduto ma actual/periodo/unità ancora non verificati;
3. **PENDING_POST_RELEASE_DAILY_OBSERVATIONS** — actual
   certificato, tassi/fixing non ancora aggiornati a
   una data successiva a quella del comunicato;
4. **DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY** — prima
   osservazione *successiva al giorno* del comunicato
   rispetto alla fotografia conservata, con dati veri
   e date proprie per USD e CAD;
5. status granulari separati per 2Y, 10Y, FX e
   CORRA futures CAD (solo se la definizione/mappatura
   degli strumenti non è cambiata).

**Importante:** una variazione descritta tra 27 ottobre
e 2 novembre non misura l'effetto causale del PIL uscito
il 30 ottobre. Contiene tutti i movimenti successivi,
anche altri dati e geopolitica.

La prima osservazione post deve avere **data di mercato
strettamente successiva al giorno della notizia**:
il fixing dello stesso 30/10 non è trattato come
un prezzo intraday verificato dopo l'annuncio.
Le serie ufficiali con sola data giornaliera
restano contesto osservato, non testimonianze evento→prezzo.

Per comparabilità:
- non si sottraggono indicatori 2Y di banche centrali
  come se fossero due OIS puri;
- non si interpreta il cambiamento di un futures
  con diverso contract/horizon mapping;
- non si danno segnali long/short o percentuali
  di probabilità macro senza prova OOS.

## Test deterministici

La regressione usa una **fotografia di valori reali
presenti nel repo il 28 ottobre**,
\`validation/macro/fixtures/macro_event_market_preanchor_oct28_v1.json\`,
e solo *successivamente* aggiunge valori/post-news
**sintetici marcati come tali** nei test.
Verifica che:
- prima della notizia tutte le due righe restino PENDING;
- nessun actual venga inferito dalla presenza del dato
  giornaliero, né dal feed RSS;
- due actual sintetici dopo la data portino al calcolo
  di differenze descrittive soltanto in presenza delle
  serie post con data coerente;
- le serie datate *30 ottobre* non siano spacciate
  per timestamp intraday post-release;
- un cambiamento di mappatura futures blocchi il confronto;
- il catalogo degli anchor non possa essere riscritto
  o riordinato senza rilevazione;
- nel feed ufficiale attuale ci siano ancora **zero
  actual pre-release**.

## Stato e prossima verifica

Il prossimo passaggio futuro sarà osservare effettivamente:
- il primo valore BLS e Statistics Canada;
- le date delle nuove quotazioni 2Y/10Y, EUR fixing
  e CORRA futures;
- l'eventuale mancanza di un vero feed OIS/futures
  coerente per USD;
- banca centrale Want/Can da testo ufficiale.

I dati sulla reazione *intraday* e il legame
causale con la notizia restano **NON CERTIFICATI**.
Nessuna ricalibrazione di Core \`D.json\`, ranking G8,
28 coppie, Beta/Forward o modifica all'alert orario.

Nessuna nuova schedulazione: inserito nel flusso
Calendar/News già esistente, e nella struttura
\`NEWS_PULSE_OPERATIONAL.json\` come **nuovo livello
informativo separato**. Si aggiorna ai successivi
passaggi del workflow; non garantisce un alert
alle 13:30 del 30 ottobre.
