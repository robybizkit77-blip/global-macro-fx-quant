# GLOBAL MACRO FX QUANT

Staging pulito della **v490 Runtime Validated**.

Questa branch è separata da `main` e non alimenta il sito live.

Struttura:
- `index.html` loader minimale
- `payload/part-00.txt` … `part-15.txt`: contenuto completo della v490
- nessun file legacy della precedente architettura

La v490 viene ricomposta integralmente nel browser e verificata tramite il manifest runtime già incorporato nel payload.
