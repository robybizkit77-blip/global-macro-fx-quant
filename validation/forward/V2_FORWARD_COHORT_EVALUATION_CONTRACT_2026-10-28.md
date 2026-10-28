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

**Passaggio successivo:** il primo protocollo H1 è fissato qui sotto *prima* delle future osservazioni ammissibili. Questo documento non esegue il test, non attribuisce segnali alle fotografie già archiviate e non certifica una relazione predittiva.

## Protocollo prospettico H1 — Repricing relativo del 2Y e FX (research only)

**ID immutabile del disegno:** `V2-H1-2Y-REPRICING-1W-V1`. Questo è un **test di una singola relazione rates→FX**, non un nuovo score macro, non un Beta FX/2Y validato, non un segnale della Control Room. Data di preregistrazione: 28 ottobre 2026; la versione verificabile è il commit che introduce questo paragrafo su `main`. Lo snapshot V2 del 28 ottobre può essere usato soltanto come **lag storico già acquisito**, mai come osservazione predittiva H1 valutata retroattivamente.

### Domanda economica e verso previsto

Quando il rendimento governativo 2Y del paese base viene *repriced verso l'alto* più del 2Y del paese quotato, la valuta base tenderà ad apprezzarsi **successivamente** rispetto alla valuta quotata? L'ipotesi è volutamente difficile: il FX potrebbe aver già incorporato tutta l'informazione e il differenziale 2Y potrebbe riflettere premi/rischi diversi dalle attese di banca centrale.

Per ogni cross **A/B** alla data di cattura `t`, con l'ultimo snapshot valido del *precedente giorno lavorativo Roma* `t-1`:

```text
x[A/B,t] = 100 * ((Y2[A,t] - Y2[A,t-1]) - (Y2[B,t] - Y2[B,t-1]))  [basis points]
H1 verso previsto = sign(x[A/B,t])
r[A/B,t,1W] = ln(ECB_AperB_outcome / ECB_AperB_T0)
```

La convenzione è **positivo = apprezzamento della valuta A**; nessuna previsione probabilistica, nessuna posizione o sizing. Non stimare beta, pesi, soglie di selezione, ranking o parametri sui rendimenti futuri. I 2Y sono proxy sovrani osservati, **non OIS puri**; un esito positivo non dimostra causalità né anticipazione del monetary policy pricing.

### Ammissibilità point-in-time (fail-closed)

1. **Solo acquisizioni successive alla pubblicazione di questo protocollo su `main`**, già presenti nel journal immutabile V2, con `capture_at_utc`, hash validi, 28 T0 BCE e tutte le 8 schede. Non ricostruire o rietichettare dati precedenti.
2. Richiedere `two_year_observed_yield_pct` numerico finito e `bond_date` per entrambe le valute, **sia in `t` sia in `t-1`**. `bond_date` non può essere successiva alla rispettiva cattura; la sua anzianità deve essere **al massimo due giorni lavorativi locali**, non due giorni civili. Il dato per ciascuna valuta deve provenire da una nuova seduta (`bond_date[t] > bond_date[t-1]`), evitando false variazioni zero dovute a quotazioni stale. Differenze di emittente, tenore o definizione non confrontabili richiedono esclusione documentata, non interpolazione.
3. Per il benchmark servono due T0 originali BCE archiviati in due giornate lavorative consecutive; usare soltanto i valori già congelati all'epoca. Non ricostruire il momentum da una storia BCE corrente che potrebbe essere stata revisionata.
4. Una coppia non ammissibile resta nel **denominatore complessivo di copertura** (28 possibili cross per giornata). Non scartare selettivamente cross scomodi, valute sfavorevoli o date con risultato negativo. Classificare separatamente `missing_rate`, `stale_rate`, `unchanged_bond_date`, `noncomparable_source`, `missing_prior_T0`, `missing_future_fixing` e `zero_signal`.
5. Non usare in H1 `domestic_activity_z_within_own_history`, `six_month_policy_delta_bp`, `cb_communicated_WANT_not_prediction` o le componenti stimate/non-PIT. Sono interessanti ma hanno comparabilità/qualità eterogenee; eventuali ipotesi su macro o OIS richiederanno un protocollo **separato**. Il vecchio Core, ranking e Beta non sono etichette da predire.

### Outcome, baseline e criterio di falsificazione

- **Unico orizzonte primario:** `1W` già definito nel workflow come **7 giorni civili**, con primo fixing ufficiale BCE **strettamente successivo al giorno di maturazione completa**, entro il limite di quattro giorni e con gap documentato. Gli altri cinque orizzonti sono monitorati come contesto, **non** alternative per scegliere il migliore.
- **Benchmark unico:** semplice momentum dell'FX nel tratto T0 precedente → T0 attuale, `sign(ln(P_t/P_(t-1)))`, calcolato sugli stessi snapshot già congelati. È una baseline ingenua ma verificabile senza stimare coefficienti. Si valuta la differenza **sulla stessa identica sottopopolazione** di coppie con input di H1 e benchmark non nulli.
- **Criterio primario predefinito:** per ogni coppia ammissibile, accuratezza del segno previsto di `r[A/B,t,1W]` contro accuratezza del segno momentum. Calcolare **prima la differenza media delle accuratezze all'interno della giornata t**, poi la media tra giornate. Segnali zero o rendimento esattamente zero sono `no-call/tie`, non successi: pubblicare conteggi e copertura di entrambi e non trasformarli in hit rate favorevoli.
- **Null:** H1 non supera il momentum (differenza media giornaliera <= 0). Una differenza <=0, instabile per sottoperiodo o dipendente solo da pochi cross è evidenza contro l'ipotesi; non aggiustare a posteriori soglie, direzioni e coppie per salvarla.
- **Prima lettura soltanto descrittiva:** non fare test formali prima di **120 distinte giornate Roma di acquisizioni H1 con almeno una coppia pienamente valutabile** e relativa maturazione 1W. Anche 120 giornate non sono 120 prove indipendenti: i cross condividono valute e i rendimenti 1W si sovrappongono. Per l'incertezza usare ri-campionamento per **blocchi consecutivi di 10 giornate** (sensibilità 20 giornate) sulla serie delle *differenze giornaliere*, con intervallo al 95%; registrare sempre date, copertura, dati mancanti e sensibilità. Nessun p-value per singola coppia/righe × orizzonti e nessun claim di validazione con campione insufficiente.
- Se qualità delle fonti, disponibilità dei 2Y e copertura rendono H1 non valutabile, l'esito è **`INSUFFICIENT_VALID_PIT_COHORT`**. Non sostituire i buchi con prezzi, OIS o stime non preregistrati.

### Separazione dalla produzione

Nessun nuovo workflow/cron, modifica degli snapshot, del `D.json`, delle 28 coppie operative o dei report. Questo **protocollo documentale** non crea ordini, previsioni ufficiali, backtest o statistiche OOS. L'implementazione futura della ricerca, se e quando i dati lo permetteranno, dovrà consumare **in sola lettura** i due journal già esistenti e produrre soltanto ricevute di ricerca; qualsiasi nuova ipotesi costituisce una nuova famiglia di test dichiarata prima dei rispettivi outcome.
