# Metodo causale Global Macro G8 → banche centrali → pricing → Forex

**Versione:** 1 · **Congelato come specifica di ricerca:** 9 novembre 2026  
**Stato:** progettato e versionato; **non** attivo nel sito né nei segnali.

## Perché esiste

L'obiettivo non è replicare previsioni personali sulla Fed o imitare la narrazione di un singolo analista. È applicare a **USD, EUR, GBP, JPY, CHF, CAD, AUD e NZD** lo stesso processo economico, adattando le domande alla struttura del paese e al mandato specifico della sua banca centrale.

**Prima**: che cosa mostrano le imprese, le assunzioni, i licenziamenti, i salari, il reddito e la domanda delle famiglie?  
**Poi**: quale catena economica può plausibilmente produrre un'accelerazione, una frenata o un punto di svolta nei prossimi mesi?  
**Poi**: come cambia il bilanciamento dei rischi *WANT/CAN* della banca centrale?  
**Poi**: quanto è già incorporato nella curva OIS/futures, nel 2Y e nel 10Y, e che cosa viene riprezzato sul dato?  
**Infine**: il cambiamento *relativo fra due paesi* può avere conseguenze FX credibili, oppure il prezzo, il rischio globale e i flussi non confermano?

## Output per ognuna delle otto valute

La prima frase deve contenere il **giudizio economico attuale** senza numeri gratuiti. La seconda racconta il **cambiamento e la sua composizione**; la terza spiega **come potrebbe propagarsi a imprese, lavoratori e consumatori**. La quarta esplicita **quale reazione condizionata della banca centrale potrebbe diventare più plausibile**; la quinta dice **cosa sta prezzando il mercato dei tassi, con le qualità delle fonti**; la sesta chiarisce **quale dato conferma/smentisce la tesi**.

Non forzare le sei frasi se un paese ha dati insufficienti: esplicitare l'incertezza è più professionale di inventare una lettura completa. Non sono previste probabilità numeriche finché non esiste una calibrazione. Le revisioni, il consenso e le date devono essere distinti dai valori osservati; le stime da dati ufficiali.

## Specificità dei paesi

Il riferimento macchina-leggibile è `validation/macro/G8_CAUSAL_REACTION_COUNTRY_BOOK_V1.json`; contiene tutti e otto i paesi, con meccanismi distinti.

- **USD:** composizione assunzioni/licenziamenti, salari, domanda privata e trasmissione Fed a famiglie/imprese.
- **EUR:** domanda industriale e dei servizi, salari, credito bancario, eterogeneità dell'area euro e BCE.
- **GBP:** salari e servizi, mutui, reddito reale, shock inflazionistici e compromessi BoE.
- **JPY:** ciclo salari-prezzi, domanda interna, normalizzazione BoJ, costo delle importazioni e carry.
- **CHF:** domanda estera, inflazione, cambio come condizione monetaria, SNB e domanda di bene rifugio.
- **CAD:** famiglie indebitate, rinnovo mutui, occupazione, petrolio, commercio USA e BoC.
- **AUD:** inflazione domestica/lavoro, leva delle famiglie, Cina e materie prime, RBA e risk sentiment.
- **NZD:** immobili, repricing mutui, occupazione, inflazione non-tradable, export e RBNZ.

## Esempio esplicitamente IPOTETICO: EUR/GBP

**Europa:** peggiorano ordinativi e prestiti bancari, mentre i salari negoziati si attenuano. Se il rallentamento persiste, la BCE potrebbe avere più spazio per allentare; *ma la domanda e i salari vanno verificati*.  
**Regno Unito:** i consumi si indeboliscono, ma i servizi restano inflazionistici. La BoE potrebbe essere costretta ad aspettare.  
**Confronto:** la narrativa suggerirebbe differenziali di policy più favorevoli alla sterlina. **Non è ancora un trade EUR/GBP short**: occorre misurare i differenziali di tassi impliciti *già prezzati*, la sorpresa delle successive pubblicazioni e le reazioni relative di 2Y e cambio. Controllare anche pressione sul credito UK e possibilità che la BoE reagisca più rapidamente di quanto il consenso anticipi.

Nessuno di questi eventi viene affermato come dato del 9 novembre 2026. È solo un esempio della struttura del ragionamento.

## Sviluppo e confini

1. **Progettato ora:** specifica G8 comune, con meccanismi e mandati differenziati, senza score/forecast inventati.
2. **Da implementare come ricerca:** adattatori ai dati G8 esistenti, con timestamp di pubblicazione, qualità e finestre comparabili.
3. **Da verificare:** una reale narrativa per ciascuna valuta e un audit indipendente su dati ufficiali, aspettative e alternative. Testare la capacità di distinguere *driver* da correlazioni.
4. **Solo dopo:** pubblicazione dentro le sezioni esistenti Macro/Valute/Coppie. Niente nuove pagine, niente duplicazioni e nessun cambiamento al Core delle 28 coppie senza validazione.

**Regola guida:** una storia plausibile spiega il *perché*, ma senza dati e repricing non dimostra un vantaggio operativo.
