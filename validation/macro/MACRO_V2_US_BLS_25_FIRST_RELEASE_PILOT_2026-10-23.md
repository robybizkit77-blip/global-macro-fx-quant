# Macro V2 — Primo replay storico reale: USD unemployment U-3, 25 prime pubblicazioni

**Stato: pilot di ricerca storico; NON uno score USD del 23 ottobre 2026, NON segnale Forex e NON backtest certificato.**

## Provenienza

Le 25 osservazioni vanno da settembre 2023 a settembre 2025. Per ogni mese, il tasso di disoccupazione U-3 riportato nel testo della prima pubblicazione BLS Employment Situation è stato riconciliato con la data e l'ora 08:30 Eastern dell'articolo originale in [BLS Employment Situation Archives](https://www.bls.gov/bls/news-release/empsit.htm). Gli indirizzi individuali sono nel manifesto:

`validation/macro/fixtures/v2_bls_us_unrate_25_first_releases_2023_09_2025_09.json`

La serie BLS `LNS14000000` alimenta la serie `UNRATE` su FRED per la disoccupazione U-3 destagionalizzata. Questa identità economica è supportata da [FRED](https://fred.stlouisfed.org/series/UNRATE), **ma il simbolo FRED corrente non ricostruisce i valori storici alla prima pubblicazione**. Pertanto il replay usa esclusivamente i headline BLS, non valori FRED attualmente revisionati.

Le prime cinque osservazioni già controllate nel pilota precedente (dicembre 2023–aprile 2024) sono riconciliate anche con quell'archivio. Tutte e 25 hanno inoltre valori e date pin in codice, con controlli della pagina specifica e del fuso ET/DST. Gli HTML di fonte non sono conservati come bytes immutabili/hash indipendenti; dunque questa è una serie **attestata manualmente tramite pagine ufficiali**, non una catena PIT verificata indipendentemente per produzione.

## Una discontinuità che non va nascosta

- La **prima pubblicazione di settembre 2025**, valore **4,4%**, è avvenuta solo il **20 novembre 2025 alle 08:30 ET** (shutdown): usare la data convenzionale ottobre crea **look-ahead bias**.
- L'**Employment Situation relativo a ottobre 2025 non è mai stato pubblicato**. È impossibile inserirlo nel campione con un valore osservato alla prima pubblicazione. Non facciamo interpolazione, né backfill dai database FRED aggiornati, né retrodatazione.
- Il campione storico di 25 prime pubblicazioni consecutive si ferma quindi a settembre 2025. **Non è un archivio mensile completo fino al 23 ottobre 2026**. La regola di staleness vieta di usarlo come livello Macro corrente.

## Primo calcolo storico Macro V2

Cutoff: **20 novembre 2025 alle 13:30 UTC**, istante della pubblicazione ufficiale di settembre.

- Campione training: **24** prime pubblicazioni, settembre 2023–agosto 2025.
- Osservazione fuori training: **4,4%**, settembre 2025, annunciato il 20 novembre.
- Mediana precedente: **4,1%**; MAD precedente: **0,1 punti percentuali**.
- Z-score robusto: `(4,4 − 4,1) / (1,4826 × 0,1) ≈ +2,02`.
- Indicatore di **tensione del mercato del lavoro** (segno disoccupazione invertito): **≈ −2,02**.

Questo significa che, **in quel cutoff storico**, il tasso di disoccupazione era insolitamente alto rispetto alle 24 prime pubblicazioni precedenti: segnale descrittivo di allentamento del mercato del lavoro, non previsione di tagli Fed e tantomeno short USD meccanico.

## Limitazioni per scoring/live/quant

La prima misura storica reale è **riproducibile** dai valori archiviati e verificabili in pagina, ma:
- manca il controllo indipendente/immutabile completo degli HTML BLS e delle revisioni successive;
- mancano una finestra continua successiva a ottobre 2025, regole corrette per i mesi non pubblicati e PIT live fino al 2026;
- non sono state verificate capacità predittive su FX, tassi, positioning o prezzo, né OOS, costi o falsificazione cross-regime;
- le trasformazioni della crescita e dell'inflazione G8 non sono state aggregate né confrontate con la lettura labour;
- il nuovo modello non può sostituire i 24 score del 25 settembre 2026.

Non si modificano `D.json`, `PAIR_SETUP_OPERATIONAL_VIEW.json`, il sito pubblico, 28 coppie, ranking, OIS, rendimenti, sized trades o workflow schedulati. Il CI è manuale/PR-only, i ricevuti sono prodotti sotto `/tmp`.

## Replica

```bash
python -m unittest validation.macro.test_v2_bls_us_unrate_25_release_pilot_v1 -v
python -m validation.macro.v2_bls_us_unrate_25_release_pilot_v1 --out /tmp/macro-v2-shadow/us-25-release-pilot.json
```

Il report ha sempre `safe_to_publish_new_D=false`, `safe_to_update_pair_theses=false`, `eligible_for_backtest=false` e `writes_live_data=false`.
