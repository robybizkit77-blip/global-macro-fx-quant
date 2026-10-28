# Global Macro FX Quant — primo controllo quantitativo del Core
**28 ottobre 2026 · ricerca, nessun nuovo punteggio FX pubblicato.**

## Che fase è?

Siamo entrati nella **validazione quantitativa del candidato domestico**
(versione della formula esplicita del 27/10) e abbiamo collegato
i risultati ai controlli Beta/Forward già esistenti. **NON** è
completata la validazione predittiva del modello FX, né il backtest
point-in-time (PIT), né la certificazione del vecchio Core.

L'antico \`D.json\` è ancora datato **25/09/2026**. Il suo generatore
originale dei punteggi Growth/Labour/Inflation non è identificato e
riproducibile. La vista prezzi delle 28 coppie è aggiornata al
**27/10/2026**: aggiornare quest'ultima NON ricostruisce il Core.

## Risultato numerico effettivo

Il candidato preregistrato calcola **per ogni singola economia**
\`A = 0.50*z_Crescita + 0.50*z_Tensione_lavoro\`, dove
z_Lavoro è invertito rispetto alla disoccupazione.
Inflazione è **un asse separato** e non contribuisce ad A.
Questi z sono normalizzati sulla *storia propria*, non una
forza valutaria confrontabile fra paesi. Non derivano tassi, CB/OIS,
posizionamento, risk sentiment o performance attese.

I controlli falsificabili hanno confermato la riproducibilità
aritmetica per **8 valute e 24 assi**; i pesi sono messi alla prova
con tre varianti predefinite (Growth 25/50/75%, Lavoro complementare).
La **classe** resta invariata in **4/8** valute (EUR, GBP, JPY, CAD);
cambia in **4/8** (USD, CHF, AUD, NZD).

Questa è **instabilità a scelta di pesi**, non errore di programma.
Non selezionare il peso più performante vedendo gli esiti: nessun
esito FX out-of-sample della nuova formula è stato verificato.
USD conserva una stima per la discontinuità dei dati BLS; EUR e CHF
conservano caveat di definizione del GDP. Non etichettare le
classificazioni come “macro strength” confrontabile fra paesi.

## Forward: ricevute riconciliate con l'archivio reale

Audit diretto del \`CORE_DECISION_SNAPSHOTS_V1.jsonl\`, non
sulla base delle sole ricevute:

| Lotto | Momento UTC | Decisioni archiviate | Ricevuta |
|---|---|---:|---|
| \`real-main-smoke-20261014\` | 14/10/2026 21:01:45 | 28 | Smoke del primo blocco, 28 duplicati rilevati al retry |
| \`frozen-core-20261026\` | 26/10/2026 19:12:17 | 28 | 28 scritte, corrispondono all'archivio |
| \`frozen-core-20261027\` | 27/10/2026 19:09:58 | 28 | 28 scritte, corrispondono all'archivio |

**84 decisioni su 3 date; 3 ricevute riconciliate, 0 lotti
disallineati**. Questo corregge i precedenti resoconti che dicevano
che fosse archiviato soltanto il lotto del 14 ottobre. L'archivio
è progredito e va letto attualmente.

**0 risultati successivi al segnale verificati** nel registro
\`validation/forward/outcomes/\`. Una decisione salvata non
prova un profitto, un tasso di successo, o che il Core sia corretto.
Il vecchio Forward schema ha un disallineamento di forma nei record
smoke e l'archivio non misura ancora prezzi/costi OOS indipendenti.
Non chiamare le 84 righe 84 decisioni indipendenti:
**sono 28 coppie ripetute su sole 3 giornate**.

## Beta e vecchio walk-forward

- Beta 52 settimane FX contro differenziale 2Y: esiste un
  **modello osservazionale e diagnosi pseudo-OOS**. Non è
  certificata una fonte PIT completa con prezzi/rendimenti
  comparabili, né l'efficacia di hedging OOS, né le regole B1/B2.
- Il documento \`HISTORICAL_WALKFORWARD_V93_CONCLUSION_2026-10-01\`
  dichiara esplicitamente lo stato **PSEUDO_OOS_ONLY**.
  Il paniere forte 12 settimane in finestre trimestrali non
  sovrapposte mostra media **−0,0021%** su 28 checkpoint:
  non prova alpha robusto; è inoltre un **vecchio modello**,
  non una prova del nuovo candidato domestico.

## Matrice di avanzamento e di blocco

| Controllo | Stato |
|---|---|
| Formula 8×3 e scenari pesi calcolabili | Verificato come **ricerca numerica** |
| Forward snapshot in archivio/receipt | Verificato come **raccolta osservativa** |
| 24 assi con vintage PIT sincronizzati | Non certificato |
| Forza FX confrontabile tra le 8 valute | Non definita/validata |
| OOS indipendente del nuovo candidato | Non eseguito |
| Risultati Forward e costi indipendenti | Assenti |
| Beta PDF A–Z e riduzione varianza OOS | Non certificati |
| Ricalibrazione \`D.json\` e delle 28 tesi | Non autorizzata |

**2 controlli preliminari e 6 blocchi residui**. Questo numero
non è una percentuale di completamento e non va trasformato in
un PASS di performance perché il workflow CI è verde.

## Successiva sequenza utile, senza rifare lavori già fatti

1. **Scegliere e preregistrare** come le tre dimensioni macro
   diventano input confrontabili nel nuovo Core, incluse le
   reazioni CB, OIS/front-end 2Y, qualità delle fonti e
   comparabilità internazionale; mantenere l'incertezza visibile.
2. Usare un **dataset storico sincronizzato alle pubblicazioni**
   o una metodologia chiaramente separata e meno forte se
   persistono le due lacune, **senza denominare PIT ciò che
   non lo è**. Validare stabilità per data, regime e pesi.
3. Continuare i **prospective frozen Core snapshots**, collegare
   realmente *solo quando maturi* gli outcome 1D/3D/1W/2W/1M/3M,
   prezzi verificati e costi; fare controlli benchmark,
   dipendenza fra coppie e finestre non sovrapposte.
4. Completare Beta **a partire dallo scopo reale e dal capitolo
   23 del PDF**, non spuntando artificiosamente tutti i capitoli.
5. Solo dopo le verifiche indipendenti e collaudo sito,
   proporre il rilascio effettivo. Non attribuire nuova data
   al Core vecchio per farlo apparire aggiornato.

**Implementazione di questa PR:** un audit che ricalcola i controlli
e riconcilia \`run_id\` e \`decision_cutoff\` fra ricevute e
ledger, prove adversariali, CI non programmata e ricevuta
temporanea \`/tmp\`. Non tocca \`D.json\`, \`live_data\`,
\`PAIR_SETUP_OPERATIONAL_VIEW\`, i 28 segnali, gli archivi
Forward, i parametri Beta o il sito. Un verde CI certifica
**solo che il controllo funziona**.

Esecuzione locale:
\`python -m unittest validation.macro.test_v2_core_quant_falsification_readiness_v1 -v\`
e
\`python -m validation.macro.v2_core_quant_falsification_readiness_v1 --as-of 2026-10-28 --out /tmp/gmfq-core-quant-falsification-2026-10-28.json\`.
