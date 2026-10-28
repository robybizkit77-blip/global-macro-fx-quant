# Macro V2 — Repricing 2Y con date effettive e ammissione delle sorprese macro
**28 ottobre 2026 · Ricerca separata dal Core e dalle 28 tesi operative**

## Cosa abbiamo scoperto, concretamente

L'ultimo snapshot dei rendimenti sovrani 2Y contiene sia uno storico
con date osservate, sia un campo sintetico \`chg2_bp\`. Non possiamo
assumere che \`chg2_bp\` significhi sempre «ultima osservazione meno
precedente»: confrontandolo con le ultime due osservazioni dello
storico ufficiale risultano **cinque incompatibilità**:

| Valuta | Ultima data 2Y archiviata | Delta ultime due osservazioni (bp) | chg2_bp in riepilogo | Scarto |
|---|---|---:|---:|---:|
| 🇺🇸 USD | 27 ott | +2,00 | −9,0 | −11,00 |
| 🇪🇺 EUR | 26 ott | +4,19 | −2,8 | −6,99 |
| 🇯🇵 JPY | 27 ott | 0,00 | −2,1 | −2,10 |
| 🇨🇭 CHF | 30 set | −5,80 | −3,7 | +2,10 |
| 🇨🇦 CAD | 26 ott | +15,00 | +4,0 | −11,00 |

GBP, AUD e NZD hanno valori numericamente compatibili con la
differenza delle due ultime osservazioni, ma anche qui non è
certificata la definizione temporale del campo di riepilogo.
Il problema è **un mancato chiarimento del riferimento
temporale**, non la prova che il dato fonte sia scorretto.
Nessun dato è stato sovrascritto.

### Soluzione verificabile per confrontare due 2Y

Il nuovo auditor considera ogni coppia FX solo se:
1. entrambi i rendimenti 2Y hanno **la stessa data finale**;
2. esiste **la stessa data iniziale** realmente osservata
   in entrambe le serie;
3. l'intervallo tra le due date non supera **7 giorni di calendario**;
4. non vengono interpolate, riempite o spostate date mancanti.

Dopo questi controlli risultano **4 coppie su 28** con
una *variazione di differenziale di rendimento 2Y* misurabile
sullo stesso identico intervallo storico:

- **EUR/GBP:** dal 23 al 26 ottobre.
- **EUR/CAD:** dal 22 al 26 ottobre.
- **GBP/CAD:** dal 22 al 26 ottobre.
- **USD/JPY:** dal 26 al 27 ottobre.

La differenza è calcolata come
\`(2Y_base_end-2Y_base_start)-(2Y_quote_end-2Y_quote_start)\`
moltiplicata per 100 punti base per punto percentuale.
Sono **valori descrittivi**, non un segnale FX:
Treasury par, curve zero-coupon e titoli governativi
degli altri paesi hanno metodologie/sottostanti differenti,
e non è ancora verificato il loro archivio di pubblicazione
originaria in senso PIT.

Nessuna differenza può essere presentata come immediata
reazione del prezzo a una notizia priva di confronto
intraday prima/dopo il timestamp del comunicato.

### Repricing OIS 6 mesi: la fonte da sola non basta

GBP, JPY, CAD e AUD dispongono di 6M ufficiali.
Per CHF/EUR/USD/NZD alcune informazioni sono soltanto
indicative o stimate; anche quando appare un campo
\`change_1w_bp\` per una fonte ufficiale, non è stato
ancora certificato un **intervallo inizio/fine e scadenza
omogenei tra entrambe le gambe della coppia**.
**0** delta relativi 6M abilitati come repricing FX
sincronizzato in questo audit. Conserveremo i singoli
delta informativi, chiarendo la loro qualità.

### La sorpresa macro non è un dato «ultimo vs precedente»

Il repository conserva oggi due consensus previsionali
secondari per eventi confermati nel calendario ufficiale
del **30 ottobre**:

- USD — Employment Cost Index: consenso **0,8%**;
- CAD — PIL mensile: consenso **0,2%**.

Sono **consensi pre-release**: nessun actual ufficiale
è stato ancora collegato a questi eventi, il calendario
ufficiale contiene data e titolo ma non valore/consenso.
Non siamo autorizzati a calcolare *actual - consensus*
prima della pubblicazione, né a sostituire i dati
precedenti al consenso. Un sistema che producesse
oggi «sorpresa» darebbe **un risultato inventato**.
L'ammissione richiederà consenso datato *prima*
dell'orario del comunicato, actual ufficiale con
unità economica coerente, precedenti/revisioni
e timestamp di disponibilità.

### CB Want / Can

La distinzione approvata Want/Can (focus principale
della banca centrale e vincoli reali che ne limitano
la capacità di azione) resta **qualitativa**: per
attribuirla a una singola decisione servono fonti
ufficiali delle banche centrali. Non basta sapere
che il 2Y o il tasso di riferimento è salito.
Il nuovo controllo riporta **0** collegamenti
Want/Can da testo monetario attestato; non ne
inventa alcuno.

## Stato dello sviluppo quantitativo

Il lavoro precedente (#727–#729) ha trovato:
- candidato nazionale 50% crescita, 50% lavoro
  riproducibile ma instabile ai pesi per 4 G8;
- nessuna delle 28 coppie mantiene un contrasto
  FIRM/SOFT in tutte e tre le combinazioni di pesi;
- zero bundle completi 2Y+OIS ufficiale sincronizzati.

Questa fase aggiunge **un confronto storico 2Y
con tempi controllati** e un controllo su che cosa
costituisce davvero una sorpresa macro.
Non aumenta magicamente le serie PIT, né rende
attendibile il modello FX.
Prima di calcolare punteggi relativi occorre definire
una funzione di risposta verificabile rispetto al
mercato (sorpresa → CB Want/Can → OIS/2Y →
FX relativo) e testarla su dati e timestamp reali.

## Protezioni

- Script: \`validation/macro/v2_fx_2y_repricing_surprise_admission_v1.py\`
- Test: \`validation/macro/test_v2_fx_2y_repricing_surprise_admission_v1.py\`
- CI **solo pull request/manuale**, niente nuovo
  aggiornamento programmato o stime arbitrarie.
- Output: file temporaneo sotto \`/tmp\`.

Non sono modificati \`live_data\`, il Core \`D.json\`,
le 28 decisioni operative, i rendimenti archiviati,
le schede dei tassi, Beta, Forward, dashboard,
GitHub Pages o notifiche chat. Il CI GREEN
dimostra la correttezza del confronto temporale
e del blocco dei falsi segnali, **non** prova
capacità predittiva.
