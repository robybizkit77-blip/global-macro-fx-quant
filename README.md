# GLOBAL MACRO FX QUANT

## Sito operativo ufficiale — FX Quant V2

**[Apri FX Quant V2 — Research Desk](https://robybizkit77-blip.github.io/global-macro-fx-quant/site/fx-quant-v2/)**

La versione approvata e operativa è `site/fx-quant-v2/` (12 sezioni). La grafica V2, le 28 coppie FX e il Core restano congelati; nuove modifiche richiedono un difetto riproducibile o una fonte verificata.

### Ingressi e versioni storiche

- Il repository root `/` e `site/website-v1/index.html` rimandano alla V2 per navigazione; **non** sono il codice sorgente della V2.
- `site/control-room-preview/`, `site/website-v1/`, `dashboard/` e `payload/` restano archivi *di compatibilità*: non cancellarli o disattivarne i workflow senza tracciare chi li utilizza.
- I workflow storici continuano ad alimentare alcuni feed condivisi, pubblicare dati su Pages, fare audit oppure mantenere la retrocompatibilità. Un workflow vecchio non equivale a un workflow inutilizzato.

### Fonti e qualità

I feed `live_data/sections/` sono condivisi. L'interfaccia V2 separa valori ufficiali, stime, futures secondari, proxy e dati storici. **24 livelli visualizzati non implicano 24 quotazioni OIS ufficiali.** Le osservazioni CHF/NZD di ricerca non sono automaticamente promosse a dati canonici o segnali FX.

### Collaudo

- V2 desktop/mobile: `.github/workflows/fx-quant-v2-browser-daily-qa.yml`
- Pubblicazione V2: `.github/workflows/publish-fx-quant-v2.yml`
- Prova pubblica delle 08:00: `.github/workflows/fxv2-morning-public-proof.yml`
- Gate di ricerca/Core: `.github/workflows/final-e2e-certification-gate-v3.yml`

Vedi [AGENTS.md](AGENTS.md) per le regole di intervento e [manutenzione e archiviazione](MAINTENANCE_V2.md) per la politica di pulizia.
