# Macro V2 — tre assi economici, ipotesi sperimentale preregistrata (27/10/2026)

## Obiettivo e confini

Costruire una lettura coerente, comprensibile e riproducibile **per ognuna delle G8** senza dichiarare una nuova forza valutaria. Il Core `live_data/sections/D.json` al 25/09/2026 e le 28 coppie non vengono modificati. Il presente calcolo è **uno scenario metodologico**, non il risultato di un backtest.

Le tre variabili indipendenti sono:

1. **Growth:** PIL reale trimestrale rispetto ai **12 trimestri precedenti**. Il dato corrente è la prima pubblicazione web documentata, mai una successiva revisione incollata a posteriori. USD tasso annualizzato BEA convertito a tasso trimestrale non annualizzato. L'origine web storica **non** equivale a un archivio completo dei byte pubblicati il giorno originale.
2. **Labour:** disoccupazione rispetto alle **24 osservazioni mensili precedenti** o **12 trimestrali**. Si inverte il segno: disoccupazione più alta = meno tensione sul lavoro. I dati del registro attuale sono serie storiche revisionate, non repliche degli istanti originari.
3. **Inflation:** inflazione headline rispetto al proprio storico, interpretata come **pressione dei prezzi**. Il suo segno non è automaticamente né positivo né negativo per la valuta. Per determinare la reazione dei tassi servono aspettative, funzione di reazione della banca centrale e OIS.

Tutte le intensità sono z-score robusti, già limitati all'intervallo da −3 a +3 dal motore osservazionale. Gli input hanno frequenze eterogenee e **date di osservazione diverse**; il periodo economico non va mai confuso con la data di prima pubblicazione.

## Formula tecnica sperimentale (non calibrata sul vecchio D)

```
g = z( PIL reale QoQ )
l = - z( tasso di disoccupazione )
p = z( inflazione headline )
A = 0.50*g + 0.50*l
```

`A` è un **indicatore illustrativo di attività e tenuta del lavoro, relativo allo storico dello stesso paese**. I coefficienti 0,50 sono una scelta trasparente *da valutare*, non parametri ottimizzati né empiricamente validati. La pressione prezzi `p` è mantenuta **separata**; inflazione più alta non aumenta matematicamente `A`. Non si calcola una variabile `FX strength`.

Una semplice matrice descrittiva usa le soglie **+0,50** / **−0,50** su `A` e `p`, marcando *relativamente forte / relativamente debole / vicino al centro*. Le soglie non sono soglie cliniche/economiche validate, non definiscono GOLDILOCKS/STAGFLATION e non costituiscono segnali d'ingresso.

## Qualità e stime — niente dati finti

- 🇺🇸 USD: le due z-score osservazionali inflazione/disoccupazione non passano il requisito storico continuo a causa dell'ottobre 2025 durante lo shutdown BLS. Si usa **separatamente una stima esplicita** basata sui 24 valori reali disponibili in 25 mesi; non si inventa un CPI o un tasso di disoccupazione di ottobre. Qualità: `ESTIMATED_RESEARCH_ONLY`.
- 🇪🇺 EUR: la popolazione Eurozona e la definizione delle vintages non sono omogenee nello storico PIL. Qualità: `GDP_DEFINITION_CAVEAT_RESEARCH_ONLY`.
- 🇨🇭 CHF: PIL svizzero pubblicato con differenze fra dati sports-adjusted e flash/regular. Qualità: `GDP_DEFINITION_CAVEAT_RESEARCH_ONLY`.
- Altre G8: vettori matematici calcolati, ma lo storico di inflazione/lavoro è revisionato e quello Growth non ha un archivio originale verificato per ogni release. Qualità: `REVISED_OR_WEB_RESEARCH_NOT_PIT`.

**Nessun numero `A` è un punteggio certificato di forza relativa tra valute.** Anche dove la formula è aritmeticamente riproducibile, la comparabilità delle serie e le date di conoscibilità devono essere validate autonomamente.

## Condizioni per passare a una Macro V2 realmente operativa

1. Archivio originali delle pubblicazioni, revisioni e timestamp indipendentemente verificabili, con test che blocchino il *look-ahead bias*; specialmente transizione EA19→EA20→EA21 e definizione PIL svizzero.
2. Studio indipendente di sensibilità e stabilità dei pesi, delle soglie e delle finestre; confronto in più periodi *out of sample*, non fitting dei 24 valori del vecchio D.
3. Distinguere il ciclo macro domestico dalle pressioni inflazionistiche e dal **policy pricing**. Collegare solo successivamente OIS, 2Y, 10Y e premi, aspettative relative, COT, prezzo, orario della reazione e qualità dei dati.
4. Backtest replicabile e **Beta/Forward Test** vero prima di modificare `D.json`, rankings G8/28 coppie o dashboard operativa; poi audit finale dell'intera pipeline delle 08:00.

Il workflow sul progetto resta **read-only**, sfrutta quello già esistente dopo l'aggiornamento delle fonti, salva un artefatto di ricerca; non avvia nuovi cron né altera il sito.
