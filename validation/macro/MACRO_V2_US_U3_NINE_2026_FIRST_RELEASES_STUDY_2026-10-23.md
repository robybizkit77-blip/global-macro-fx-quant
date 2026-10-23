# Macro V2 — USD Labour 2026: nove headline BLS originali, replay con cutoff

**23 ottobre 2026 · Ricerca PIT shadow. Non è un nuovo score Forex.**

## Dati effettivamente verificati

Nell'[archivio originale BLS Employment Situation](https://www.bls.gov/bls/news-release/empsit.htm) sono disponibili le nove prime pubblicazioni della disoccupazione CPS U-3 destagionalizzata, serie `LNS14000000` (riferimento FRED `UNRATE`). Sono state lette le singole pagine archiviate, **non** un estratto FRED successivamente revisionato.

| Periodo osservato | Prima pubblicazione (08:30 NY) | U-3 headline |
| --- | --- | ---: |
| Gennaio 2026 | [11 febbraio](https://www.bls.gov/news.release/archives/empsit_02112026.htm) | 4,3% |
| Febbraio 2026 | [6 marzo](https://www.bls.gov/news.release/archives/empsit_03062026.htm) | 4,4% |
| Marzo 2026 | [3 aprile](https://www.bls.gov/news.release/archives/empsit_04032026.htm) | 4,3% |
| Aprile 2026 | [8 maggio](https://www.bls.gov/news.release/archives/empsit_05082026.htm) | 4,3% |
| Maggio 2026 | [5 giugno](https://www.bls.gov/news.release/archives/empsit_06052026.htm) | 4,3% |
| Giugno 2026 | [2 luglio](https://www.bls.gov/news.release/archives/empsit_07022026.htm) | 4,2% |
| Luglio 2026 | [7 agosto](https://www.bls.gov/news.release/archives/empsit_08072026.htm) | 4,1% |
| Agosto 2026 | [4 settembre](https://www.bls.gov/news.release/archives/empsit_09042026.htm) | 4,1% |
| Settembre 2026 | [2 ottobre](https://www.bls.gov/news.release/archives/empsit_10022026.htm) | **4,2%** |

Il dato del mese di ottobre 2026 non era ancora stato pubblicato al 23 ottobre: il BLS lo prevede per [6 novembre 2026](https://www.bls.gov/cps/publications/release-calendar.htm). La prima pubblicazione di gennaio 2026 è avvenuta **11 febbraio**, non il giorno inizialmente programmato; gli orari del dataset sono quelli effettivi.

## Due misure da non confondere

La cronologia di studio comprende 25 release fino a settembre 2025, l'assenza **strutturale** di ottobre 2025, le pubblicazioni di novembre/dicembre 2025 e le 9 nuove pubblicazioni 2026: **36 osservazioni first-release effettivamente disponibili**, su 37 mesi di riferimento settembre 2023–settembre 2026.

Il modello Macro V2 mensile `build_shadow_intensity` **continua a rifiutare** questo campione, perché nel precedente rolling window di 25 osservazioni il mese 2025-10 non esiste.

Il nuovo `v2_bls_us_u3_2026_shadow_replay_v1.py` calcola soltanto, a ogni effettiva pubblicazione, una **intensità descrittiva eventi-anziché-mesi** confrontando il dato U-3 appena annunciato con le ultime **24 release FIRST precedenti**, escludendo il dato corrente. I 24 eventi non rappresentano 24 mesi contigui.

A settembre 2026: headline **4,2%**, mediana del precedente campione di 24 first-release **4,2%**, MAD **0,1 p.p.**; intensità descrittiva Labour Tightness circa **0,00**. Significa che il valore finale è vicino alla mediana della specifica finestra, **non che il mercato del lavoro sia forte, che la Fed sia neutral, o che l'USD debba rimanere invariato**.

L'analisi conserva `velocity_per_month=null`, `acceleration_per_month_squared=null` e `turning_point_per_month=null` nei receipts: non inferiamo dinamiche mensili da una finestra di normalizzazione non contigua. Una valutazione dei movimenti 2026 potrà avere un'altra base, con metodologia e certificazione dedicate, ma non è implicita in questo risultato.

## Integrità delle date di trading e limiti

Il modello ammette il dato solo **alle 08:30 NY** della pubblicazione originale: per settembre 2026 il cutoff è **2 ottobre 2026, ore 12:30 UTC**. Un secondo prima il dato resta assente. Tutti i nove archivi sono pin in codice con data, valore, URL e offset NY/DST.

Le pagine originali sono verificabili online, ma **non sono stati archiviati i loro bytes con hash indipendente né ricostruite tutte le successive revisioni**. Il receipt è una prova di calcolo riproducibile, non una certificazione indipendente per backtest, previsione economica o ranking valutario.

**Non** aggiornare `D.json`, la baseline Growth/Labour/Inflation del 25 settembre 2026, `PAIR_SETUP_OPERATIONAL_VIEW.json`, i segnali sulle 28 coppie, i parametri di rischio, OIS, prezzi, o il sito pubblico. Questo stage modifica soltanto `validation/macro/` e il CI manuale/PR-only.

## Comandi

```bash
python -m unittest validation.macro.test_v2_bls_us_u3_2026_shadow_replay_v1 -v
python -m validation.macro.v2_bls_us_u3_2026_shadow_replay_v1 \
  --asof 2026-10-23T12:00:00Z \
  --out /tmp/macro-v2-shadow/bls-u3-jan-sep-2026.json
```

Per il prossimo passaggio, serve ancora validare longitudinalmente gli errori di previsione e l'impatto **relativo alle aspettative** OIS/2Y/cross FX: non basta vedere che un indice storico è diverso da zero.
