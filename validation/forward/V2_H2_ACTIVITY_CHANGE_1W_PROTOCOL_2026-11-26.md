# V2-H2-ACTIVITY-CHANGE-1W-V1 — Preregistrazione ricerca Macro → FX

**26 novembre 2026 | Solo ricerca.** Il protocollo diventa vincolante alla sua integrazione in main, prima della prima acquisizione ammissibile del nuovo cohort (27 novembre 2026). Non modifica H1, Core, scoring operativo, archivio storico o workflow.

## Domanda

Una variazione positiva della forza dell'attività economica di un paese rispetto alla propria storia, maggiore di quella osservata nell'altro paese, è associata al successivo apprezzamento relativo della valuta? Il mercato potrebbe avere già prezzato il cambiamento; inflazione, tassi, rischio e flussi possono dominare l'effetto. Un esito negativo falsifica questa specifica ipotesi, non l'intera macroeconomia.

## Modello fissato prima degli outcome

Leggere esclusivamente il nuovo journal V2_UNIFORM_MACRO_PROSPECTIVE_V1.jsonl e il suo journal V2_UNIFORM_MACRO_ECB_REFERENCE_RETURNS_V1.jsonl, senza mescolare altri cohort. Usare il pannello sample-SD, non scegliere tra MAD e SD sulla base degli outcome. Per ogni valuta c, A(c,t) è il campo sample_sd_domestic.activity, pari a 0.5*z(PIL)+0.5*z(tightness lavoro), con z già limitati a ±3. Inflazione resta separata; non viene trattata come forza della crescita.

Con due snapshot realmente archiviati di giorni lavorativi Roma consecutivi, antecedenti al risultato:
- delta A(c,t) = A(c,t) - A(c,t-1)
- x(A/B,t) = delta A(A,t) - delta A(B,t)
- verso sperimentale: sign(x), positivo = apprezzamento della valuta base A.
- zero = nessuna chiamata. Non introdurre soglie dopo aver visto gli esiti.

Questo è un cambiamento di coordinate normalizzate in due vintage realmente osservati, non una sorpresa rispetto al consenso, non un rilascio PIT storico certificato e non un confronto diretto dei livelli dei PIL tra paesi. Può includere revisioni e cambiamenti della finestra. Annotare cambi di periodo e variazioni del valore a periodo invariato; non inferire la loro causa senza evidenza.

## Ammissione e denominatori

Richiedere integrità dei due snapshot, data t0 e 28 cross ufficiali ECB, medesimo policy ID e definizione degli assi nei due snapshot, valori finiti, attività disponibile e tier COMPLETE_OBSERVATION_WINDOW_RESEARCH_ONLY per entrambi gli assi growth/labour e per entrambe le valute in entrambi gli snapshot. Escludere cambi di definizione o tier, gap stimati e dati mancanti; non sostituire con zero. In particolare le coppie USD non sono ammissibili mentre il lavoro usa il gap BLS stimato. Non usare la presenza del prezzo futuro per selezionare le coppie. Il denominatore è sempre 28 coppie per data, con conteggi di esclusioni, segnale zero, benchmark zero, tie e outcome mancanti; nessuna selezione retroattiva di valuta o coppia. Se il primo snapshot non ha un precedente autentico, nessuna chiamata.

## Outcome e benchmark

Orizzonte primario unico 1W: primo fixing ECB strettamente successivo al giorno di maturazione dei sette giorni civili, come nell'observer esistente, gap massimo quattro giorni. Segno del rendimento logaritmico base/quote. Le altre scadenze sono descrittive, non occasioni di selezionare il risultato migliore.

Benchmark unico: segno del rendimento FX tra i due T0 congelati t-1 e t. Valutare modello e benchmark sulla stessa sottopopolazione con x, benchmark e outcome non nulli. Misura primaria: differenza tra accuratezza direzionale del modello e del benchmark, prima mediata sulle coppie nella stessa data, poi sulle date ammissibili. Nessun peso ottimizzato o test ripetuto per cercare un vincitore.

I 28 cross non sono indipendenti: sette livelli EUR al massimo per data, e gli orizzonti si sovrappongono. Soglia minima di avvio dell'inferenza: 120 giornate distinte con almeno un confronto ammissibile e maturato; non è garanzia di potenza statistica. Rendicontare anche giorni con nuove osservazioni economiche, distribuzione per valuta, date escluse, concentrazione e copertura. Intervallo 95% mediante bootstrap per blocchi consecutivi di 10 giorni di acquisizione, sensibilità 20, seme fissato 20261126; preservare il calendario e i giorni senza chiamate, non comprimere i buchi creando continuità artificiale. 10000 repliche; esclusione solo di repliche senza dati valutabili, riportarne il numero. Nessun p-value ingenuo su righe per coppia. Se copertura o numerosità non consentono inferenza credibile, risultato INSUFFICIENT_VALID_COHORT.

Null: differenza media <= 0. Evidenza favorevole preliminare solo se limite inferiore 95% > 0 con entrambi i blocchi e differenza positiva nelle due metà cronologiche predefinite della finestra valutata; altrimenti non dichiarare vantaggio robusto. Nessuna implicazione causale o economica in termini di PnL. Una eventuale validazione trading successiva richiede prezzi eseguibili, costi, slippage, rischio e test out-of-sample indipendente.

## Momentum mensile e accelerazione: separati

Il modulo current_activity_momentum conserva crescita 3m/3m, velocità (differenza tra tassi consecutivi), accelerazione (differenza delle velocità) e turning point; NZD usa QoQ e AUD spesa nominale. Questi numeri non sono ancora comparabili come un unico score globale: per il momento solo diagnosi a livello di singola economia. Non inserirli nell'equazione H2. Un test incrementale futuro deve fissare orizzonte, fonti reali comparabili, trasformazione, pesi e benchmark prima di osservare i propri outcome; niente selezione ex post tra i 13 indicatori.

## Stato

Protocollo documentale, non valutatore eseguito. Il codice di acquisizione, l'observer e l'audit giornaliero sono già integrati (PR 1666–1668). Nessuna osservazione del nuovo cohort verificata al momento della registrazione; nessuna evidenza predittiva, nessun nuovo segnale, ranking o pubblicazione di D.json. Conservare l'identità di questo protocollo e registrare eventuali nuove ipotesi in un documento separato prima della relativa finestra OOS.
