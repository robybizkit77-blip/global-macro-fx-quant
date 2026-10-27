# Macro V2 — EU HICP membership EA19/EA20/EA21 + CHF SECO/SNB precision

**27 ottobre 2026 — evidenze separate dalla certificazione di forza FX.**

## EUR.inflation: tre popolazioni realmente diverse nel nostro storico Eurostat

La serie HICP **first-web flash** di 105 mesi, già copiata e verificata con CSV SHA-256 e fingerprint economico nel repository, contiene:

| Composizione | Mesi archiviati | Intervallo |
| --- | ---: | --- |
| EA19 | 60 | 2018-01 … 2022-12 |
| EA20 (Croazia inclusa) | 36 | 2023-01 … 2025-12 |
| EA21 (Bulgaria inclusa) | 9 | 2026-01 … 2026-09 |

**Prove publisher.** Eurostat spiega la composizione geografica dinamica e il concatenamento degli aggregati. Per il 2023 l'ingresso della Croazia è documentato da <https://ec.europa.eu/eurostat/documents/2995521/15725194/2-31012023-AP-EN.pdf/d6c60a83-0dc6-04aa-774d-0fefc772ef68>. Per gennaio 2026 l'ingresso della Bulgaria e la transizione EA20→EA21 sono indicati da <https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-25022026-ap> e dalla BCE <https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.pr260101~c830245e42.en.html>.

**Nuova regola:** uno z-score basato su *24 primi comunicati precedenti* è considerato omogeneo per popolazione solo quando tutti i 24 mesi precedenti e il mese corrente appartengono alla **stessa composizione Eurozona**. Ci sono **48 finestre su 105** con 24 mesi precedenti omogenei (36 EA19 dal 2020 e 12 EA20 nel 2025); **57** non sono omogenee o hanno troppo poco storico. Questi numeri descrivono **finestra e definizione**, non 48 prove di previsione.

**Ottobre 2026:** l'ultima osservazione è settembre 2026, HICP flash 3,8%, regime EA21. Gli **otto mesi precedenti dello stesso regime** (gennaio-agosto 2026) non raggiungono 24. Nessuno deve esporre uno z-score a 24 mesi EA21 come se derivasse da un campione omogeneo. Qualsiasi valore costruito usando i mesi EA20 sarebbe, al massimo, un **calcolo di ricerca con comparabilità geografica ridotta e stima dichiarata**, non una fonte certificata o un nuovo score nel Core.

## CHF.labour: precisione del comunicato diversa dal vintage della serie SNB

Il comunicato ufficiale SECO pubblicato il **6 ottobre 2026** riporta **3,1%** di disoccupazione registrata destagionalizzata settembre (147.411 persone destagionalizzate). <https://www.konsum.admin.ch/it/newnsb/Cdju9-o8WGML>

Un tasso pubblicato a **un decimale** è soltanto compatibile, secondo l'arrotondamento convenzionale, con **3,05% inclusivo fino a 3,15% esclusivo**. Il dato esatto **3,1249882357461%** attualmente nello storico canonico SNB è dentro quell'intervallo, ma **il confronto NON dimostra che quello stesso numero fosse pubblicato il 6 ottobre**. La fonte SNB è <https://data.snb.ch/api/cube/amarbma/data/json/en>. Se non esiste un timestamp della prima distribuzione del valore esatto, il timestamp esatto rimane **nullo**.

Come controllo sul rischio revisioni: per **agosto 2026** il comunicato SECO originario del 7 settembre conteneva 147.970 disoccupati destagionalizzati; quello di settembre riportava agosto revisionato a **147.886** (−84), sebbene il tasso arrotondato rimanesse 3,1%. <https://www.seco-cooperation.admin.ch/de/newnsb/OfSdV0mM5gUa>

Per rappresentare il primo report SECO senza inventare un orario di messa online, si usa conservativamente il **7 ottobre 00:00 UTC**. Questo è un *gate di disponibilità prudente per il valore arrotondato*, NON un'attestazione del timestamp SNB o del momento di pubblicazione intraday.

## Impatto sul progetto

- Aggiunto al motore di ricerca il controllo EA19/EA20/EA21 e la semantica di precisione CHF, con test falsificabili di periodi, tagli di pubblicazione, arrotondamenti e revisioni.
- I due output sono un **sidecar di qualità dati** nelle viste temporali G8. I 105 record e il Core non sono modificati.
- **Nessun WITHHELD visuale nuovo richiesto al sito:** in una futura esposizione operativa si potrà mostrare «stima con definizione mista» o «SECO 3,1% arrotondato», ma non inventare l'esatto primo SNB.
- Nessun punteggio Macro V2 FX certificato, ranking 28 coppie, nessun avvio Beta o Forward Test, nessuna modifica a UI e schedule.

## Prossima verifica

Serve un riferimento di serie EA21 ricostruito su una **definizione geografica costante**, con regole ufficiali di comparabilità verificate e prova point-in-time (senza reinserire oggi dati revisionati nelle vecchie giornate); per CHF occorre un vero archivio ufficiale SNB/AMSTAT con l'esatto valore alla prima disponibilità, oppure operare dichiaratamente sulla metrica alternativa SECO arrotondata.
