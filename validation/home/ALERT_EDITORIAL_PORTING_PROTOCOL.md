# FX Quant Next · Desk orario indipendente — versione senza costi API

## Principio

La Panoramica deve offrire un quadro generale dei mercati, con giudizio economico e
implicazioni relative per il Forex, non numeri arbitrari. La guida editoriale è la
copia **immutata** delle istruzioni V3 degli alert ChatGPT:
`validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md`.

**Distinzione corretta:** il nuovo motore gratuito segue i PRINCIPI del metodo V3
(Macro → Rates/Pricing → Risk/Flows ipotetici → Prezzo → Prova contraria),
ma **non esegue un LLM** e non può riprodurre alla pari la ricerca aperta e il
ragionamento contestuale degli alert ChatGPT. Non presentarlo come AI.

## Implementazione (costo API zero)

- Workflow dedicato `.github/workflows/next-independent-ai-hourly-desk-v1.yml`:
  ogni ora al minuto 17 UTC, inclusi i weekend, GitHub Actions standard su
  repository pubblico. Gli schedule possono subire ritardi.
- Generatore `validation/home/build_free_hourly_desk_v1.py`: usa
  `NEWS_PULSE_OPERATIONAL.json`, `CALENDAR_OPERATIONAL_VIEW.json` e
  `ESTIMATED_RESIDUAL_GAPS.json`; ricerca anche gli RSS GRATUITI di banca
  centrale G8 ed EIA mediante il collector GIÀ ESISTENTE
  `validation/collect_official_news_rss_v1.py`.
- Prima una narrativa multi-asset in italiano chiaro, poi il collegamento al
  Forex. Rilevazioni, stime/proxy, fonti, date e prove contrarie distinte.
- Feed pubblico **solo di lettura**:
  `site/fx-quant-v2/next/hourly-market-desk-current.json` su `gh-pages`.
  Lo storico di edizioni mantiene un digest dei dati effettivamente cambiati.
  Stessi dati → nessuna nuova edizione artificiale e timestamp invariato.
- Panoramica usa la versione gratuita solo quando una edizione valida è
  stata pubblicata; altrimenti resta il Morning Desk esistente. DARK DESK
  e tutte le altre pagine non cambiano.

## Costi e isolamento

- **NESSUNA** chiave OpenAI, nessuna API a pagamento, nessuna chiamata a
  `api.openai.com`; il precedente script AI è stato eliminato.
- Il repository è pubblico; i normali job GitHub-hosted del repository
  pubblico non richiedono un piano AI aggiuntivo. Restano possibili limiti di
  frequenza, disponibilità degli RSS e politiche GitHub Actions.
- **Gli alert orari ChatGPT NON SI TOCCANO:** stesso prompt, schedule,
  delivery, notifiche e automazione. Nessun workflow GitHub interagisce
  con l'automazione di ChatGPT e nessuna dipendenza inversa.
- L'assenza di RSS non impedisce di utilizzare altri dati datati e con
  collegamenti fonte; la mancanza di dati sufficienti lascia l'ultima
  edizione valida invece di pubblicare movimenti fittizi.

## Gap noti

Questa prima versione gratuita **non sostituisce** una ricerca AI su tutto il
mondo: fonti RSS istituzionali, dati di mercato ed energia sono coperti, ma
news azionarie societarie, politica e geopolitica in tempo reale non hanno
ancora una raccolta gratuita ampia e con la stessa profondità. Le migliorie
future devono rispettare le fonti, non inventare fatti.
