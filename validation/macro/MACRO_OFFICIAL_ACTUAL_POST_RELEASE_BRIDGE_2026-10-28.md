# Macro → consenso congelato → actual ufficiale: collegamento operativo post-release

**28 ottobre 2026. Nessun dato del 30 ottobre è stato ancora pubblicato.**

## Perché questo è operativo e non un'altra semplice analisi

La PR #732 ha congelato realmente i due consensi di prima
dell'annuncio alle **08:35:08 UTC del 28 ottobre**:
- 🇺🇸 ECI USA, costi totali dei lavoratori civili, variazione
  trimestrale destagionalizzata: **+0,8%** (forecast
  SECONDARIO Fair Economy, NON dato ufficiale BLS).
- 🇨🇦 PIL reale canadese per industria, variazione
  mensile di agosto: **+0,2%** (forecast secondario).

Il passo aggiunto adesso alla **pipeline Calendar/News
già programmata** controlla le fonti ufficiali
*soltanto dopo l'ora dell'annuncio del 30 ottobre 2026*.

**Orario corretto in Italia: 13:30 CET del 30 ottobre**,
equivalente alle 12:30 UTC e alle 08:30 di New York
e Toronto. L'ora legale italiana termina domenica
25 ottobre: NON sono le 14:30 italiane.

La nuova acquisizione:
1. legge il registro immutabile con SHA del forecast
   raccolto prima dell'annuncio;
2. attende la **data/ora ufficiale** del rilascio:
   prima non contatta nessuna pagina di actual;
3. consulta BLS Employment Cost Index e soltanto pagine
   del bollettino **The Daily** su Statistics Canada
   del 30/10 (serie di URI candidati, senza
   dichiarare in anticipo che esistano);
4. richiede un testo con **data del comunicato,
   periodo esatto, definizione economica,
   percentuale e unità coincidenti**;
5. non confonde il PIL di agosto con una stima
   anticipata di settembre né ECI costi totali
   con la componente retribuzioni;
6. congela il **primo valore osservato nel runner**
   in \`validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl\`,
   insieme alla fonte, all'ora UTC, all'impronta SHA256
   del documento HTML originale e al riferimento hash
   del consenso immutabile;
7. calcola \`actual − forecast\` in **punti percentuali**,
   mantenendo etichetta SECONDARIA del consenso;
8. se manca il comunicato o il testo non coincide
   esattamente: **nessun actual, nessuna sorpresa inventata**;
9. replica automaticamente il controllo in seguito,
   senza sostituire una prima osservazione con
   una revisione successiva.

Non vengono aggiunti cron o servizi a pagamento:
si usa il workflow Calendar/News esistente.
La cattura degli actual non dipende da
News Pulse RSS: un titolo BLS/StatCan da solo
non contiene il numero necessario.

## Limiti che devono restare visibili

Anche il primo valore registrato da GitHub Actions
è un **first seen del nostro runner**, NON
la prova indipendente dei byte pubblicati al
primo millisecondo dall'istituto. L'URL BLS
del comunicato più recente è aggiornabile
nel tempo e non equivale automaticamente
a un archivio storico first-vintage.

L'informazione \`actual−forecast\` è una vera
**differenza numerica tra due fonti e istanti**,
ma non dimostra:
- che il consenso secondario rappresentasse
  le aspettative di tutto il mercato;
- che OIS, 2Y, FX abbiano reagito in quell'istante;
- che la Fed/Banca del Canada *voglia o possa*
  cambiare tassi a causa del dato;
- che sia appropriato ricalcolare i punteggi Core,
  le 28 coppie, Beta o Forward.

Serve la successiva fase con prezzi/contratti
pre e post comunicato su timestamps
allineati, indicazione di qualità, e se
non disponibili descrizione semplice anziché causalità.

## Test e verifiche

\`python -m unittest validation.macro.test_capture_official_postrelease_actuals_v1 -v\`

\`python -m validation.macro.capture_official_postrelease_actuals_v1\`

I test non fanno richieste network e usano testi
**sintetici etichettati come tali**.
Casi avversariali: prima del comunicato
nessun fetch, mese/serie sbagliati, dati di
stima anticipata confusi col PIL effettivo,
sito indisponibile, doppia cattura,
manomissione di SHA, timestamp assenti,
reazione FX inventata.

I test e il codice sul ramo PR NON pubblicano
informazioni macro operative. In produzione
le prime osservazioni ufficiali sono registrate
nel commit Calendar/News solo se verificabili.
Alla data odierna **0 actual** per il 30 ottobre;
i 2 consensi sono già realmente archiviati.
