# Macro V2 — matrice sincronizzata delle 24 evidenze G8

## Consegna: una sola fotografia temporale

Il modulo `validation/macro/v2_g8_24_axis_asof_evidence_v1.py` ricostruisce le **8 economie × 3 assi** alla stessa data/ora UTC, senza utilizzare un dato prima della data documentata di disponibilità.

Per ogni casella separa:
- **Data di pubblicazione** vs **mese/trimestre economico di riferimento**. La fotografia è sincronizzata sul primo, NON pretende che tutte le variabili misurino lo stesso mese.
- **Primo valore web documentato** vs **eventuale revisione visibile a quella data**. Il dettaglio Eurostat non riscrive retroattivamente la prima stima flash.
- **Identità serie canonica** vs **candidato ufficiale non identico**. Le quattro eccezioni note sono obbligatoriamente fissate e verificate; una quinta sostituzione fallisce.
- **Qualità** della fonte: serie coincidente, genealogia concettuale, primo valore in archivio, metrica alternativa arrotondata, definizione geografica EA21, periodi privi di documentazione.
- **Politica per stime:** si mostra il valore osservato ufficialmente e la qualità reale; non si inventa una pubblicazione storica inesistente. Il software è pronto ad associare separatamente stime *solo quando formula, data e base osservazionale siano esplicite*.

La parte PIL proviene dalle prime stime web dei quarterly real GDP: USA SAAR convertito correttamente a QoQ non annualizzato, gli altri nella rispettiva unità pubblicata. Non si usa una revisione successiva come prima pubblicazione.

Per **EUR inflation** si utilizza la serie canonica Eurostat **105 prime flash** già recuperate, con l'avvertenza EA19/EA20/EA21: settembre 2026 ha soltanto 8 mesi precedenti di regime EA21 e perciò non è ammissibile affermare una normalizzazione a 24 mesi omogenea.

Per **AUD inflation** si utilizza la serie canonica **34 osservazioni quarterly first release**, NON il CPI mensile candidato.

Per **CHF labour** il comunicato SECO fornisce un tasso **3,1% rounded** e intervallo compatibile convenzionale **[3,05%; 3,15%)**, con visibilità prudente da 2026-10-07T00:00Z. Questo non è il primo valore **preciso SNB**: non si inventa un timestamp della release del cube SNB né si sostituisce il numero esatto attualmente revisionato come vintage iniziale.

## Verifiche di comportamento

Test agli istanti di confine, al secondo/microsecondo:
- Eurostat settembre 2026 non visibile prima del **3 ottobre 00:00 UTC**.
- SECO 3,1% settembre 2026 non visibile prima del **7 ottobre 00:00 UTC** nella politica prudente (NON effettivo minuto di prima uscita).
- CPI trimestrale Australia Q2 2026 non visibile prima del **29 luglio 01:30 UTC** (=11:30 Canberra, AEST).
- Fonte di frequenza errata, falsa equivalenza, release nel futuro e archivi alterati causano errore, non un punteggio.
- `D.json` e la vista 28 coppie non cambiano.

## Cosa misura veramente

È una **matrice di disponibilità delle evidenze alla data del taglio**, utile come ponte verso un **replay storico comune** e come metrica della copertura reale delle fonti. **Non** è ancora un backtest economico/FX: 24 ultime osservazioni visibili in un giorno non significano 24 serie complete con ogni first-release storica della finestra di training. Rimangono non certificate le catene complete di revisioni e la comparabilità delle definizioni. Nessun risultato va usato per modificare rankings, Core, Beta/Forward.

Il modulo gira in read-only, produce un report temporaneo e un SHA-256 del contenuto, con test automatici. Non introduce schedule e non modifica il sito.
