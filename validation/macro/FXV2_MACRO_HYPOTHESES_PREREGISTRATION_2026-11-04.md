# FX Quant V2 — protocollo Macro Hypotheses V1 (4 novembre 2026)

**Perimetro:** ricerca isolata. Nessun nuovo segnale FX, ranking, ordine, modifica a `D.json`, Forward, Beta, sito o scheduler. La baseline Macro V1 disponibile è una fotografia revisionata **non PIT**.

## 1. Prima diagnosi: che cosa è confrontabile oggi?

La metrica `descriptive_coverage_pairs` del modulo
`validation/macro/fxv2_macro_hypothesis_coverage_v1.py` significa soltanto
che entrambe le valute hanno dati con **lo stesso periodo economico**
(e, dove rilevante, stessa frequenza), non che il fattore sia predittivo.

Nel file pubblicato del 4 novembre: 15/28 contrasti disoccupazione,
11/28 inflazione, 1/28 accelerazione PIL; **0/28** coppie con tutte e tre.
Per l'accelerazione PIL il solo confronto presente è EUR/USD.
Questa copertura cambierà con le pubblicazioni successive e non va
congelata come risultato universale.

**Caveat:** date del mese/trimestre economico non sono i timestamp delle
pubblicazioni. Le variazioni su tre intervalli NON sono necessariamente
tre mesi per tutte le economie. Le righe revisionate non diventano PIT.

## 2. Ipotesi preregistrate (nessun peso calibrato, nessun FX forecast)

**H0 — Labour change, controllo semplice.**
Confronto descrittivo `-Delta U_base + Delta U_quote`: una disoccupazione
che diminuisce più rapidamente è, a parità di altro, un possibile segno di
tenuta relativa del lavoro. Il segno **non implica apprezzamento FX**; la
relazione con FX resta da testare. Il modello serve da baseline macro.

**H1 — Attività: Growth + Labour.**
Proseguire il precedente esperimento domestico
`A_c(w) = w * z_GDP_c - (1-w) * z_Unemployment_c`, con
`w = 0.25 / 0.50 / 0.75`, senza scegliere ex post il peso vincente.
Gli z devono derivare da finestre rolling disponibili *prima* del
cutoff; l'esperimento attuale non ne produce di nuovi dalla fotografia
revisionata. Il contrasto base-quote di questi z non è automaticamente
una scala FX internazionale comparabile.

**H2 — Activity + Inflation context.**
È H1 condizionata dalla pressione prezzi, **non** la formula
`activity + inflation`: inflazione più alta può favorire tassi più
alti oppure segnalare perdita di potere d'acquisto. Si devono misurare
prima le risposte dei policy rates e i diversi regimi. L'attuale
controllo di completezza richiede tutti e tre gli assi allineati.

**H3 — Activity + OIS policy repricing.**
Estensione condizionata dal *cambiamento congelato* del pricing OIS
6M relativo base/quote, non dal solo livello OIS e non da una stima
corrente. Richiede stesso benchmark, timestamp della rilevazione,
qualità e osservazioni precedenti congelate. Nessuna serie di shock
OIS storici in Macro V1: **0/28 eleggibili** qui. Non sostituire in
silenzio futures, 2Y governativi o proxy come se fossero OIS.

Queste quattro famiglie sono preregistrate come **ipotesi**, non come
modelli già stimati. La copertura del confronto descrittivo resta
distinta dall'ammissibilità al training PIT, che è **zero** per tutte.

## 3. Protocollo di falsificazione futura

- **Target primario:** rendimento logaritmico della coppia FX sul solo
  orizzonte 1W, prezzo base/quote da fixing BCE congelato T0 e primo
  fixing verificato dopo maturazione; niente interpolazioni.
- **Cutoff:** per ciascuna previsione, tutti i valori macro, revisioni,
  2Y, OIS e FX devono avere timestamp di pubblicazione/acquisizione
  non successivo al congelamento della previsione. Lo snapshot
  revisionato del 4 novembre non può essere usato per ricostruire
  artificialmente le previsioni del passato.
- **Benchmark:** FX momentum T0 precedente→T0 e protocollo rates-only
  `V2-H1-2Y-REPRICING-1W-V1` già preregistrato, sulla **stessa
  popolazione ammissibile**. Confrontare le famiglie macro anche con un
  nullo/nessun segnale, non solo tra loro.
- **Campionamento:** acquisizioni prospettiche complete; non chiamare
  28 cross della stessa giornata 28 osservazioni indipendenti.
  Aggregare prima nella giornata, poi lungo giornate. Rendimenti a 1W
  sovrapposti → incertezza a blocchi consecutivi di 10 giornate,
  sensibilità 20. Nessuna significatività con campione insufficiente.
- **Soglie:** nessun claim formale prima di 120 distinti giorni Roma
  valutabili con outcome maturato per il protocollo; anche allora
  effettuare validazione temporale OOS, controllo multi-ipotesi e
  robustezza ai regimi. Il criterio 120 giorni è un *minimo di
  valutabilità*, non garanzia di potenza statistica.
- **Ottimizzazione:** se un peso verrà adattato, solo dentro le finestre
  di training walk-forward; mai scegliere i parametri dopo aver letto
  le performance del test OOS. Separare uso operativo di stime
  trasparenti sul sito da un backtest che pretenda osservazioni PIT.
- **Output ammessi:** coverage, missingness e (quando maturi) esiti
  OOS con incertezza, costi e sensibilità. Fino a quel momento
  `macro_score = null`, `fx_forecast = null`,
  `out_of_sample_skill = null`, `backtest_executed = false`.

## 4. Come eseguire il controllo reale

```sh
python3 -m unittest validation.macro.test_fxv2_macro_hypothesis_coverage_v1 -v
python3 -m validation.macro.fxv2_macro_hypothesis_coverage_v1 --output /tmp/fxv2-macro-hypotheses-v1.json
```

Il modulo **legge soltanto** `site/fx-quant-v2/macro-baseline-candidate-v1.json`
e non crea né modifica file nel repository. L'output in `/tmp` non
entra in GitHub Pages e non è una fonte per i 28 segnali.
