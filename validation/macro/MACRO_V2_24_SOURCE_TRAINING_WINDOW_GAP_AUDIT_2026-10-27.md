# Macro V2 — audit per valuta della completezza storica (27 ottobre 2026)

## Cosa viene misurato

Il nuovo controllo confronta le **24 componenti G8** con una regola temporale uguale per tutti: la variabile attuale è *fuori dal campione di training* e per normalizzarla servono esattamente **24 pubblicazioni mensili precedenti** oppure **12 trimestrali precedenti** della *stessa metrica*. Non basta possedere 25 o 13 valori disordinati: l'audit calcola **i periodi economici precisi mancanti** all'interno della finestra precedente, e verifica le date di visibilità delle pubblicazioni.

Per ciascuna casella si registrano: serie canonica e **serie realmente usata come evidenza** (anche se diversa), numero totale di prime pubblicazioni visibili, frequenza, ultimo riferimento economico, periodi che mancano rispetto al campione 24M/12Q, possibilità puramente **matematica** di calcolare una statistica e limiti economici della definizione.

## Cosa evitare di confondere

- **8 Growth GDP**: le serie first-web trimestrali documentate possono coprire 12 trimestri antecedenti ma rimangono ricerca, senza archivio immutabile di tutti i byte dei primi comunicati e con riserve EUR (popolazione EA) e CHF (sports/flash).
- **Inflation EUR**: i 105 valori iniziali Eurostat permettono una finestra *numericamente completa* di 24 mesi, **non** una finestra geografica omogenea EA21. La qualità non può diventare “certificata” per effetto della sola lunghezza.
- **Inflation AUD**: gli archivi ABS contengono 34 osservazioni **trimestrali**. Nessuno può dichiarare la serie mensile equivalente al CPI trimestrale del Core.
- **Labour USD**: il dossier BLS della fonte `LNS14000000` è economicamente riconducibile a `UNRATE`, ma non si deve inventare la disoccupazione assente di ottobre 2025 né chiamare “completo” un campione con un mese intermedio saltato. L'identità tra le fonti non completa le vintages.
- **Labour CHF**: il dato ufficiale SECO **3,1% a un decimale** è un'alternativa di ricerca; non è lo storico originale a più decimali SNB. Nessun rounding inverso e nessuna simulazione di un timestamp storico preciso.

La stessa logica è applicata agli altri Paesi. Ogni casella riceve una **qualità nominativa**, fra `INCOMPLETE_PRIOR_FIRST_RELEASES`, `DEFINITION_OR_SEMANTIC_RISK` e `NUMERIC_WEB_WINDOW_AVAILABLE_NOT_PIT_CERTIFIED`. La presenza di una finestra numericamente completa **non** certifica un backtest: il controllo espone sempre **zero serie approvate per training storico PIT** finché non esistono catene complete, riproducibili e omogenee.

## Esito verificato sulla fotografia del 26 ottobre (prima CI)

- **11/24** finestre di first-web research numericamente continue; **13/24** incomplete, con **280 periodi mancanti nelle rispettive finestre richieste** (non 280 pubblicazioni indipendenti, perché le finestre sono per serie).
- **4/24** con caveat di definizione statistica espliciti; **1** pilot BLS di Labour USD storicamente continuo ma **non aggiornato** alle pubblicazioni 2026.
- Il campione BLS di **25 mesi** termina a **settembre 2025**: i 24 mesi precedenti sono completi **per quella data storica**. L'assenza del dato di ottobre 2025 per shutdown avviene *dopo* quel campione e non è un buco della finestra 2023–2025. L'ultimo dato di disoccupazione del 2026 nel sistema osservazionale è un'altra fonte/storia e non diventa automaticamente una prima pubblicazione del pilot. Chi dichiara questo pilot pronto per il Core di ottobre 2026 sbaglia.
- **Zero** storici completamente certificati per training PIT e zero punteggi FX nuovi: completezza matematica ≠ idoneità operativa.

## Come leggere il prossimo risultato

L'obiettivo è avere un elenco concreto, non genericamente “ancora manca lo storico”: una **tabella 24×1** di periodo attuale, prime uscite disponibili, mesi/trimestri mancanti, definizione statistica e intervento successivo. Questa tabella stabilirà dove indirizzare il recupero delle singole pubblicazioni più utili.

## Perimetro

`validation/macro/v2_g8_24_axis_training_history_gap_audit_v1.py` legge le fonti certificate e candidate già raccolte nel progetto, senza scaricare nuovi dati durante il collaudo. Il valore `as-of` di riferimento è **26 ottobre 2026 alle 23:59:59 UTC**, con la giornata completa, senza look-ahead al 27. Le ricevute sono solo ricerca. Nessuna modifica a `D.json`, ranking 28 coppie, sito, Beta, Forward Test o pianificazione.
