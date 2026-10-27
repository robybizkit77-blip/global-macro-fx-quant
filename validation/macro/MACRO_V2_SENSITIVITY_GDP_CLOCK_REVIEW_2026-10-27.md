# Macro V2 — verifica di sensitività e cronologia release (27 ottobre 2026)

## Risultato di ricerca implementato

La PR introduce **due controlli distinti, senza pubblicare punteggi di forza valutaria**.

**A. Sensitività dei pesi e degli input** su ogni economia G8:

- Formula *ipotetica*, non ottimizzata: `A = w · zGrowth + (1 − w) · zLabourTightness`.
- Si provano soltanto `w = 0,25; 0,50; 0,75`, per osservare quanto la lettura locale cambia rispetto alla scelta centrale del 50/50.
- Stress separato di **±0,25 punti z** su Growth oppure Labour. L'ampiezza è **uno scenario scelto**, non una stima della deviazione standard degli errori statistici o un intervallo di confidenza.
- Vengono misurati dispersione, variazioni nella categoria qualitativa e robustezza alle perturbazioni **per la stessa economia**. Nessun confronto numerico di forza FX tra Paesi.
- L'inflazione rimane un asse separato: non contribuisce positivamente o negativamente ad `A`.
- USD mantiene l'etichetta di **stima per l'ottobre 2025 BLS mancante**; EUR e CHF conservano le riserve sulla comparabilità delle definizioni del PIL.

**B. Cronologia delle prime pubblicazioni web del PIL**:

- Per ogni G8, vengono riprodotti i trimestri **2024Q3–2026Q2**, quindi **8 trimestri × 8 Paesi = 64 casi**.
- Ogni caso è ricalcolato non prima del giorno UTC successivo alla **data di prima pubblicazione** documentata dall'istituto. Una verifica all'istante immediatamente precedente deve escludere il trimestre non ancora visibile.
- Le **12 prime pubblicazioni trimestrali precedenti** alimentano la normalizzazione robusta; l'osservazione corrente resta fuori dal campione di training. Le revisioni successive non vengono inserite retroattivamente nelle prime pubblicazioni.
- È una verifica concreta della **coerenza del software con le date del dossier**, non una certificazione dei byte effettivamente pubblicati in origine, né del timestamp intraday, né un backtest con quotazioni FX.

## Attenzione ai limiti

1. **64 controlli GDP con date** non sono 64 prove di capacità previsionale né 64 osservazioni indipendenti: molte finestre di training trimestrali si sovrappongono e i dati sono web-statement storici, non archivi di pubblicazione certificati.
2. Le feature Labour/Inflation sono ancora basate su una vista corrente di serie storiche in parte revisionate. Non esiste un replay genuino, sincronizzato e certificato delle **24 componenti alla conoscenza disponibile in ciascuna data del passato**.
3. La rilevazione di instabilità a pesi alternativi può **falsificare una pretesa di robustezza**, ma non dimostra la validità predittiva o economica delle classificazioni.
4. Il passaggio a un vero punteggio Macro, a regime economico, o al ranking FX richiede: serie con fonte e release PIT validate, test cronologici indipendenti, sensitività su finestre diverse, funzione di reazione di BCE/Fed/BoE/BoJ/altre banche, OIS/2Y/10Y e un **forward test** separato dalla costruzione del modello.

## Perimetro operativo

Workflow **di ricerca già esistente**, senza nuovi orari programmati. Artefatti temporanei sotto `/tmp` per revisione; nessun overwrite di `live_data/sections/D.json`, nessun aggiornamento ranking delle 28 coppie, nessuna modifica del sito o delle logiche Beta/Forward.
