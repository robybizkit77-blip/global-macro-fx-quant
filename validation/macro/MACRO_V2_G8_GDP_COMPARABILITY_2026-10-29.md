# Macro V2 — PIL G8: stesso trimestre non equivale a stessa forza valutaria
**29 ottobre 2026 · Esperimento quantitativo di comparabilità, solo ricerca.**

## Domanda da falsificare

Se si classificano otto economie con il PIL reale trimestrale QoQ, l'ordine è identico a quello degli **Z-score** del PIL rispetto ai 12 trimestri precedenti di ciascun paese? Se differisce, quel rango non può essere presentato come una quantità assoluta comparabile né come 'Macro FX Strength' validata.

Il modulo `v2_g8_growth_cross_country_comparability_v1.py` prende **esclusivamente** l'attuale ricevuta delle prime dichiarazioni GDP ufficiali e il candidato domestico preregistrato, senza cambiare alcuna formula.

## Definizioni e limitazioni

- **Stessa variabile economica**: crescita reale del PIL nel **2026Q2**; non output industriale contro PIL, non YoY contro QoQ.
- **USA**: il valore ufficiale SAAR annualizzato è trasformato con `100*((1+SAAR/100)**(1/4)-1)`; gli altri valori sono già variazioni trimestrali (con differenze tra correzioni stagionali e definizioni).
- **Z-score per paese**: valore corrente confrontato con la mediana e MAD delle **12 pubblicazioni iniziali trimestrali precedenti**, senza includere il dato corrente. Una deviazione grande rispetto alla *propria storia* non significa un PIL maggiore in assoluto, né tassi più restrittivi e certamente non prevede FX.
- **Eurozona**: attenzione al passaggio di composizione EA e al suo effetto sulla storia, non colmato dalla formula.
- **Svizzera**: stime flash, correzioni per eventi sportivi e definizioni miste negli storici. Non si normalizza artificialmente la serie.
- **Date**: le 8 dichiarazioni del Q2 sono arrivate tra 30 luglio e 17 settembre; non potevano essere conosciute tutte simultaneamente il 30 luglio. Questo è un confronto descrittivo *dopo* l'ultima pubblicazione, non un modello PIT per l'intero trimestre.
- **Fonte originaria**: archivi web documentati nel repository, ma **zero** archivi originali certificati byte-per-byte all'ora di prima pubblicazione. Le edizioni successive non sostituiscono i valori di prima uscita.

## Confronto esaustivo

Le 28 coppie di paesi vengono considerate senza eccezioni. Per ognuna il sistema calcola la differenza di **PIL QoQ in punti percentuali** e la differenza dei **due Z-score locali**, conservandone le classi `ORDER_AGREEMENT`, `ORDER_INVERSION` o `TIE_IN_AT_LEAST_ONE_REPRESENTATION`.

Una inversione è una controprova concreta all'idea che *crescita più alta questo trimestre* e *crescita più straordinaria rispetto alla propria storia* siano la stessa metrica. Una coincidenza di ordine, invece, **non prova** una relazione con EURUSD o con qualunque altra coppia FX.

I test impediscono di nascondere due economie, scambiare il tasso annualizzato USA per un QoQ, ignorare i caveat EUR/CHF, alterare i pilastri del candidato e dichiarare una qualunque delle 28 comparazioni idonea per un ranking forex.

## Risultato effettivo verificato dal CI del 29 ottobre 2026

Run [#40886683372](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40886683372): 5 test di comparabilità superati. Tutte le **28** combinazioni sono state valutate: **23 accordi di ordine, 2 inversioni, 3 parità** (nella variabile QoQ o z). **13/28** combinazioni includono almeno uno dei due caveat EUR/CHF.

| Valuta | PIL reale 2026Q2 QoQ dopo conversione | Z rispetto ai propri 12 trimestri precedenti |
| --- | ---: | ---: |
| USD | +0,372909% (SAAR di +1,5% convertito) | −1,1463 |
| EUR | +0,4% | +0,6745 |
| GBP | +0,4% | +1,1242 |
| JPY | +0,3% | +0,2248 |
| CHF | +1,5% (definizioni sport/flash miste) | +3,0000 (clipped) |
| AUD | +0,4% | +0,6745 |
| NZD | +0,2% | 0,0000 |
| CAD | +0,8% | +1,4839 |

**Le due inversioni sono USD/JPY e USD/NZD.** Il PIL USA QoQ supera rispettivamente +0,3% e +0,2%, ma la sua deviazione rispetto alla propria storia è nettamente più debole. Le tre parità QoQ emergono dalle tre economie al +0,4% (EUR, GBP e AUD). Non vanno trasformate in ipotesi di direzione dei cross FX.

Osservazioni di contesto: le prime dichiarazioni di GDP 2026Q2 sono state pubblicate in **sette giornate distinte** distribuite su 49 giorni civili. Il rischio di non simultaneità e le differenti metodologie persistono anche dopo la conversione del tasso annualizzato USA; restano **0/28** confronti autorizzati come ranking di forza FX e **0** storici congiunti PIT certificati. **28 confronti diagnostici non sono 28 esperimenti predittivi**.

## Verifica separata della capacità predittiva

Il protocollo H1 già preregistrato per il repricing relativo dei 2Y resta autonomo. Al controllo di oggi (run Forward ECB Reference Outcomes V1 #40883368047), il suo archivio era di **una sola giornata V2**, senza rendimenti 1W maturati e con **zero giornate H1 ammissibili**. Il test richiede almeno 120 giornate pienamente valutabili prima di un'inferenza formale. Le serie 2Y di AUD, CHF e NZD mostravano insufficiente freschezza per l'H1 in quel controllo.

**Nessuna** di queste verifiche fornisce una stima di profitto, Beta, bontà predittiva, direzione di valuta, né autorizza `D.json` o le 28 coppie.

## Dove leggere la prova

- Modulo: `validation/macro/v2_g8_growth_cross_country_comparability_v1.py`.
- Test avversariali: `validation/macro/test_v2_g8_growth_cross_country_comparability_v1.py`.
- Workflow già esistente: `.github/workflows/macro-v2-explicit-formula-candidate-ci.yml`.
- Ricevuta riproducibile: `/tmp/gmfq-g8-gdp-comparability-20261029.json`, artefatto CI.

**Prossimo collo di bottiglia reale**: rendere omogenee statisticamente le definizioni e la conoscibilità all'istante originale, poi accumulare un pannello prospettico post-registrazione con validazione OOS. Non inventare missing BLS, timestamp SNB o rendimenti.
