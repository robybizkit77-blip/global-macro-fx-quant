# Macro V2 — acquisizione permanente 139 prime uscite ufficiali HICP EUR / CPI AUD

**27 ottobre 2026 · Sola ricerca quantitativa · Nessuna promozione al Core**

Questa PR aggiunge al repository, come fixture testuali **LZMA/base64**, copie esatte di due CSV recuperati dagli *artefatti GitHub Actions storici*:

| Serie canonica | Fonte, periodo | Artefatto storico | SHA-256 completo del CSV originale |
|---|---|---|---|
| EUR `EA_HICP_HEADLINE_YOY` | 105 prime stime flash mensili Eurostat, gennaio 2018–settembre 2026 | ID `11674452706`, run `38063873303` | `78b876f9eec93d6a77696373a93e0444aed0e72e97a1dc71e4f74ae61eed541f` |
| AUD `AU_CPI_HEADLINE_Q_YOY` | 34 trimestri ABS Q1 2018–Q2 2026, inclusa la transizione dopo l'avvio della CPI mensile completa | ID `11627499603`, run `37956927900` | `03271a29146afa1ab88837b84ee437e01c1617bac9a361e4cc1d3c9a8908ac7e` |

Il file Eurostat esisteva in **due materializzazioni** dell'artifact `a/` e `b/` coerenti nel contenuto economico e già controllate nella ricevuta precedente; la fixture importata è `a/`, con hash del file CSV riportato sopra. Entrambi i contenuti sono conservati qui anziché dipendere dalla retention degli artifacts.

## Cosa verifica concretamente il loader

- Ricalcola SHA-256 del CSV recuperato, prima di elaborare i dati.
- Verifica che il fingerprint economico in formato JSON canonico coincida con la ricevuta ufficiale precedente (**EUR `fd19fe...86b1`**, **AUD `d448f8...31f`**).
- Ricostruisce periodi osservati senza lacune (105/105 mesi EUR, 34/34 trimestri AUD), valori, fonte URL HTTPS, SHA-256 della fonte individuale e percorso di acquisizione. Blocca periodi duplicati e fonti di dominio diverso dal publisher.
- EUR: la **data del comunicato** viene trasformata solo in disponibilità prudente dal **giorno UTC successivo**, quando non esiste un orario intraday attestato. Distingue esplicitamente **flash** dai successivi dettagli già documentati nel dossier web più breve.
- AUD: tratta l'ora locale ABS di **11:30 Canberra** mediante il fuso IANA `Australia/Sydney` (stesso orario civile Canberra), rispettando l'ora legale `AEDT` e `AEST`, quindi la converte in UTC. **Non** usa i CPI mensili come sostituti del canonico trimestrale.
- Affianca le due nuove serie archiviate alla ricostruzione giornaliera G8 e mostra i loro snapshot *as-of* senza cambiare l'inventario e l'origine delle 16 fonti candidate precedenti.

## Limiti che rimangono

Questo è un **import vero dei singoli record**, ma il download di due archivi Actions già validati NON equivale a ricontrollare adesso i byte immutabili originali dei 139 comunicati sul sito del publisher, né certifica tutte le revisioni e il cambio popolazione EA20→EA21. Il riferimento SHA in ogni riga è la ricevuta storica della precedente materializzazione, non una firma crittografica del servizio corrente.

La nuova vista archivio è conservata separatamente dalla precedente timeline di fonti candidate: non stiamo dichiarando risolte tutte e quattro le incompatibilità dell'inventario operativo e non sovrascriviamo la lettura mensile australiana contestuale. Per la versione definitiva occorrerà riconciliare il ledger unificato e verificare le serie degli altri pilastri allo stesso livello.

**Non si modifica `D.json`, il suo 25 settembre 2026, nessuna delle 28 coppie, il sito Control Room, nessuna logica di Beta/Forward Test, i pesi Macro o Rates/CB Pricing.**

## Riproduzione

`python -m unittest validation.macro.test_v2_eur_aud_archival_first_web_overlay_v1 -v`

`python -m validation.macro.v2_eur_aud_archival_first_web_overlay_v1 --output /tmp/macro-v2-eur-aud-source-archive.json`
