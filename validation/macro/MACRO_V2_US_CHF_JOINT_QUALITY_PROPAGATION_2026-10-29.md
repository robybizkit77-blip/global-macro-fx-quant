# Macro V2 — due lacune residue, trasferimento dell'incertezza al candidato domestico
**29 ottobre 2026 · ricerca, non modello FX approvato.**

## Obiettivo effettivo
I precedenti controlli hanno già documentato 22/24 finestre numeriche first-web continuative, e 0/24 training vector con storia congiunta PIT indipendentemente certificata. Evitiamo di "riempire" a mano le due caselle con un valore che la fonte non ha mai pubblicato.

Questa fase stressa l'effetto sul **candidato domestico preregistrato**, non sul vecchio Core. In particolare:

- **USD.inflation** — si confrontano lo z YoY derivato dagli indici BLS SA nei fogli del relativo mese (acquisiti tardivamente) e lo z del medesimo orizzonte dalla serie CPIAUCSL oggi revisionata. I 24 mesi di training sono 24 osservati su 25 di calendario, **ottobre 2025 assente**. Si registra la differenza quantitativa e si può verificare se la sola *classe descrittiva* è coerente; la qualità PIT, gli orologi e la continuità restano non certificate. Nel candidato approvato per la sola ricerca, l'inflazione è **asse separato** dall'attività, e non viene usata per attribuire forza al dollaro.
- **CHF.labour** — si prende lo **z dei primi rapporti SECO arrotondati** (21 PDF con byte recuperati oggi, quattro testi originali indicizzati soltanto), con intervallo conservativo che riflette ±0,05 punti percentuali sulla stampa. Si inverte il segno in modo puramente aritmetico per la variabile *tensione del lavoro* e lo si propaga alla formula **attività = w·Growth + (1−w)·tensione del lavoro**, con w fisso al 50% e in un intervallo di sensibilità già preregistrato [25%,75%]. Gli estremi vengono da quattro vertici del rettangolo peso × tasso SECO. La prima serie SECO arrotondata e lo storico corrente SNB preciso sono **fonti alternative non intercambiabili**: i valori ottenuti sono scenari, non una revisione del candidato e non una stima di una vintage esatta SNB.

## Cosa misura il test e cosa non misura
Un confronto tra due misure descrittive può dare una classe uguale senza dare un'affidabilità predittiva. Analogamente, un intervallo di scenari che attraversa la soglia di classe significa **"non robusto in questo stress"**, non autorizza a scegliere l'estremo favorevole. L'intervallo conservativo non è un intervallo di confidenza e non pretende che gli estremi siano effettivamente raggiungibili da una precisa storia originale.

L'algoritmo rifiuta discrepanze di fonte, falsi PDF verificati, variazione dei pesi registrati, valori SNB inventati e promozione delle classi a FX. Produce **solo una ricevuta sotto /tmp**, in un workflow di ricerca già presente, con test adversariali e controllo delle scritture.

## Esito atteso per la pubblicazione
Il verdetto sarà verificabile nel log CI, che emette z USD, intervallo SECO CHF e attività alternativa. Anche se qualche classe risultasse stabile, **non** viene pubblicata alcuna nuova valutazione FX; il candidato non diventa Core `D.json`, non modifica le 28 coppie, Beta o Forward, e non apre nuovi cron o task.

Prossimo ostacolo per un Core realmente vivo: scegliere i fattori e le unità economicamente coerenti fra otto paesi, disporre di un archivio temporalmente valido e confrontare la capacità predittiva fuori campione con benchmark. Non ripetere la ricerca di una inesistente statistica BLS ottobre 2025.
