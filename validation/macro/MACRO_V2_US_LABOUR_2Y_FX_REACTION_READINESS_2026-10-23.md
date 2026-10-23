# Macro V2 — BLS U-3 → Treasury USA 2Y → EUR/USD (9 eventi 2026)

**23 ottobre 2026 — Studio osservazionale, non event study intraday certificato.**

## Che cosa è stato misurato

Sono stati allineati i 9 headline originali BLS U-3 (gennaio–settembre 2026) già certificati come letture da pagine di archivio nel pilota Macro V2, il file `NATIVE_RATES_DATA.json` (rendimenti Treasury USA 2Y giornalieri), lo storico `ECB_G8_PRICE_HISTORY.json` (USD per 1 EUR) e gli archivi OIS/futures già presenti nel repository.

Il controllo produce, **per ogni release**:

- Data e istante BLS in UTC, valore U-3 originale, senza attribuire una sorpresa consenso non disponibile.
- Treasury 2Y del giorno della release e **precedente osservazione effettivamente disponibile**, con gap del calendario, differenza in punti base e categoria della sessione.
- EUR/USD tra il **fixing BCE già determinato prima della notizia** e il **primo fixing successivo**, con date e periodo trascorso. Un cambio in calo (USD per EUR) rappresenta dollaro più forte rispetto all'euro, non più debole.
- Stato OIS storico e consenso atteso: **NON DISPONIBILI come misure sincronizzate** nel dataset per questi nove eventi.

Il Treasury USA descrive la propria curva dei rendimenti [daily par yields](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics) come quotazioni indicative rilevate in genere alle **15:30 New York**: la variazione della sessione non è la reazione nei minuti dopo le 08:30 BLS.

La [BCE](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) determina normalmente il fixing intorno alle **14:10 di Europa centrale**, mentre il BLS pubblica alle **14:30 ora di Roma**: **il fixing dello stesso giorno è pre-release**, anche se viene diffuso intorno alle 16:00. La prima osservazione sicuramente successiva in questo dataset è il fixing di un giorno **posteriore**, non la variazione intraday dello stesso giorno.

La [SIFMA](https://www.sifma.org/resources/general/holiday-schedule) ha raccomandato **chiusure anticipate** per Treasury e fixed income sia nel Good Friday del **3 aprile** sia il **2 luglio 2026**, vigilia osservata del giorno dell'Indipendenza. Il [New York Fed](https://www.newyorkfed.org/markets/opolicy/operating_policy_260312) segnala in particolare le anomalie operative del 3 aprile. Entrambe le release sono marcate come sessioni non standard. Il 2 ottobre la precedente osservazione Treasury disponibile risale al 28 settembre: intervallo di 4 giorni, da non attribuire alla sola release.

## Dati assenti — limiti assoluti

1. **Nessun consenso di disoccupazione timestamped pre-release** per l'intero campione. La differenza rispetto al precedente dato non è una sorpresa economica.
2. **Nessuna vera quotazione OIS allineata agli eventi**. Gli snapshot OIS/futures USD del repository iniziano solo il **16 ottobre 2026**, dopo l'ultimo evento BLS del 2 ottobre. Non vanno retrodatati né impiegati come proxy OIS dei mesi precedenti.
3. **Nessuna quotazione intraday a secondi/minuti** del Treasury 2Y o di EUR/USD immediatamente prima/dopo il comunicato. Giorni con altri annunci, volatilità, calendario festivo e spread possono dominare le misure giornaliere.
4. **Nessuna relazione causale o predittiva certificata**: nove eventi non consentono inferenze robuste, e i dati giornalieri contengono confondenti temporali.

Il file `validation/macro/v2_us_labour_market_association_audit_v1.py` applica questi divieti nel contratto e nei test negativi. Non produce corr/Sharpe, segnali, delta OIS, forecast FX o regressioni ingannevoli.

## Riproduzione

```bash
python -m unittest validation.macro.test_v2_us_labour_market_association_audit_v1 -v
python -m validation.macro.v2_us_labour_market_association_audit_v1 \
  --json-out /tmp/macro-v2-shadow/us-labour-daily-associations.json \
  --markdown-out /tmp/macro-v2-shadow/us-labour-daily-associations.md
```

I risultati sono **read-only sotto `/tmp`** e richiedono provenance/cutoff coerenti per ogni sorgente. Nessun `D.json`, `live_data`, `site`, 28 coppie, bias, segnali, automazioni, sizing o backtest viene modificato.

## Cosa serve per uno studio di impatto reale

Acquisire per **ogni** annuncio: consenso verificato *prima* delle 08:30, dato effettivo e revisione, livello Treasury 2Y alle 08:25 e 08:35 NY, stesso contratto SOFR/OIS alle stesse due ore, EUR/USD alle stesse due ore e alle sessioni successive, spread di negoziazione, orari delle altre release e news; definire finestre e direzioni **prima** dell'analisi, poi misurare in-sample/out-of-sample senza look-ahead. Senza questa base il valore Macro V2 rimane descrittivo.
