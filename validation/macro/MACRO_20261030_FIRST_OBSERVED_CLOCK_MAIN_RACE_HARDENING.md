# 30 ottobre: orario reale dell'actual e retry sicuro contro main concorrente

Data intervento: 28 ottobre 2026, prima del comunicato del 30 ottobre.

## Problemi individuati

1. Il parser BLS/Statistics Canada salvava captured_at_utc usando
   l'ora **di partenza** della funzione, prima del download e
   dell'estrazione del numero. Se una fonte impiega tempo,
   l'archivio anticipava impropriamente la vera lettura.
2. Il fast-check PR #735 controllava l'hash della main una volta.
   Se durante il download un altro workflow aggiornava main,
   il job falliva; il candidato poteva non essere pubblicato.
3. Durante un controllo senza actual nuovo, il fast-check
   ricostruiva ugualmente il News Pulse e rischiava di
   produrre un commit non relativo all'evento.

## Correzione concreta

Il timestamp viene ora rilevato **dopo il download e la
verifica dell'indicatore e del periodo**. Rimane la
prima osservazione del runner, non prova del timestamp
indipendente del primissimo rilascio al mercato.

La procedura GitHub sul ramo main, nella finestra del
30 ottobre dalle 12:30 UTC, è:

- Legge i due forecast firmati e l'archivio official first-seen;
- Se nessun actual nuovo è verificato: **non scrive** News Pulse
  o file macro; emette solo una ricevuta;
- Quando un actual BLS/StatCan è disponibile, costruisce
  il livello News Pulse **noncausale** e verifica che nessun
  altro file fuori dai due autorizzati sia stato modificato;
- Prima del commit confronta la versione locale di main
  con quella attuale remota; push non è forzato;
- Se main è cambiata: riscarica la nuova main, scarta il
  candidato obsoleto e **riscarica l'attuale pagina ufficiale**.
  Evita di inventare una fusione fra catene SHA256 append-only.
  Se nel frattempo un altro job ha catturato il dato, il
  nuovo tentativo lo vede e non crea doppioni;
- Al massimo **tre tentativi** per singolo controllo.
  Esauriti, la run fallisce esplicitamente.

La concurrency group calendar-news-operational-refresh-v1
era **già identica** su entrambi i workflow: rimane invariata.
I retry aggiungono difesa contro altri processi di main.

## Date e limitazioni

Pubblicazione prevista il 30 ottobre **12:30 UTC /
13:30 CET Europe/Rome**.
Fast-check richiesti per **12:37, 12:57, 13:27, 14:07 UTC**.
GitHub Actions può partire in ritardo. Nessuna nuova
promessa di latenza garantita o di notifica ChatGPT.

Gli actual e le sorprese sono dati descrittivi,
con consenso secondario B e actual su pagina ufficiale.
Non provano una variazione OIS/2Y/FX causata
dall'annuncio, né danno segnali di ingresso.

Il codice non scrive Core D.json, 28 coppie,
Beta, Forward, COT, report o alert chat.
La ricevuta resta nell'artefatto temporaneo della run.

Test: clock after-fetch con ritardo simulato, tre
conflitti main, altro writer che ha già archiviato,
assenza di actual = nessuna scrittura, fail-closed,
BLS/Canada e contesto FX senza ricalcolo di tesi.

Il collaudo finale resta l'effettiva esecuzione
del workflow il 30 ottobre.
