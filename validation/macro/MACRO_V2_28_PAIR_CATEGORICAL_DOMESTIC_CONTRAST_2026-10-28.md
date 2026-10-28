# Macro V2 — esperimento 28 coppie: contrasto di attività domestica e stabilità ai pesi
**28 ottobre 2026 · RESEARCH ONLY · nessun segnale FX o nuova classifica.**

## Perché è un controllo diverso dalla precedente matrice fonti

La PR #728 aveva verificato per 28 coppie l'allineamento delle date 2Y e
OIS: **nessun confronto completo 2Y + OIS 6M sincronizzato sulle due
valute**. La PR #727 aveva verificato che il candidato domestico
Growth 50% + Labour 50% era aritmeticamente calcolabile su 8 economie,
ma che **quattro classificazioni nazionali cambiavano con i pesi**.

Questa prova unisce i due risultati **senza** sottrarre i numeri z
di nazioni diverse, senza introdurre un «FX strength» inventato e
senza utilizzare prezzi futuri.

## Metodo registrato *prima* di valutare le performance

La **crescita** riceve i pesi già registrati **25%, 50%, 75%** e
il lavoro riceve rispettivamente **75%, 50%, 25%**. L'inflazione
resta un indicatore **separato**: inflazione alta non significa
acquistare la valuta. Le classi nazionali sono quelle
già approvate per la *ricerca* sulla storia propria:
- **FIRM** se attività z nazionale >= +0,50;
- **SOFT** se attività z nazionale <= -0,50;
- **MIXED** altrimenti.

Per ciascuna delle 28 coppie canoniche la descrizione «attività
domestica opposta» si manifesta **solo** se una è FIRM e l'altra
SOFT. Altri confronti diventano «nessuna opposizione netta».
Questo è **un contrasto di categorie**, non un confronto di
entità economiche direttamente calibrate in termini di valuta.

Uno scenario è «persistente» soltanto quando **tutti e tre**
i pesi danno la stessa categoria opposta (stessa direzione
base/quote). È «sensibile» se l'opposizione compare solo
in una parte degli scenari; altrimenti nessuna opposizione.

## Esito numerico effettivo — NON è un risultato di trading

| Gruppo descrittivo | Coppie |
|---|---:|
| Attività domestiche opposte e stessa categoria in TUTTI 3 i pesi | **0 / 28** |
| Opposizione nazionale in 1 o 2 scenari; scompare almeno una volta | **9 / 28** |
| Nessuna opposizione nazionale FIRM/SOFT nei tre scenari | **19 / 28** |
| Almeno una riserva sulle fonti o una componente stimata | **18 / 28** |
| Bundle 2Y + OIS ufficiale con date coincidenti su entrambe le valute | **0 / 28** |
| Nuovi ranking/segnali/previsioni FX e OOS autorizzati | **0** |

Le nove coppie con interpretazione sensibile al peso sono:

| Coppia | Growth 25% | Growth 50% | Growth 75% | Qualità |
|---|---|---|---|---|
| AUD/CAD | AUD SOFT / CAD FIRM | AUD SOFT / CAD FIRM | nessuna opposizione | Nessun flag aggiuntivo |
| AUD/CHF | nessuna opposizione | AUD SOFT / CHF FIRM | nessuna opposizione | Caveat |
| GBP/AUD | GBP FIRM / AUD SOFT | GBP FIRM / AUD SOFT | nessuna opposizione | Nessun flag aggiuntivo |
| GBP/NZD | GBP FIRM / NZD SOFT | GBP FIRM / NZD SOFT | nessuna opposizione | Nessun flag aggiuntivo |
| GBP/USD | nessuna opposizione | GBP FIRM / USD SOFT | GBP FIRM / USD SOFT | Caveat |
| NZD/CAD | NZD SOFT / CAD FIRM | NZD SOFT / CAD FIRM | nessuna opposizione | Nessun flag aggiuntivo |
| NZD/CHF | nessuna opposizione | NZD SOFT / CHF FIRM | nessuna opposizione | Caveat |
| USD/CAD | nessuna opposizione | USD SOFT / CAD FIRM | USD SOFT / CAD FIRM | Caveat |
| USD/CHF | nessuna opposizione | USD SOFT / CHF FIRM | USD SOFT / CHF FIRM | Caveat |

**Le etichette FIRM/SOFT qui dicono soltanto «più/meno
attiva rispetto alla storia di quella specifica economia».**
NON significano LONG o SHORT le coppie indicate.

### Interpretazione e limite centrale

La classificazione di attività domestica **non discrimina
stabilmente nessuna delle 28 coppie** ai tre pesi preregistrati.
Ciò falsifica la pretesa di usare direttamente questa regola
semplificata come screening FX comparativo robusto.
Non dimostra che i mercati FX siano privi di segnali macro:
il loro prezzo dipende anche da **differenziale di sorprese,
politica monetaria attesa, CB Want/Can, OIS/2Y e relativo
repricing, 10Y real/term premium, rischio globale, COT e prezzo**.

Non ottimizziamo oggi i pesi per far emergere coppie «migliori»:
sarebbe un adattamento retrospettivo senza controllo OOS.
La prova **non** dispone di vintage PIT pienamente
certificati né di osservazioni di performance del nuovo
modello. Da sola non costruisce un candidato operativo.

## Passaggio successivo che serve davvero

Non ripetere ogni volta il confronto 50/50 o altri micro audit.
Per avanzare verso un Core versione nuova, serve **una
definizione preregistrata del confronto relativo** che separi:
1. attività domestica *e differenziale di sorprese* misurati
   con metriche coerenti tra valute;
2. focus della banca centrale **Want** e vincoli **Can**
   ricavati da fonti monetarie verificabili;
3. **repricing**, non solo livello, dei tassi attesi 3M/6M
   e del 2Y, con date allineate e basi comparabili;
4. driver del 10Y e rischio globale come modificatori
   espliciti e qualitativi quando mancano serie omogenee;
5. falsificabilità: benchmark neutro, test di stabilità,
   block/permutation robustness, serie storiche PIT
   disponibili alla decisione e poi vero Forward OOS.

Finché le componenti non saranno realmente confrontabili,
si può esporre **l'incertezza e le stime etichettate**, ma
**non** attribuire numeri FX di forza confrontabile.

## Artefatti e protezioni

- Modulo \`validation/macro/v2_fx_28pair_domestic_categorical_contrasts_v1.py\`:
  tre pesi × 28 coppie, orientamento canonico, zero
  differenze di intensità macro tra nazioni.
- Test \`validation/macro/test_v2_fx_28pair_domestic_categorical_contrasts_v1.py\`:
  invertibilità base/quote della sola categoria,
  indifferenza all'inflazione come voto FX, scenario
  FIRM/MIXED/SOFT, fonti stimate, aggiornamenti
  vietati e archivi immutati.
- CI pull-request **senza scheduling** e ricevuta
  \`/tmp/gmfq-v2-28-pair-domestic-categorical-contrast-2026-10-28.json\`.

**Non modificati**: \`live_data\`, \`D.json\`, prezzi, 28 pair,
sito, selezione, Beta, Forward, orari, alert.
Un green CI con questo risultato **non certifica**
l'efficacia predittiva o un nuovo score FX.
