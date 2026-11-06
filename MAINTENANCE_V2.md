# FX Quant V2 — maintenance e pulizia sicura

Data: 2026-11-06. Inventario e regole di archiviazione; nessuna autorizzazione a cancellare dati.

## Versione di riferimento

- **Unica interfaccia di lavoro:** `site/fx-quant-v2/` (12 sezioni).
- Vecchi front-end: `site/control-room-preview/`, `site/website-v1/`, `index.html`, `dashboard/`, `payload/`.
- Inventario iniziale: 1.446 file tracciati, 225 workflow GitHub Actions, 49 file nella V2, 25 nella Preview, 93 in website-v1.

## Mantenere

Sito V2, feed condivisi `live_data/`, publisher Pages, pipeline di raccolta dati, verifiche di freschezza, audit, ricerca Forward, storici e provenance.

## Da verificare prima di disattivare

Anteprime, loader e vecchi workflow possono essere ancora collegati a `workflow_run`, ai publisher o ai test. Il nome “v1”, “v10”, “old” o “preview” **non dimostra** che il componente sia superfluo.

## Procedura per ogni workflow candidato

1. Verificare chi legge i suoi output e chi lo chiama da `workflow_run`.
2. Verificare cron, trigger, sorgenti, segreti, data di ultima esecuzione utile e publisher.
3. Dimostrare che esiste un produttore alternativo per tutti i consumatori.
4. **Disattivare**, senza eliminare il codice; mantenere rollback.
5. Ricontrollare dati pubblici, 24 viste browser e aggiornamenti reali successivi.
6. Eliminare solo dopo osservazione e approvazione esplicita.

## Non incluso in questa pulizia

Nessun ritocco al motore FX, formule delle 28 coppie, stime o quotazioni, interfaccia, schedule attivo o qualificazione delle fonti. Gli eventuali gap ufficiali CHF/NZD e OIS rimangono visibili.
