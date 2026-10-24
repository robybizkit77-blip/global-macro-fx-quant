# Audit operativo — Control Room v10 vs Macro V2

**24 ottobre 2026 — snapshot del repository `main` prima della correzione PR.**  
**Obiettivo:** separare operatività quotidiana, integrità dei dati e ricerca storica PIT. Non introdurre dati economici stimati come certificati, non attivare score nuovi, non alterare 28 coppie.

## Risultato immediato: blocco individuato

La verifica delle ultime esecuzioni di **Daily Data Orchestrator V2** in GitHub Actions conferma un fallimento **prima** dell'esecuzione dei collector:

| Evento | Run | Esito | Root cause |
| --- | --- | --- | --- |
| 23 ott 2026, 23:11 UTC | [#40038190674](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40038190674) | `contract = failure`; `orchestrate = skipped` | `test_check_morning_readiness_v1.py`, riga 39, assert obsoleta su OIS withheld |
| 24 ott 2026, 00:05 UTC | [#40043237527](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40043237527) | `contract = failure`; `orchestrate = skipped` | Identico errore |
| 23 ott 2026, 17:06 UTC | [#39992370784](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/39992370784) | `failure` | Stesso workflow; non usarlo come prova della causa senza leggere separatamente il job log |
| 23 ott 2026, 17:52 UTC | [#39998684081](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/39998684081) | `failure` | Stesso workflow; non attribuire automaticamente alla stessa causa senza log |

**Causa confermata nelle prime due run:** il file `validation/orchestration/test_check_morning_readiness_v1.py` costruiva una fixture partendo dal feed operativo variabile e forzava solo `EUR` e `NZD` a `WITHHELD`. Poi pretendeva che l'elenco withheld fosse esattamente `["EUR","NZD"]`. Ma il feed ha anche **CHF** withheld, perché i futures CHF disponibili sono solo un proxy informativo, non un OIS ufficiale certificato. L'asserzione obsoleta fallisce e la dipendenza `needs: contract` impedisce l'avvio dell'intero job `orchestrate`.

**Intervento minimo di questa PR:** pin esplicito di **tutti gli 8 stati OIS** nella fixture deterministica; i risultati attesi sono **ufficiali AUD/CAD/GBP/JPY; stima informativa USD; withheld CHF/EUR/NZD**. La fixture non attribuisce alcuna certificazione nuova ai feed effettivi, non cancella la sezione OIS e non promuove CHF. I test di freschezza, DST, integrità dei prezzi, VIX e baseline rimangono invariati.

Questo risolve **il blocco di contratto riprodotto**, ma **non costituisce prova** che tutte le future esecuzioni schedulate o le singole fonti esterne funzioneranno: ogni esecuzione richiede nuovo riscontro.

## Due binari, non duecento mini-PR scollegate

### Binario A — Control Room operativa, priorità P0

Dai file del repository consultati durante l'audit:

- `.github/workflows/daily-data-orchestrator-v2.yml` ha cinque fasi **prebrief 05:00**, **premorning 07:45**, **morning 09:10**, **close 18:30**, **night 00:50** Europe/Rome. Le schedule attuali sono **lunedì–venerdì**, con doppio cron UTC e gate DST. L'utente vede un briefing alle 08:00: il refresh delle 09:10 non può essere considerato la fonte del briefing delle 08:00.
- Il `prebrief` concatena child workflow macro/rates/CB/OIS/calendar-news/VIX, poi `final-e2e-certification-gate-v3` e `publish-dashboard-pages-v1`. Il blocco nel job `contract` impedisce **tutta** questa catena; una run riuscita di **Publish Dashboard Pages** da sola non dimostra la freschezza di tutti i dati.
- `live_data/sections/D.json` contiene `asOf = 2026-09-25`: **baseline Macro storica congelata, non lo snapshot macro aggiornato a ottobre**. Qualsiasi etichetta “macro di oggi” che lo presentasse come calcolo fresco sarebbe erronea.
- `NEWS_PULSE_OPERATIONAL.json` ha `content_as_of = 2026-10-22`, `generated_at_utc = 2026-10-23T06:52Z`. Il contenuto è un **segnale OIS deterministico**, non un normale feed di notizie testuali fresche.
- `OIS_OPERATIONAL_VIEW.json` ha **4 ufficiali certificati** (`AUD,CAD,GBP,JPY`), **1 proxy stimato** (`USD`), **3 withheld** (`CHF,EUR,NZD`). Sono stati informativi differenti, mai equivalenti.
- La maggior parte dei dati macro mensili/trimestrali ha *reference period* precedente al giorno di lettura; questo può essere normale per il calendario ufficiale e **non prova da solo** un collector bloccato. Le date di pubblicazione, la frequenza e il numero di osservazioni devono essere esibiti accanto al valore.
- Il confronto dei feed e dei run ha rilevato un **blocco effettivo** e **non** consente di affermare che il sito sia completamente aggiornato al 24 ottobre o che il refresh mattutino abbia avuto successo.

**Definizione di “mattina pronta”, da verificare ogni giorno operativo:**
1. `contract` PASS, `orchestrate` eseguito e completato; ciascuna child run con `success` e identità/run-id documentati.
2. Controllo delle date **delle osservazioni delle fonti**, non solo `workflow conclusion=success`.
3. FX fixing ufficiale e chiusura VIX dell'ultima sessione disponibile; compatibilità prezzo delle 28 coppie; data di generazione News Pulse/calendario; origine esplicita degli OIS ufficiali vs stime.
4. Snapshot mattutino visibile sulla pagina pubblica con evidenza di source-date e build-date; browser QA desktop e mobile. Non classificare come “fresco” uno score `D.json` del 25 settembre.
5. Se qualche fonte è indisponibile o una pubblicazione non è ancora uscita, mostrare **ultimo valore valido + data + tipo di fonte + causa**, non un numero inventato.

### Binario B — Macro V2 storico, priorità separata

- I candidati publisher web sono collegati per **24/24** combinazioni G8 × Growth/Labour/Inflation, ma **0/24** nuove catene storiche full PIT sono approvate per nuove score.
- `MACRO_SOURCE_REGISTRY_2026-10-08.json`: 16 serie Inflation/Labour registrate; per Growth 8/8 candidati con trasformazioni e coorti economiche in ricerca, **nessuna selezione canonica**.
- Il laboratorio su Fed G.17 è arrivato a **13/25** mesi di prima pubblicazione descrittivi (2025-09…2026-09, con shutdown e due mesi pubblicati nello stesso giorno). Non ci sono i 25 periodi iniziali, i 25 **precedenti feature congelati** per normalizzare o l'archivio originale indipendente completo.
- Gli score legacy e la selezione delle 28 coppie **non vanno ricalcolati** a partire dalle fixture PIT attuali: manca la definizione storica della formula originaria, il mapping definitivo dei Growth, la certificazione dei publisher bytes, la prova delle revisioni e il walk-forward/OOS.
- È preferibile **completare una catena intera di una fonte/indicatore con verifiche**, poi scalare il metodo per fonti omogenee, anziché aprire infinite PR per un singolo mese e dichiarare completamento per il solo incremento dei contatori.

## Ordine di lavoro — criteri verificabili

| Priorità | Lavoro | Criterio oggettivo di chiusura |
| --- | --- | --- |
| **P0** | Eliminare il test obsoleto OIS che blocca Daily Data Orchestrator | PR con test mattutini + CI GREEN su nuovo commit; nessuna falsa certificazione OIS |
| **P0 subito dopo** | Verifica reale della prossima run operativa e fonte-per-fonte | `contract=success`, job `orchestrate=success`, child run e source dates verificate |
| **P1** | Audit sito/UX su provenienza, date e note “con rischio”/WITHHELD | Browser QA 1440/390, etichette data valore vs data build distinte, proxy visibili come *indicativi*, nessuna etichetta falsa |
| **P2** | Rendere il laboratorio Growth V2 scientificamente riutilizzabile | Serie canoniche G8 selezionate per PIL/IP, orizzonti QoQ/YoY/3m3m concordati, input originali e revisioni period-specific; nessuna normalizzazione forward-looking |
| **P3** | Certificare storico completo, nuovi pesi, score e FX ranking | Catene ufficiali complete, OOS, walk-forward, sign causale con tassi/OIS e confronto al prezzo, review separata prima della pubblicazione |

**Non sostenere che il sito sia guarito solo perché questa PR passa:** il fix elimina una regressione del preflight, non prova ancora esecuzione end-to-end, tempestività di tutte le fonti o correttezza della user experience.

## Impatto e confini

Questa PR cambia soltanto il **test deterministico** di `validation/orchestration/test_check_morning_readiness_v1.py` e questa nota di audit; **non** cambia lo scheduler, non crea automazioni, non richiede refresh live manuali, non scrive in `live_data/`, `D.json`, `site/`, `payload/`, `dashboard/`, non cambia publisher OIS o configurazioni modello.

L'esecuzione del test e il controllo PR devono essere GREEN **prima** del merge. La prossima run schedulata dovrà essere verificata separatamente; le schedule `1-5` non costituiscono una garanzia automatica per sabato e domenica.
