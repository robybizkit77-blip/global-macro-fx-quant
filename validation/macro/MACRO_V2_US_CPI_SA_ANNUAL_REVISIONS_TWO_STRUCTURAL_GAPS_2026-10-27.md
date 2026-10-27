# Macro V2 — revisioni stagionali CPI USA e regola dei mesi mancanti

**27 ottobre 2026 · RESEARCH-ONLY · nessuna modifica al Core operativo.**

## Risultato: il confronto tra edizioni BLS è materialmente diverso

Abbiamo esaminato i **24 file XLSX originali presenti sul sito editore**
\`cpi-u-YYYYMM.xlsx\`, acquisiti e SHA-256 verificati **il 27/10/2026**.
Il confronto fra i 24 fogli per i mesi ripetuti produce **199
coppie documento/mese**, di cui **102 contengono un indice CPI-U
destagionalizzato a tre decimali diverso dalla prima edizione di
quel mese**. Questi conteggi sono *diagnostici*, ottenuti dalle
copie XLSX raccolte nel [run di acquisizione](https://github.com/robybizkit77-blip/global-macro-fx-quant/actions/runs/40587426321);
i 15 cambiamenti della riclassificazione stagionale annuale sotto
sono conservati con entrambe le impronte SHA-256 nel ledger e
controllati in CI.

**Campione delle revisioni annuali verificate:** 4 mesi del 2024
confrontati con l'edizione BLS **gennaio 2025 (pubblicata 12/02/2025)**,
e 11 mesi del 2025 (ottobre escluso) confrontati con l'edizione
**gennaio 2026 (pubblicata 13/02/2026)**: **15 variazioni** su 15
e differenza assoluta massima **0,170 punti indice**.

| Mese economico | Indice SA nel file del mese | Valore in successiva edizione annuale | Revisione, punti indice |
|---|---:|---:|---:|
| 2024-09 | 314,686 | 314,851 | +0,165 |
| 2024-12 | 317,685 | 317,603 | −0,082 |
| 2025-03 | 319,615 | 319,785 | +0,170 |
| 2025-09 | 324,368 | 324,245 | −0,123 |
| 2025-11 | 325,031 | 325,063 | +0,032 |
| 2025-12 | 326,030 | 326,031 | +0,001 |

Fonte metodologica: [BLS Seasonal Adjustment](https://www.bls.gov/cpi/seasonal-adjustment/);
[BLS annuncio aggiornamento fattori stagionali 13 febbraio 2026](https://www.bls.gov/cpi/notices/2026/seasonal-adjustment.htm).
I fattori stagionali sono ricalcolati in febbraio e gli indici
dei precedenti cinque anni possono essere revisionati. Il confronto
non autorizza a usare l'edizione febbraio 2026 in una decisione
presa nell'ottobre 2025: sarebbe **look-ahead**.

## Regola strutturale — due lacune distinte

Il [BLS shutdown FAQ](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm)
conferma che **l'indice all-items per ottobre 2025 non fu pubblicato**,
e che **per ottobre 2026 non verrà pubblicata la variazione annua
nelle serie prive dell'ottobre 2025**, perché manca il denominatore.

- **2025-10**: manca il livello originale pubblicato **CPIAUCSL SA INDEX**,
  dunque anche un tasso YoY osservato in quel mese. Non si imputa.
- **2026-10**: il livello CPI SA potrebbe essere regolarmente pubblicato
  durante novembre 2026, ma il calcolo **YoY da indice SA** non è
  disponibile senza il livello 2025-10. Questa è una regola
  **prospettica al cutoff 26/10/2026**, non una pretesa di avere già
  il CPI di ottobre 2026.
- Il BLS può usare internamente una **media geometrica** dei livelli
  settembre/novembre 2025 per stimare i fattori stagionali; non è
  un valore «all-items ottobre 2025» pubblicato, né una misura che
  possiamo etichettare *osservata*.
- Il **+0,2% del novembre 2025** originario è riferito ai **due mesi
  settembre→novembre**: mai usarlo come variazione mensile ordinaria.

## Decisione di ricerca, senza cambiare il modello

La serie CPI del Core rimane \`CPIAUCSL\`,
\`yoy_pct_from_index\` (non CPI annuale headline NSA).
Il calcolo descrittivo di ricerca può utilizzare **24 osservazioni
effettivamente pubblicate in 25 mesi di calendario**, riportando
«STIMA, finestra irregolare, non PIT» e **nessuna interpolazione**.
Non è la stessa cosa che **24 mesi consecutivi**, e non deve essere
promosso nei punteggi, Beta/Forward, 28 pair o backtest.

**Finestre future teoriche**, *a condizione* che dopo ottobre 2026
tutte le pubblicazioni utili arrivino regolarmente:

- Per i **livelli mensili dell'indice**, primo mese di riferimento
  il cui training storico di **24 mesi precedenti** esclude
  ottobre 2025: **novembre 2027**.
- Per le **trasformazioni YoY derivate dall'indice** (metrica Core),
  occorre escludere anche il YoY ottobre 2026 mancante:
  primo mese di riferimento con **24 tassi YoY consecutivi precedenti**
  teoricamente completi: **novembre 2028**.

Questi sono limiti matematici, **non previsioni di futura
certificazione PIT**. Servono comunque prove di pubblicazione,
disponibilità alle date storiche, ricostruzione delle revisioni e
collaudo prima di qualsiasi promozione di nuove valutazioni.

## File verificabili

- \`fixtures/v2_us_cpi_sa_seasonal_revisions_shutdown_gap_policy_2026_10_27.json\`:
  15 coppie di revisioni annuali, date edizioni, SHA-256 delle due
  versioni del prospetto, differenze e regola strutturale.
- \`v2_us_cpi_two_annual_sa_vintage_revisions_gap_policy_v1.py\`:
  verifiche incrociate contro il registro esistente delle 24
  pubblicazioni, controllo calendario e protezioni contro look-ahead.
- \`test_v2_us_cpi_two_annual_sa_vintage_revisions_gap_policy_v1.py\`:
  test avversariali su fonti, differenze, dati mancanti, finestre,
  falsi source-day PIT e assenza di scritture al Core.
- Aggregazione **separata**, solo ricerca, nell'audit già esistente
  \`v2_g8_24_axis_training_history_gap_audit_v1.py\`.

**Invarianti**: ancora **22/24** finestre *numeriche* G8
first-web documentate; **0/24** dataset completi PIT certificati,
**0** nuovi punteggi o segnali autorizzati. Non toccare \`D.json\`,
\`live_data\`, ranking delle 28 coppie, Beta, Forward, Control Room,
OIS, Rates o scheduler.
