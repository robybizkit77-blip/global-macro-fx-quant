# Macro V2 — storico “quando era conoscibile”: Inflazione/Lavoro G8

## Risultato nuovo

Un unico ledger read-only per **16 combinazioni valuta × pilastro** registra ogni candidato di pubblicazione ufficiale documentata, distinguendo:

- **Periodo osservato** (per esempio inflazione settembre): non è la **data di rilascio**.
- **Prima pubblicazione** (FIRST_WEB): valore effettivamente attestato da una pagina ufficiale datata, disponibile da un orario attestato o dal **giorno UTC seguente** in assenza di orario.
- **Rettifica/dettaglio/revisione**: il valore può cambiare **solo da quando è disponibile**. Una revisione di un mese precedente non crea un nuovo mese economico e non sovrascrive il valore conoscibile prima.
- **Identità della serie**: il candidato può essere ufficiale ma misurare un concetto diverso dalla serie usata dal Core. Esempi: indice mensile CPI Australia vs registro CPI trimestrale; LNS14000000 vs UNRATE; SECO CHF tasso disoccupazione arrotondato vs registro SNB.
- **Qualità**: una pagina web storica non è automaticamente un archivio immutabile degli originali. Il match fra `series_id` e frequenza non prova la completa catena delle revisioni.

L'audit crea snapshot giornalieri UTC dal **1 luglio 2026** alla data di esecuzione, salvo diverso intervallo richiesto, registrando per ciascuna delle 16 serie l'ultimo mese/trimestre **per cui esiste una prima pubblicazione documentata a quella data**, e due valori distinti: prima uscita e ultimo valore revisionato già conoscibile.

## Esempi testati

- 🇳🇿 NZD disoccupazione Q1 2026: prima uscita **5,3**, revisione successiva a **5,4** pubblicata con l'uscita Q2; Q2 è un altro periodo economico (**5,6**), non una revisione del Q1.
- 🇪🇺 EUR inflazione: flash e dato dettagliato restano due eventi temporali separati, senza inserimento retroattivo.
- 🇬🇧 GBP disoccupazione: la serie LFS a tre mesi identifica il **mese finale della finestra**, non il mese centrale del bollettino.
- 🇦🇺 AUD: la storia CPI mensile preliminare **non sostituisce** il dato trimestrale canonico.

Tutti gli eventi sono filtrati usando l'effettiva data di disponibilità registrata, **mai** la data economica. Il test agli estremi `un microsecondo prima / al momento della gate` deve sempre dimostrare l'assenza del nuovo evento prima dell'orario registrato.

## Limiti e prossimo salto

Questo è un vero meccanismo di replay degli **eventi ufficiali già documentati**, ma NON è ancora un dataset PIT indipendentemente certificato per il modello: varie serie hanno pochi mesi di primi comunicati, altre non coincidono esattamente col registro canonico, e le revisioni archiviate non sono complete per tutte.

La verifica permette finalmente di misurare con precisione **quali osservazioni storiche attestabili abbiamo davvero**, quali mancano e quali non sono semanticamente confrontabili. I prossimi step sono acquisire ed attestare gli originali delle vintages storiche per ogni serie e ottenere test cronologici omogenei dei 24 assi, prima di Backtest/Beta/Forward, nuova versione di `D.json` e ranking 28 coppie.

**Perimetro protetto:** Nessuno score, nessun riempimento artificiale, nessun cambio dei dati di produzione, delle 28 coppie o del sito. JSON solo sotto `/tmp` in artifact GitHub; nessun nuovo schedule.
