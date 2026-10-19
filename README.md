# GLOBAL MACRO FX QUANT

## Control Room operativa — versione di riferimento

**Apri la [Control Room Preview v10](https://robybizkit77-blip.github.io/global-macro-fx-quant/site/control-room-preview/#/home)**

L'interfaccia approvata e attualmente in sviluppo si trova in `site/control-room-preview/`. Questa è la destinazione corretta per miglioramenti alle card, ai grafici, alla navigazione e all'esperienza mobile.

La pagina alla radice del sito e `site/website-v1/` restano interfacce precedenti, conservate come storico: **non sono la Control Room operativa in fase di sviluppo**.

Le serie di mercato sono condivise tra più interfacce: i workflow Price, Rates, OIS e COT possono aggiornare dati riutilizzabili, ma **una modifica alla dashboard precedente non equivale a un aggiornamento della Preview**. Per verificare la Control Room usare `validation/qa_control_room_v10_public.js` e `control-room-v10-public-browser-qa.yml`.

Per le regole di sviluppo e le condizioni per non confondere le due interfacce, vedi [AGENTS.md](AGENTS.md).

---

## Nota storica: vecchia architettura v490

Staging pulito della **v490 Runtime Validated**.

Questa branch è separata da `main` e non alimenta il sito live.

Struttura:
- `index.html` loader minimale
- `payload/part-00.txt` … `part-15.txt`: contenuto completo della v490
- nessun file legacy della precedente architettura

La v490 viene ricomposta integralmente nel browser e verificata tramite il manifest runtime già incorporato nel payload.

Production deployment: v490 OIS audit validated and browser-tested on 2026-09-30.
