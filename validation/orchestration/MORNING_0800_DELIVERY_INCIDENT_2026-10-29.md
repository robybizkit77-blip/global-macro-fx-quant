# Control Room v10 — 29 ottobre 2026, incidente consegna 08:00 Europe/Rome

**Ambito**: precisione del dato, fonte ufficiale, tasso d'aggiornamento e prova pubblica dei byte. Nessun modello FX ricalcolato per coprire un problema operativo.

## Due errori di validazione distinti, riproducibili

**1. Orchestratore, fase contrattuale.** I run [#40803488261](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40803488261) e [#40809180976](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40809180976), avviati rispettivamente alle **02:57 e 03:55 Roma**, hanno concluso `failure` prima del dispatch dei figli. Il test prebrief `test_check_morning_readiness_v1.py` asseriva rigidamente che **AUD.inflation** fosse ancora al mese `2026-06`; nel frattempo era presente un mese ABS più recente. Anche il successivo schedule [#40845406016](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40845406016) si è fermato per lo stesso motivo. La regressione è stata corretta separando fixture storiche sintetiche e lettura della fonte attuale, senza modificare il dato ufficiale.

**2. Pubblicazione, preflight.** I tentativi Pages [#40827522531](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40827522531), [#40831819908](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40831819908) e [#40832224021](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40832224021), osservati prima delle 08:00 Roma, hanno fallito nel controllo runtime. Il codice allora imponeva `cal['coverage']['macro_ccy_coverage']==8`, anche quando il calendario delle prossime release aveva una copertura macro dichiarata e limitata da fonti effettivamente note. La versione successiva del publisher usa `verify_future(cal,seed,cb_source,datetime.now(timezone.utc))`: è una verifica delle date contro il registro delle fonti, **non** un'autorizzazione ad aggiungere release non certificate.

## Verifica dell'ora reale, non un semplice badge GREEN

La pubblicazione [#40838827265](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40838827265) ha registrato `PAGES_DELIVERY_PROOF=PASS` e `PAGES_PUBLIC_HTTP_PROOF` con HTTP 200 e SHA256 identici, ma la sua ricevuta `PAGES_INDEPENDENT_0800_SLA` riporta la **prima osservazione HTTP verificata in quel run alle 08:59:05 Roma**, perciò `on_time_delivery_proven=false`.

GitHub Pages aveva anche completato altri build precedenti; **un build GREEN non prova da solo** che tutte le fonti della sessione e i byte del sito fossero effettivamente disponibili entro le 08:00. Una verifica successiva al termine non può provare che il sito fosse definitivamente in ritardo: documentiamo il punto come **SLA 08:00 non dimostrata**, non ricostruiamo timestamp HTTP che non abbiamo catturato.

L'ulteriore [Daily Data Orchestrator #40884445446](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40884445446) è stato avviato più tardi e ha correttamente conservato `LATE_SOURCES_READY_AFTER_DEADLINE`, non `PASS_DELIVERED_BY_0800`.

## Azione preventiva

Un test di regressione *non sostitutivo* dei controlli reali, `test_morning_source_drift_contract_v1.py`, viene eseguito sia dal workflow orchestratore sia dal publisher Pages. Rifiuta la riapparizione di vecchie asserzioni rigide che già avevano bloccato le 08:00, richiede ancora i confronti contro dati live, la validazione ufficiale delle date e le ricevute di verifica HTTP/08:00.

Questo non abbrevia da solo i tempi di GitHub Actions, non certifica una nuova giornata, non introduce un cron e non indebolisce alcuna protezione. La **prima prova conclusiva della nuova catena operativa** richiederà la verifica della prossima sessione feriale con source gates e HTTP esatti prima delle 08:00 Roma.
