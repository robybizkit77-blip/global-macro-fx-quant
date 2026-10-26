# Reattivazione JPY nel Beta storico — solo ricerca, 26 ottobre 2026

**Contesto:** PR #639 ha dimostrato via CI che lo storico 2Y locale giapponese contiene 246 date non canoniche e 30 inversioni, oltre a due valori discostanti dall'ultimo archivio originale del Ministero (2026-09-25 e 2026-09-28). Dopo aver ripristinato insieme data e rendimento, usando i due valori originari verificati del Ministero e mantenendo tracciate entrambe le correzioni, il confronto completo è risultato **273/273 corrispondenze**.

Il problema non si esauriva nell'ordine delle date: alcune settimane mancavano nel sottoinsieme del sito. La nuova variante del laboratorio Beta `--mof-historical-csv/--mof-current-csv` importa **soltanto nella memoria del processo** la cronologia 2Y completa, ricostruita dai file originali MoF, fino alla data massima già dichiarata dalla sorgente del sito. È ammessa **solo** dopo aver validato le 273 osservazioni originali e corretto esattamente i due disallineamenti controllati. Non interpola rendimenti per festività o settimane mancanti; la finestra FX resta ECB e il matching delle tre fonti deve avvenire sulla stessa data effettiva.

### Esito osservato in CI con il file del 26 ottobre

- Default senza CSV originali: **21/28** coppie con almeno una verifica storica oltre le 52 settimane; sette JPY in quarantena per date non canoniche.
- Con gli originali MoF acquisiti e verificati indipendentemente: **27/28** coppie con almeno una verifica storica *pseudo-OOS*. **12/28** con almeno quattro osservazioni successive per un confronto **puramente descrittivo** di varianza (non sufficiente per rivendicare efficacia statistica).
- Non forzare l'ultima coppia a essere certificata: dati ancora troppo brevi, date non comuni o serie CHF/NZD vecchie possono impedire una finestra OOS completa. Il job stampa il numero esatto di prove per ciascuna coppia JPY.

```bash
python -m validation.beta.weekly_fx_2y_shadow_oos_v1 --as-of 2026-10-26 \
  --mof-historical-csv /tmp/jpy-2y-history-original.csv \
  --mof-current-csv /tmp/jpy-2y-current-original.csv \
  --out /tmp/beta-jpy-official-shadow.json
```

**Non è la messa in produzione del Beta**: i dati sono l'ultima versione pubblica, NON i veri valori di prima pubblicazione disponibili settimana per settimana (PIT); inoltre i benchmark 2Y non hanno definizione omogenea nei vari paesi. Le 52 settimane precedenti si usano per stimare e le successive per misurare soltanto un confronto storico preliminare. B1/B2, standard error robusti, rilevanza statistica e benchmark monetizzabile vanno ancora validati.

**Non viene cambiato** alcun file sotto `live_data/`, i punteggi, le 28 classifiche delle coppie, il sito, il Forward Test, Beta canonico, gli alert, gli scheduler delle 08:00 o i dati sorgente originali. Il confronto indipendente ufficiale può fallire o avere aggiornamenti successivi: in quel caso nessuna correzione nuova è accettata automaticamente.
