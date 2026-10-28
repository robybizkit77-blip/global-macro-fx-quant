# Forward V2 — Regole di valutazione delle osservazioni prospettiche (28 ottobre 2026)

**Stato: SOLO RICERCA. Nessuna validazione di capacità predittiva, nuovo segnale FX o Core operativo.**

## Qual è la singola unità osservata?

Il workflow serale congela una fotografia delle **8 valute G8 e 28 cross**, con riferimento ufficiale BCE dello stesso giorno, solo se i controlli sugli orari e sulle fonti consentono una vera acquisizione prospettica. In seguito i sei orizzonti (1D, 3D, 1W, 2W, 1M, 3M) vengono confrontati con il primo fixing BCE **strettamente successivo** alla scadenza completa; non con il fixing della mattina o del giorno che precede la scadenza.

**28 cross non sono 28 prove indipendenti**: sono combinazioni di 8 valute, e la fonte BCE parte da EUR. Fissato EUR=1, gli altri sette livelli BCE sono al massimo sette variabili di prezzo per giornata, non 28 variabili indipendenti. Inoltre le giornate successive sono serialmente correlate. Perciò il numero `N=28 × giorni × orizzonti` **non deve mai diventare un N statistico, un p-value, un t-statistic o un indice di affidabilità**.

## Controlli di ammissibilità dei dati

1. **Fotografia originale:** obbligatorio SHA-256, timestamp reale, 8 profili economici e tutte le 28 coppie, senza esclusione di cross sfavorevoli; Core originale non aggiornato. Se manca un prezzo T0, fallisce il lotto anziché utilizzare meno coppie selezionate.
2. **Risultato futuro:** deve appartenere a uno snapshot già registrato, coincidere esattamente con il T0 BCE originale e avere data successiva alla scadenza totale. Nessuna interpolazione; distanza massima quattro giorni civili rispetto alla data di scadenza, sempre dichiarata.
3. **Denominatore per orizzonte:** ogni giornata con orizzonte già decorso contribuisce **28 righe potenziali**, anche se il fixing futuro non è disponibile. Le righe mancanti vengono contate; non scompaiono dalla popolazione.
4. **Conteggi distinti:** giornate con scadenza maturata, giornate con tutte le 28 righe, con copertura parziale e senza risultati; righe complessive osservate e mancanti. Non si calcola un tasso di successo o una probabilità per il modello.
5. **Provenienza e mutabilità:** hash delle ricevute, fonte BCE originale, nessuna possibilità di scrivere ritorni sintetici nella serie reale, nessun trade side, costi, P&L, Alfa, Beta o hedge effectiveness costruiti da una variazione del fixing.
6. **Orizzonti multipli:** si osservano tutti e sei gli orizzonti fissati **prima** del dato; non si sceglie quello che ha funzionato meglio dopo aver visto i rendimenti. Eventuali futuri test di ipotesi e soglie devono essere preregistrati, poi verificati su osservazioni nuove e non usate per calibrare.

## Cosa non autorizza il controllo GREEN

- Non autorizza il ricalcolo di `D.json` né il ranking delle 28 coppie.
- Le 8 componenti macro sono normalizzate rispetto alla storia di ogni paese: **non sono automaticamente confrontabili** come ranking di forza valutaria.
- Senza una regola direzionale FX V2 registrata prima dei rendimenti non possiamo parlare di previsioni corrette, hit rate, performance, alpha o profitto.
- Il Beta FX-versus-2Y del PDF `Il beta dalla A alla Z` resta separato e richiede un pannello storico con provenienza PIT e valutazione OOS della riduzione di varianza. Un movimento di prezzi di riferimento BCE non sostituisce quell'esperimento.
- Senza snapshot reali e rendimenti maturati il risultato corretto è **0 osservazioni**, non un PASS di abilità predittiva.

## Esecuzione

`validation/forward/audit_v2_prospective_cohort_independence_v1.py` legge soltanto i due registri V2 già definiti; scrive la ricevuta **solo sotto `/tmp`**, con esito `RESEARCH_COHORT_COVERAGE_ONLY_PREDICTIVE_SKILL_NOT_EVALUABLE`. Il controllo è integrato come passo di audit nell'**esistente** `Forward ECB Reference Outcomes V1 (research only)`. Non introduce un workflow, un cron, un calendario né una nuova attività ChatGPT.

```bash
python -m unittest validation.forward.test_audit_v2_prospective_cohort_independence_v1 -v
python -m validation.forward.audit_v2_prospective_cohort_independence_v1 --receipt /tmp/gmfq-v2-cohort-audit.json
```

**Passaggio successivo, quando esistono serie reali:** scegliere e preregistrare una specifica ipotesi quantitativa V2 indipendente dal vecchio Core, includere baseline semplici senza data leakage e validare su date non utilizzate nella selezione delle ipotesi. Non dichiarare già compiuta questa fase.
