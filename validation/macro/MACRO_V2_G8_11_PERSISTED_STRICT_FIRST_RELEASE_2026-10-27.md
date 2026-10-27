# Macro V2 — conservazione permanente di 11 archivi ufficiali già certificati

**27 ottobre 2026 — research-only, senza sostituzione del Core o del ranking FX.**

## Cosa abbiamo recuperato realmente

Le prove di prima pubblicazione originale raccolte nelle precedenti esecuzioni GitHub Actions erano ancora disponibili, ma **i singoli dati non erano trattenuti nel repository né integrati nell'audit 24 assi**. In questa PR abbiamo recuperato e conservato con compressione lossless **11 fonti e 1.003 osservazioni**.

| Serie | Numero originali | Periodicità |
|---|---:|---|
| NZD CPI | 34 | trimestrale |
| NZD disoccupazione | 34 | trimestrale |
| AUD disoccupazione | 104 | mensile |
| CAD CPI | 104 | mensile |
| CAD disoccupazione | 104 | mensile |
| EUR disoccupazione | 104 | mensile |
| GBP CPI | 104 | mensile |
| GBP disoccupazione | 102 | mensile (finestra mobile LFS 3 mesi) |
| JPY CPI | 104 | mensile (cambi di base statistica da controllare) |
| JPY disoccupazione | 104 | mensile |
| CHF CPI | 105 | mensile |
| **Totale** | **1.003** | |

I file provengono dai precedenti artefatti delle workflow di ricerca ufficiale già pubblicati nel repository. Lo script `validation/macro/one_shot_retain_g8_11_original_release_artifacts_v1.py` contiene gli **11 ID di artifact, i nomi dei singoli CSV/JSON, gli SHA-256 degli originali, le quantità e le frequenze**. Il processo è stato eseguito su un ramo provvisorio e il workflow temporaneo è stato poi **eliminato**: nessun nuovo schedule o automazione di produzione.

La nuova libreria `v2_g8_11_retained_source_archives_v1.py` verifica a ogni lettura che il **CSV/JSON ricostruito sia byte-per-byte identico al materiale recuperato** e che data, periodicità, URL ufficiale, nome della serie e hash individuale delle fonti siano plausibili e non manomessi. Le versioni A/B dei materializer non implicano due fonti economiche diverse, e **non** devono essere sommate.

## Come migliorano l'audit Macro V2

L'audit `v2_g8_24_axis_training_history_gap_audit_v1.py` dà precedenza agli **originali di prima pubblicazione** disponibili per queste 11 fonti anziché ai più brevi dossier di comunicati recenti. Rileva per ogni valuta se 24 mesi o 12 trimestri precedenti sono consecutivi; registra separatamente la distanza tra l'ultimo dato conservato nell'archivio e il comunicato più recente conosciuto, quando differiscono.

Restano intenzionalmente separati:
- EUR HICP first flash 105 mesi e AUD CPI trimestrale 34 trimestri della PR #707.
- USD Labour 25 prime uscite BLS ferme al settembre 2025 (il dato ottobre 2025 non è mai stato pubblicato).
- CHF Labour: SECO 3,1% arrotondato **non** equivale alla prima precisione SNB.
- EUR labour: EA19/EA20/EA21 vanno valutate prima di dichiarare uno storico geograficamente omogeneo.
- GBP Labour: dato di fine finestra trimestrale mobile LFS, non disoccupazione di un solo mese.
- JPY Inflation: la CPI ha transizioni di base, senza garantire invariabilità della metrica nel tempo.

## Prove e limiti

L'impronta SHA verifica l'identità con i precedenti **artifact dei materializer**, che già raccoglievano dati dai comunicati e ne conservavano gli hash originari. Non significa che oggi siano stati scaricati nuovamente e ricertificati indipendentemente **i 1.003 corpi HTTP storici dei publisher**. Non possediamo neppure la catena completa delle revisioni per ogni fonte.

La completezza numerica dei periodi è pertanto un avanzamento **di copertura** per calcoli di ricerca e replay cronologici, non l'approvazione dei pesi del Macro Core o una prova di capacità predittiva.

**Nessuna modifica a `live_data/sections/D.json`, sito, prezzi, 28 pair rankings, Ratings, CB Pricing, Beta o Forward.** Nessuna promozione implicita dei 24 score. Le stime devono rimanere esplicite e distinte dagli originali.
