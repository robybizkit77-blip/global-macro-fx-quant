# Macro V2 — dieci coppie con 2Y e fixing BCE su date settimanali identiche

**Rilevazione del 31 ottobre 2026. Ricerca ex-post, non nuovo Core né segnale FX.**

## Domanda economica

Il differenziale dei 2Y può muoversi in direzione relativamente favorevole a una valuta mentre il relativo fixing spot BCE si muove in direzione opposta? Per rispondere occorrono due date identiche fra tutte e quattro le osservazioni: tasso 2Y base e quotata al momento iniziale/finale, e fixing FX delle medesime date. I campi di riepilogo "chg2_bp" non hanno un orologio dimostrato uniforme e **non sono utilizzati**.

Questa è una verifica osservazionale, NON una valutazione della reazione intraday a una notizia, né un rendimento investibile. Gli orari del fixing BCE e dei rendimenti non coincidono necessariamente; i 2Y governativi hanno convenzioni e basi nazionali differenti. Sono fonti archiviate nel repository alla data dell'audit, non vintage storiche complete point-in-time.

### Finestra esatta: 22–29 ottobre 2026

Cinque valute hanno un 2Y presente su entrambe queste date: **USD, EUR, GBP, JPY, CAD**. AUD è fermo al 28/10, NZD al 16/10, CHF al 30/09; non interpoliamo né anticipiamo i loro rendimenti. Risultato: **10/28** coppie ammesse, **18/28** escluse.

Il prezzo FX orientato base/quote viene ricostruito dai fixing BCE, che sono espressi in unità per EUR. Usiamo solo l'orientamento canonico della coppia: prezzo(base/quote) = ECB[quote] / ECB[base].

- Delta differenziale 2Y (bp) = 100 × [(2Y base finale − base iniziale) − (2Y quote finale − quote iniziale)].
- Variazione FX (%) = 100 × [prezzo base/quote finale / prezzo iniziale − 1].

| Coppia | Delta spread 2Y, pb | FX base/quote, % | Segno descrittivo |
|---|---:|---:|---|
| CAD/JPY | +15,30 | +0,92 | Stesso |
| EUR/CAD | −13,95 | −0,94 | Stesso |
| EUR/GBP | −2,83 | −0,23 | Stesso |
| EUR/JPY | +1,35 | −0,03 | Opposto |
| EUR/USD | +4,05 | −0,67 | Opposto |
| GBP/CAD | −11,12 | −0,71 | Stesso |
| GBP/JPY | +4,18 | +0,20 | Stesso |
| GBP/USD | +6,88 | −0,44 | Opposto |
| USD/CAD | −18,00 | −0,27 | Stesso |
| USD/JPY | −2,70 | +0,65 | Opposto |

**6/10** coppie hanno segno concorde e **4/10** opposto. Non è una metrica di accuratezza: le coppie condividono valute, non sono campioni indipendenti e non esiste una previsione preregistrata da giudicare. Un movimento del 2Y non equivale a sorpresa monetaria: crescita, inflazione, liquidity premium e convenzioni dei rendimenti contano.

## Perché questo non risolve ancora il Core

- Il vecchio modello Macro è del **25/09**; il fixing EUR FX del 30/10 è aggiornato indipendentemente.
- La prima formula domestica Macro V2 aveva **0/28** contrasti FIRM/SOFT robusti a tutti e tre i pesi 25/50/75%. Non usarla per produrre ranking FX.
- Mancano vintage PIT storiche complete, e gli strumenti governativi 2Y (Treasury par / curve spot / bond benchmark) non sono perfettamente omogenei.
- Le OIS 6M non sono allineate allo stesso intervallo per ogni valuta.
- Prima osservazione reale Forward V2 Quality-Aware possibile dal **2 novembre dopo le 19:00 Roma**, non prima.

## Artefatto operativo

Il modulo di ricerca validation/macro/v2_fx_exact_weekly_2y_ecb_context_v1.py cerca la più recente finestra di sette giorni esatti con fixing BCE e almeno due valute con 2Y ufficiali alle medesime due date. Il suo test esercita orientamento invertito, dati mancanti, valori invalidi, duplicati, orologi incompatibili e assenza di mutazioni. La ricerca è solo manuale/PR, senza nuovi cron e senza scrivere in Core, live_data, payload, Pages o Forward.

**Passo successivo:** preregistrare ipotesi e cutoff prospettici, distinguere livello e repricing monetario, ed effettuare veri test out-of-sample soltanto quando matura una coorte sufficiente.
