# Rates 2Y/10Y — significato verificato delle variazioni settimanali (28 ottobre 2026)

## Correzione esplicita del precedente sospetto

La PR #730 aveva osservato una differenza tra la variazione
\`chg2_bp\` del riepilogo e il cambio tra le ultime due osservazioni
di \`NATIVE_RATES_DATA.json\` per 5 valute. Quella differenza
**NON è di per sé un errore**: leggendo il codice effettivo
\`validation/build_rates_candidate_from_audit.py\` è emerso
che \`chg2_bp\` e \`chg10_bp\` sono già calcolati come variazioni
**settimanali** rispetto all'ultima osservazione disponibile
**in data pari o antecedente a (data di chiusura − 7 giorni
di calendario)**.

Ogni valuta dove il produttore automatico ha aggiornato lo
snapshot conserva anche \`weekly2_validation\` e
\`weekly10_validation\` con data e valore iniziale, finale
e differenza in punti base. La differenza sulle ultime
due sedute è una misura **diversa** e non va usata per
«riparare» la variazione settimanale.

Esempi veri del 27–28 ottobre nel repository:

| Valuta | Periodo del delta 2Y settimanale | \`chg2_bp\` | Ultime due osservazioni |
|---|---|---:|---:|
| USD | 20→27 ottobre | −9,0 pb | +2,0 pb |
| EUR | 19→26 ottobre | −2,8 pb | +4,2 pb |
| JPY | 20→27 ottobre | −2,1 pb | 0,0 pb |
| CAD | 19→26 ottobre | +4,0 pb | +15,0 pb |
| GBP | 19→26 ottobre | +2,4 pb | +2,4 pb |
| AUD | 14→21 ottobre | −0,2 pb | −0,2 pb |
| NZD | 5→16 ottobre | +6,0 pb | +6,0 pb |

*Per CHF il 2Y è datato 30 settembre e non include una
coppia \`weekly2_validation\`/\`weekly10_validation\`:
non attribuire a \`chg2_bp\` una certificazione della
finestra settimanale senza quella fonte.*
Per NZD la serie conserva un riferimento manuale
unico al 5 ottobre, che è l'ultima osservazione
disponibile prima del cutoff 9 ottobre: l'intervallo
reale è di 11 giorni, **non 7 giorni esatti**.
Per AUD l'intervallo è davvero di una settimana
fra due quotazioni settimanali; non è una variazione
giornaliera.

## Intervento che migliora davvero la pipeline

Aggiunto uno **stop prepubblicazione** dentro
\`.github/workflows/rates-persistent-daily-v1.yml\`
che controlla lo snapshot **candidato** prodotto
dalla pipeline, prima di \`update_live_direct_section.py\`:

- per USD/EUR/GBP/JPY/CAD/AUD e per la fonte manuale
  NZD, verifica **2Y e 10Y**;
- data finale, livello nel campo principale e ultimo
  livello dello storico devono coincidere;
- la data di partenza deve essere la **più recente
  tra le vere osservazioni non successive a
  (data fine − 7 giorni)**, non la penultima seduta;
- verifica valore iniziale e finale della ricevuta
  contro l'esatta coppia data-valore dello storico;
- verifica \`chg2_bp\`, \`chg10_bp\` e
  \`weekly*_validation.change_bp\` con la formula
  esplicita, arrotondata al decimo di punto base;
- 2Y e 10Y ricostruiscono la pendenza della curva;
- un candidato non può cambiare CHF o NZD né
  aggiornare altro che i 6 feed automatici
  senza revisione separata;
- nessuna data futura o ricostruzione fittizia,
  nessun refilling; fallimento non pubblica il
  candidato errato.

CHF resta **fuori dalla certificazione settimanale**
ma non blocca gli aggiornamenti delle altre 6 valute.
Il tasso NZD conserva la propria data effettiva e
non viene falsamente dichiarato aggiornato oggi.
I test usano snapshot reali e mutazioni avversariali.

## Cosa NON certifica

I rendimenti 2Y di diversi Paesi hanno **sottostanti
diversi**. Una variazione nominale settimanale
valida non è automaticamente una sorpresa monetaria
confrontabile, né prova di reazione a dati macro.
La precisione dei riferimenti non certifica
vintage storici first-release PIT, profitti,
ranking G8, 28 tesi, Beta o Forward Test.

Nessun \`chg2_bp\` storico è stato modificato e
nessun segnale FX è stato ricalcolato. Questa
correzione spiega e difende la semantica esistente,
non imposta nuovi pesi del Core.

**Per verificare in locale:**

\`python -m unittest validation.rates.test_weekly_rate_change_contract_v1 -v\`

\`python validation/rates/verify_weekly_rate_change_contract_v1.py --candidate live_data/sections/NATIVE_RATES_DATA.json --out /tmp/g8-rates-weekly-source-receipts.json\`.
