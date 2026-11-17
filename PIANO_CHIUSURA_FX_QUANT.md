# Piano di chiusura FX Quant Next

Il lavoro procede su FX Quant Next e sui dati condivisi che alimentano il sito. L'obiettivo è trovare ogni mattina la Panoramica, le 28 coppie e il Briefing della seduta, con la data e la fonte dei dati usati. Le serie settimanali e mensili seguono le rispettive pubblicazioni.

| Tappa | Intervento | Prova di chiusura |
| --- | --- | --- |
| 1. Aggiornamento e pubblicazione | Stabilizzare il coordinatore, il recupero delle esecuzioni mancate e il passaggio su GitHub Pages. | Una corsa automatica con i passaggi di raccolta e pubblicazione effettivamente eseguiti. I file pubblici corrispondono a quelli verificati per la seduta. Un recupero tardivo resta registrato come tardivo rispetto alle 08:00 di Roma. |
| 2. Copertura G8 | Risolvere i ritardi dei governativi CHF, NZD e AUD, completare le letture OIS EUR e NZD, recuperare le serie di liquidità e credito ancora arretrate. Usare stime motivate e riconoscibili dove serve. | Per ogni serie sotto intervento, data del dato, fonte e qualità sono verificabili nella sezione pubblica. La data attesa segue la frequenza della fonte. |
| 3. Uso dei dati sul sito | Collegare la lettura macro aggiornata a Valute G8 e alle 28 coppie, con validazione prima di cambiare la base delle tesi. Completare il passaggio automatico del Briefing alla Research Library e far usare a Panoramica, calendario e report le evidenze della seduta. | Ranking G8, Top 5 e 28 coppie leggibili e coerenti con le date dichiarate. La pagina pubblica apre il Briefing della seduta corretto entro le 08:00 di Roma e mostra una sola ultima edizione per categoria. |
| 4. Verifica finale | Controllare la navigazione desktop e mobile, le sezioni essenziali e un secondo aggiornamento automatico nella seduta successiva. | Il risultato è verificabile dal sito pubblico e dai log di produzione. Restano tracciate le fonti che aggiornano su un calendario diverso da quello giornaliero. |

## Verifica operativa del 17 novembre 2026

- La [corsa programmata delle 13:28](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44083535744) ha raccolto e certificato i dati operativi. Il [publisher ha verificato i file via HTTPS](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44084400520) alle 13:35 di Roma. Il controllo della scadenza ha registrato il ritardo.
- Il [Briefing originale del 17](https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/next/reports/Briefing_Forex_Commodities_2026-11-17_V3_MORNING_RESEARCH_DESK.html) è stato recuperato con la [PR #1333](https://github.com/robybizkit77-blip/global-macro-fx-quant/pull/1333). Verificati l'indice della Research Library e l'identità dell'HTML pubblico con l'originale. Il trasferimento automatico entro le 08:00 resta da dimostrare.
- Il coordinatore passa da coppie di cron UTC a cinque orari nativi Europe/Rome. La prima corsa programmata con i nuovi cron va verificata nei log, fino al controllo della pubblicazione.

- Nei [controlli Macro G8](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44097347290), due asserzioni usavano periodi di agosto e settembre su serie già aggiornate. I test ora verificano le pubblicazioni archiviate per il loro periodo e il rifiuto di associarle a mesi diversi. Il controllo resta in sola lettura e conserva i requisiti per la prima pubblicazione di ciascuna serie.

## Stato iniziale del 17 novembre 2026

- **Tappa 1 in corso.** Il controllo che usava una data fissa è stato corretto con la [PR #1331](https://github.com/robybizkit77-blip/global-macro-fx-quant/pull/1331). Il recupero del mattino ha tentato due volte di avviare il coordinatore. GitHub ha respinto entrambe le richieste perché `phase` era al livello sbagliato nel corpo della richiesta. [Primo tentativo](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44019661571) · [Secondo tentativo](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44025985294)
- Il [publisher di Pages](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/44056740084) ha pubblicato e verificato file via HTTP alle 10:35 di Roma. Questa è la prova di consegna per quella pubblicazione. La prova della catena automatica del mattino è ancora aperta.
- I prezzi delle 28 coppie usano il fixing del 16 novembre. La base macro delle tesi risale al 25 settembre. La Panoramica del 17 è online e il [Briefing pubblico](https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/next/reports/daily-latest.json) è del 16.

Il prossimo intervento si sceglie nella prima tappa ancora aperta. Dopo ogni correzione, aggiornare qui lo stato con il link al run e il risultato pubblico. Le rifiniture grafiche si affrontano dopo la verifica operativa.
