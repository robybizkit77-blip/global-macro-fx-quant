# Control Room · Audit dei WITHHELD — prima tranche (21 ottobre 2026)

**Ambiente esclusivo**: https://robybizkit77-blip.github.io/global-macro-fx-quant/site/control-room-preview/#/home

## Obiettivo
Separare i casi realmente non certificabili (WITHHELD corretto) dalle schede che omettono informazioni indicative già validate. **Non** trasformare proxy in tassi OIS osservati, promuovere score obsoleti o ridurre artificiosamente i WITHHELD.

## Riscontro diretto dei feed su `main`

| Sezione | Fonte attiva verificata | Esito, data e blocco |
|---|---|---|
| OIS ufficiali e futures monetari certificati | `live_data/sections/OIS_OPERATIONAL_VIEW.json` | **4/8** `GREEN_OFFICIAL` (GBP, JPY, AUD, CAD); **2/8** `GREEN_ESTIMATED` (USD, CHF); **2/8** `WITHHELD` (EUR, NZD), as-of per valuta 19–20 ottobre salvo NZD (2 settembre). |
| Livelli indicativi 3M, 6M, 12M | `site/control-room-preview/ois-pricing-estimates-v1.js` + proxy NZD | Copertura di ricerca distinta: USD e CHF da singoli contratti futures, EUR da futures con date non sincronizzate, NZD da Bank Bill scontato con ipotesi empirica. Non una curva OIS ufficiale. |
| Registro readiness | `live_data/sections/OIS_SOURCE_READINESS_VIEW.json` | 21 ottobre: **due** fonti senza certificazione operativa, EUR/NZD. USD/CHF rimangono stimati, non fonti OIS ufficiali. |
| Engine FX 28 coppie | `live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json` | 20 ottobre: 28 coppie; qualità `DA CONFERMARE=3`, `CON RISCHI=13`, `NON VALUTABILE=11`, `DA MONITORARE=1`. I giudizi non vengono cambiati da questa tranche. |
| Baseline Macro legacy | `live_data/sections/D.json` | `asOf=2026-09-25`, prezzo interno `priceAsOf=2026-10-02`: **non** aggiornato al giorno corrente. Alcune etichette storiche `CORRENTE COMPLETO` appartengono al vecchio baseline, non attestano freschezza 21/10. |
| Storia FX ufficiale | `live_data/sections/ECB_G8_PRICE_HISTORY.json` | `last_as_of=2026-10-20`, 28 pair. È distinta dal baseline macro legacy. |
| Storico Macro | `live_data/sections/MACRO_SERIES.json`, `MACRO_THERMOMETER_DATA.json` | Esistono serie per 8 valute e termometri attivi; non equivalgono automaticamente a 24 score Macro attuali/certificati. |
| Altri cross-asset | `home-navigation-v10.js`, sezione Cross | `Gold Price LBMA · WITHHELD` e `Brent spot ufficiale: WITHHELD` hanno significato specifico: i proxy futures non certificano uno spot LBMA/Brent. |
| Legacy OIS | `live_data/sections/OIS_DATA.json` | `as_of=2026-09-29`: USD, EUR, CHF, NZD `WITHHELD`. Non va usato per prevalere sul view operativo più recente; non mutarlo per fabbricare retroattivamente prezzi OIS certificati. |

L'ispezione testuale dei 32 frammenti della Preview pubblicati su `gh-pages` non ha individuato un **riferimento letterale** a `OIS_DATA.json`, mentre mostra riferimenti a `OIS_OPERATIONAL_VIEW.json`. Non equivale a dimostrare che ogni percorso di accesso indiretto è stato eliminato: mantenere questa verifica nel successivo audit dati.

## Prima correzione concreta — Pair Deep Dive, confronto 6M

**Prima:** quando la coppia contiene USD/CHF/EUR, il confronto 6M mostrava `6M pricing WITHHELD` senza citare il **singolo futures indicativo verificato** già presente nel layer Tassi.

**Adesso:** se e solo se la verifica già in uso in Tassi accetta il singolo dato 6M, la Pair mostra:

- `6M repricing policy non certificato` **e**, separatamente, il livello futures con `≈`, tipo, codice, data della quotazione, `NON ΔOIS, solo contesto`.
- USD/CHF: `PROXY`; EUR: `MIXED`, evidenziando la non sincronizzazione tra scadenze. Non sono interpolazioni, spread fra valute o OIS osservati.
- Se manca quotazione valida, data entro cinque giorni, identità del contratto, mapping scadenza o riconciliazione 100 meno prezzo, mantenere `6M pricing WITHHELD`.
- Nessuna nuova stima nel baseline, nel motore 28 coppie, nei 24 score Macro o nei backtest.
- Anche il riquadro dei due lati della Pair mostra l'esistenza del contesto futures, senza promuoverlo a pricing certificato.

## Priorità progressive dopo questa tranche

**P0 — Dati obsoleti o parziali mostrati con etichette ambigue.**
Tracciare `D.json` e le 11 `NON VALUTABILE` rispetto ai layer Macro, Rates, COT e Price senza modificare automaticamente i giudizi. Separare etichette *baseline storico* da *osservazione corrente*.

**P1 — Spazi WITHHELD con un proxy legittimo disponibile.**
Continuare pagina per pagina (Rates/Pairs completato parzialmente qui; poi Macro, Valute e Cross-Asset), applicando lo stesso contract fail-closed e segnalando quando il proxy è solo contesto.

**P2 — Lacune genuinamente non certificabili.**
EUR/NZD OIS vero, CHF 2Y storico omogeneo, spot oro LBMA e Brent certificati: non sostituire in silenzio dati differenti. Mostrare causa concreta e alternativa indicativa solo se verificata.

## Invarianti
- `WITHHELD` significa che *quella specifica misura* non è verificabile, non che la valuta non abbia dati.
- Le due date devono essere coerenti per sottrarre livelli ufficiali, e non basta la stessa etichetta `6M` per calcolare un repricing.
- 4/8 strumenti con pricing certificato rimangono 4/8; proxy non diventano ufficiali.
- Zero modifiche alle 32 parti grafiche approvate, ai dataset originali, al ranking delle 28 pair, alle automazioni e agli alert.
- Test negativi obbligatori per fonte scaduta, dati incoerenti e uso improprio delle stime.
