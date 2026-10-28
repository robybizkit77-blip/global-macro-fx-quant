# Macro V2 — dalle 8 economie alle 28 coppie FX: sincronizzazione delle fonti
**28 ottobre 2026 · controllo quantitativo di ricerca, NON ranking o modello operativo.**

## Risultato: prima bisogna avere le stesse date e strumenti confrontabili

Per passare da una valutazione macro **nazionale** a un vero confronto
**tra due valute** non basta sottrarre due z-score: ciascuno è calcolato
sulla storia della propria economia e non è una misura calibrata della
forza FX. Il nuovo candidato descrittivo usa 50% crescita e 50% lavoro;
l'inflazione è un asse separato. Un punteggio di inflazione elevata
NON implica un acquisto della valuta, perché conta come la banca
centrale reagisce e cosa il mercato ha già prezzato.

Per un modello FX servono anche i livelli/variazioni di
**CB pricing / OIS**, 2Y, struttura del 10Y e differenziali,
posizionamento, rischio e prezzo, con **prova della disponibilità
dei dati prima della decisione** e test indipendente su esiti FX.

Questo audit fotografa l'ultima base del repository
(al momento **prezzi FX fino al 27 ottobre 2026**, Core fermo al
**25 settembre 2026**) e **non afferma l'esistenza di nuove
quotazioni di mercato oggi 28 ottobre**.

## Prima matrice automatica delle 28 coppie G8

| Verifica | Risultato | Interpretazione |
|---|---:|---|
| Valute e coppie coperte | 8 / 28 | Universo completo |
| Paesi con 6M OIS/futures di qualità ufficiale nel sito | 4 / 8 | GBP, JPY, CAD, AUD |
| Paesi con livelli soltanto indicativi o non disponibili (non certificati OIS) | 4 / 8 | USD, EUR, CHF, NZD |
| Valute con 2Y e OIS ufficiale della **stessa data** | 2 / 8 | GBP, JPY |
| Coppie con 2Y pubblicati **nella stessa data** | 4 / 28 | Differenza 2Y solo descrittiva |
| Coppie con entrambe 6M ufficiali, ma date non necessariamente uguali | 6 / 28 | Qualità fonte, non comparabilità temporale |
| Coppie con 6M ufficiali **nella stessa data** | 3 / 28 | Osservazioni nominali, non delta policy certificati |
| Coppie con **2Y e 6M ufficiali**, tutti sincronizzati tra le due valute | **0 / 28** | Nessun bundle completo |
| Nuovi punteggi forza FX certificati | **0** | Non inventare un ranking |

I **quattro** confronti 2Y con la stessa data non diventano
automaticamente spread di politica monetaria confrontabili:
gli strumenti possono avere curve, convenzioni e componenti
di premio per il rischio differenti. I **tre** confronti 6M
ufficiali condividono il giorno riportato, ma il contratto e
il fixing di riferimento possono differire. La sincronizzazione
delle date è un controllo necessario, **non sufficiente**.

I valori EUR/USD indicativi di futures restano visibili come
**contesto stimato**; CHF/NZD possono avere altri proxy direzionali,
ma non vanno spacciati per OIS istituzionali.
Nessuna osservazione sconosciuta diventa 0, nessun dato di
settembre diventa "fresco" solo perché è stato riletto oggi.

## Esempi concreti leggibili senza segnale

- **EUR/GBP:** 2Y allineati al **26/10/2026**: differenziale
  osservabile, *descrittivo e con basi strumentali diverse*;
  6M EUR indicativo, GBP ufficiale => **non confrontabile come OIS**.
- **AUD/JPY:** 6M ufficiali al **27/10/2026**; 2Y AUD osservato
  al **21/10** contro JPY **27/10** => niente
  confronto 2Y sincronizzato. Nemmeno l'OIS nominale 6M
  è un segnale FX se manca la reazione a nuove notizie.
- **GBP/JPY:** due fonti ufficiali OIS, ma date rispettivamente
  **26/10** e **27/10**: mai costruire uno spread *same day*
  con questi due livelli.
- **CHF/NZD:** i livelli/delta ufficiali OIS non sono certificati;
  conservare i proxy qualitativi con avviso esplicito e
  senza promozione implicita.

## Che cosa abbiamo deciso sui pesi?

**Nessuna nuova scelta di pesi FX.**
I pesi 50/50 del candidato sono *nazionali*,
non la combinazione Macro+Rates per comprare una valuta.
La precedente validazione ha dimostrato che **4 valute su 8**
cambiano classe domestica se il peso growth passa da 25% a 75%.
Prima di assegnare pesi FX bisogna preregistrare:
- definizione **comparabile** delle feature e loro disponibilità;
- cosa vuole la banca centrale (preoccupazioni primarie)
  contro cosa può fare (vincoli inflazione/lavoro);
- differenziale di **repricing**, non solo livello di tasso,
  e distinzione tra front-end e 10Y;
- trattamento di COT, prezzo e rischio come conferme,
  non come variabili presunte causali;
- test fuori campione dei 28 pair su dati disponibili all'epoca,
  con confronti contro benchmark e finestre non sovrapposte.

La distinzione **Want/Can** rimane utile ma **non può essere
dedotta automaticamente dai soli 2Y/OIS**: serve attestazione
di comunicati delle banche centrali e contesto macro.

## Intervento software

\`v2_fx_28pair_synchronized_evidence_gate_v1.py\`
genera 28 righe con data di ogni 2Y e 6M OIS,
provenienza ufficiale/indicativa,
differenziali numerici solo quando entrambe le date
corrispondono, sempre **etichettati come descrittivi**.

Le 28 coppie rispettano l'orientamento ufficiale del sito;
non modifica i nomi, prezzi o tesi delle coppie.
Test avversariali rifiutano date future, falsi OIS certificati,
cambiamenti di baseline e valute non valide.
Si collega alla PR #727 (Core quant readiness): mai
promuovere l'interpretazione a FX strength, Beta o Forward.

**Cosa manca:** normalizzare basi 2Y/risk-free e disponibilità
storiche 6M, costruire un modello comparativo economicamente
coerente preregistrato, test PIT e vero OOS.
Il lavoro non riguarda altre 24 ricerche CPI e non sblocca
per magia \`D.json\`.

## Esecuzione

\`python -m unittest validation.macro.test_v2_fx_28pair_synchronized_evidence_gate_v1 -v\`

\`python -m validation.macro.v2_fx_28pair_synchronized_evidence_gate_v1 --as-of 2026-10-28 --out /tmp/gmfq-v2-28pair-2y-ois-synchronization.json\`

Tutto in **/tmp**, nessun aggiornamento a Core \`D.json\`,
28 pairs, sito, Beta, Forward, registri di decisione,
workflow programmati o alert.
