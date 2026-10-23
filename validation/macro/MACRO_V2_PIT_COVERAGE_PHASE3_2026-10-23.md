# Macro V2 — Fase 3: audit della copertura PIT delle 24 componenti G8

**23 ottobre 2026 · ricerca, senza nuove score o segnali.**

## Risultato strutturale

La presenza di serie macro storiche non equivale a un archivio point-in-time di tutte le **prime pubblicazioni**. Il test distingue:

- 8/8 valute con almeno una serie osservata di **Growth**, ma nessuna selezione definitiva e certificata di serie, definizione economica e unità;
- 16/16 serie **Inflation/Labour** registrate e con storici, ma senza dimostrazione di una catena completa e verificata delle FIRST releases;
- 8 attestazioni web ufficiali dell'**ultima** pubblicazione Inflation/Labour, più 2 per Growth (AUD/NZD); le 10 attestazioni sono specifiche a periodo e valore, non attestazioni di tutto lo storico;
- 5 prime pubblicazioni BLS per il pilota `LNS14000000`, **non automaticamente mappabili** alla serie canonica `UNRATE`; 3 finestre ONS GBP `MGSX`, prive di completa attestazione degli orari UTC e soggette alla distinzione fra mese centrale e fine finestra;
- 0/24 pilastri **certificati** con la storia completa delle prime pubblicazioni necessaria per ricalcolare score economici.

Il conteggio `0/24` riguarda esclusivamente **la validazione dei nuovi score**: non significa che manchino 24 osservazioni economiche utilizzabili per studiare.

## Contratto di validazione

`validation/macro/v2_pit_coverage_readiness_v1.py` controlla le identità di fonte, trasformazioni e frequenze dei 16 input registrati, la coerenza fra l'ultima osservazione del termometro e le attestazioni ufficiali disponibili, gli ancoraggi Growth esatti, le date precedenti al cutoff e l'assenza di scambi automatici tra provenienze.

Per le variabili mensili la fase quantitativa richiede un minimo di **25 prime pubblicazioni consecutive**: 24 per il training e 1 osservazione fuori training. Per quelle trimestrali ne richiede **13**. Finché il pilastro Growth non ha serie/unità/frequenza fissate, non può ricevere arbitrariamente una soglia 25 o 13. Gli storici completi di valori revisionati non vengono contati come release.

Sono riportati, per ognuna delle 24 righe, frequenza, serie candidata o registrata, profondità dello storico osservato, presenza di attestazione dell'ultima pubblicazione e blocker della catena first-release. Le classificazioni sono per qualità documentale, **non** segnali trading.

Il modulo è read-only e termina con errore se una nuova attestazione contraddice l'ultimo valore o la frequenza canonica, se una fonte è rietichettata, se una release è nel futuro, se la serie non corrisponde a quella ufficialmente attestata o se uno snapshot dichiara retroattivamente una certificazione PIT inesistente.

## Audit e output

```bash
python -m unittest validation.macro.test_v2_pit_coverage_readiness_v1 -v
python -m validation.macro.v2_pit_coverage_readiness_v1 \
  --asof 2026-10-23 \
  --json-out /tmp/macro-v2-readiness.json \
  --markdown-out /tmp/macro-v2-readiness.md
```

Il CI produce un artefatto JSON/Markdown sotto `/tmp` ma non modifica `live_data/`, `site/`, `payload/`, `dashboard/` o i workflow schedulati. L'output proibisce espressamente `safe_to_publish_new_D` e `safe_to_update_pair_theses`.

## Azioni di ricerca ordinate

1. **USD Labour:** verificare la corrispondenza fra il pilota BLS `LNS14000000` e `UNRATE`, senza dichiararli identici a priori; estendere la catena ufficiale mensile ad almeno 25 FIRST releases.
2. **GBP Labour:** riconciliare i periodi ONS delle finestre mobili, con etichette canoniche e orari di pubblicazione verificabili, poi acquisire FIRST releases contigue.
3. **AUD/NZD Growth:** conservare le due attestazioni ufficiali già presenti ma selezionare contratti macro distinti: GDP QoQ per AUD non equivale al GDP YoY per NZD.
4. **16 serie Core e le altre Growth:** costruire la catena storica di date/valori effettivamente pubblicati, con provenienza riproducibile, revisioni e contratti di unità; evitare cross-country comparability artificiale.
5. Solo dopo copertura e replays multi-cutoff: confronti out-of-sample e sensitività del nuovo indice, verifiche di informazioni aggiunte oltre OIS, 2Y, prezzi e positioning, e governance separata per eventuali score e 28 coppie.

**Nessuna copia dei 24 punteggi del 25 settembre viene trasformata in nuova formula.** Le letture di studio già presenti nella Control Room restano operative e indipendenti.
