# Macro V2 — replay giornaliero delle 24 evidenze economiche G8

**27 ottobre 2026 — ricerca in sola lettura, non un nuovo punteggio Macro FX.**

## Risultato

Il modulo `validation/macro/v2_g8_24_axis_daily_release_replay_v1.py` ricostruisce per **ogni giorno UTC completo** dal 1° luglio 2026 a ieri una fotografia delle ultime pubblicazioni economicamente conoscibili sulle otto economie G8, organizzate in Growth, Inflation, Labour (24 assi). L'intervallo è modificabile, ma limitato a 190 giorni per controllare costi e dimensione; i giorni ancora in corso non vengono mai considerati conclusi alle 23:59 UTC.

Per ciascuna data conserva **tutte le 24 caselle**, anche quelle senza evento attestato, e distingue:
- Primo valore pubblicato, ultimo valore revisionato noto alla data, riferimento economico (mese/trimestre) e origine ufficiale.
- Provenienza della serie e limiti: EUR inflazione nell'archivio flash di 105 mesi (EA19/20/21), AUD inflazione vera serie trimestrale di 34 trimestri, CHF lavoro solo SECO 3,1% arrotondato e non prima versione SNB esatta.
- L'eventuale cambiamento rispetto a ieri, insieme agli **eventi ufficiali documentati avvenuti il giorno del cambiamento**. Le revisioni non retrodatano il passato; una prima pubblicazione non esiste prima del suo gate.
- Giornate senza nuove uscite: i valori precedenti restano **ultime informazioni note**, senza creare osservazioni economiche aggiuntive, fare interpolazione né implicare che il mercato sia stato influenzato da una notizia.
- Raggruppamento per valuta della disponibilità giornaliera (0–3 pilastri visibili), senza paragonare timestamp di riferimento trimestrali con mensili.

## Controlli falsificabili

- Eurostat settembre 2026: non prima del 3 ottobre, 00:00 UTC; esegue il confronto 2→3 ottobre.
- SECO settembre 2026: prima disponibilità prudente 7 ottobre, 00:00 UTC; **un dato 3,1%** non rappresenta il numero preciso della prima SNB.
- CPI trimestrale ABS Q2 2026: non prima del 29 luglio 01:30 UTC; il mensile ABS resta separato.
- GDP USD: il primo valore annualizzato BEA si converte correttamente in QoQ; le revisioni vengono esposte **solo dalla data della loro uscita**, senza sostituire i vecchi headline.
- Blocca source IDs inattesi, timestamp non UTC, dati futuri, giorni incompleti, eventi che fanno variare un valore senza pubblicazione attestata, modelli/FX scores arbitrariamente “certificati”, mutazioni a D e 28 coppie.

**Importante sulla qualità:** le fonti attuali coprono le più recenti pubblicazioni, ma il dossier ufficiale di tutti i 24 assi NON ha ancora un archivio completo di prime uscite originali e revisioni per tutta la finestra di training. La ricostruzione è cronologica **nei limiti degli eventi documentati**, non una certificazione PIT piena, un backtest economico, un Beta o un Forward Test. Le date ricostruite e la copertura non sono una stima di rendimento FX.

## Riproduzione e messa a disposizione

```sh
python -m unittest validation.macro.test_v2_g8_24_axis_daily_release_replay_v1 -v
python -m validation.macro.v2_g8_24_axis_daily_release_replay_v1 --output /tmp/macro-v2-g8-daily-release-evidence.json
```

Il file JSON viene salvato solo come artefatto di ricerca nel workflow GitHub Actions esistente dopo gli aggiornamenti Macro. **Nessun nuovo cron, nessun cambiamento a Control Room, `D.json`, 28 coppie, Beta e Forward Test.**

## Prossimo lavoro che dipende da questo

Estendere **per ogni serie** i primi comunicati storici e le revisioni con fonti persistenti; rendere omogenee le definizioni geografiche Eurostat e gli istanti di pubblicazione SNB, quindi ricalcolare davvero fattori Macro su training cronologico completo e testare sensibilità/out-of-sample. Solo successivamente integrare Rates/OIS/CB Pricing e attivare il nuovo Core.
