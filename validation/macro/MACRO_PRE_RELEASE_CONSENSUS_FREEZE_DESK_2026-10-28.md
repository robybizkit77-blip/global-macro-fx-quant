# Macro → Consenso → Actual → Rates / FX: primo archivio persistente delle attese pre-release
**28 ottobre 2026 · Modifica al vero Calendar/News refresh; nessun nuovo punteggio FX.**

## Il difetto operativo risolto
Prima della modifica, ogni esecuzione del flusso
\`calendar-news-operational-refresh-v1.yml\` aggiorna
\`MACRO_CONSENSUS_SECONDARY_V1.json\` con gli eventi
**futuri della settimana**. Dopo la data di pubblicazione
il forecast del giorno precedente può scomparire
senza lasciare una base stabile \`actual−consensus\`.

Adesso il flusso giornaliero:
1. acquisisce il consensus da provider secondario come prima;
2. legge l'**evento ufficiale** e il suo orario locale con
   fuso IANA (conversione UTC inclusiva DST);
3. salva **solo prima dell'ora del comunicato** una riga nel
   file append-only
   \`validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl\`;
4. mantiene il primo valore osservato con \`captured_at_utc\`
   effettivo dell'esecuzione e \`source_generated_at_utc\`
   dichiarato dall'upstream;
5. non modifica una previsione già congelata dopo un secondo
   download, neppure quando il provider la cambia;
6. conserva la catena di hash SHA256 delle righe per rilevare
   modifiche, omissioni e riordinamenti di record;
7. pubblica il log nello **stesso commit** con Calendar/News,
   soltanto sull'esecuzione main; nelle PR è prova senza pubblicazione.

La verifica indipendente richiede **serie, area e giorno
economico esatti**, non solo la stessa valuta.
Un dato parziale tipo PMI/Import Prices non può
sostituire un CPI headline. Un \`consensus\` senza unità
esplicita (%) non è ammesso come percentuale.

## Due eventi del 30 ottobre 2026

Nel feed osservato il 28 ottobre 07:03 UTC,
il test di contratto trova:
- **🇺🇸 USD Employment Cost Index Q3 2026**:
  consenso provider **+0,8% q/q**; precedente **+0,9%**;
  orario ufficiale programmato **30/10 12:30 UTC**
  (08:30 America/New_York).
- **🇨🇦 CAD GDP mensile agosto 2026**:
  consenso provider **+0,2% m/m**; precedente **0,0%**;
  stesso orario programmato **30/10 12:30 UTC**
  (08:30 America/Toronto).

Queste informazioni in CI sono **fixture storiche
dell'osservazione**; non sono actual né sorpresa.
La vera riga con \`captured_at_utc\` verrà scritta
**soltanto dalla prossima esecuzione effettiva** del
Calendar/News che trovi l'evento ancora nel futuro.
Il test non retrodata mai una riga e non dichiara
che l'orario previsto sia già stato il primo
messaggio consegnato al mercato.

## Limitazioni esplicite

- Il provider di consenso resta una fonte **secondaria**,
  livello **B**, NON fonte ufficiale.
- L'orario nel calendario ufficiale è programmato,
  non l'istante verificato di prima divulgazione.
- Il tempo di acquisizione è quello del runner: la
  provenienza provider non è indipendentemente auditata.
- I forecast restano nella loro scala (0,8% q/q
  non è 0,8% annuo). Non vengono annualizzati.
- Eventi senza orario ufficiale completo sono
  **saltati**: giorno soltanto non basta per
  dimostrare un congelamento prima del dato.
- Non esiste ancora una pipeline che apporti un
  \`actual\` ufficiale con link verificato e revisioni.
  Da questo ledger **non** si ottiene automaticamente
  una sorpresa numerica, un percorso di tassi o un
  profitto stimato. Servirà un secondo controllo
  \`actual − frozen consensus\` con prova del comunicato,
  scalatura coerente, release timestamp e revisioni.
- Per attribuire reazioni a OIS/2Y/FX servono
  prezzi/vintage di mercato confrontati prima e
  dopo l'istante con fonti e diritti compatibili.
  Il vecchio movimento giornaliero non basta a
  dimostrare causalità.
- Want/Can banca centrale resta una diagnosi da
  documentare con comunicati e discorsi ufficiali,
  non derivabile da un tasso nominale isolato.

## Controlli

\`python -m unittest validation.macro.test_freeze_pre_release_consensus_v1 -v\`

\`python -m validation.macro.freeze_pre_release_consensus_v1\`

**Nessuna modifica** a Core \`D.json\`,
28 coppie operative, Beta, Forward, rating di
fonti ufficiali, OIS, tassi, alert orari o visuali del sito.
Non introduce nuove schedulazioni: aggiunge un
passaggio alla pipeline Calendar/News esistente.

**Esito verificabile del lancio**: file con righe
nuove nel ledger dopo l'esecuzione main,
\`new_forecasts_frozen\` del log, hash
e ora UTC della cattura; successiva esecuzione
\`new_forecasts_frozen=0\` a parità di eventi.
