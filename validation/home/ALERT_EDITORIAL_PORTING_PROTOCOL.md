# Motore GitHub indipendente — protocollo di riuso alert ChatGPT V3

## Versione canonica

`validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md` contiene la copia **testuale integrale** del prompt dell'automazione ChatGPT attiva `Macro FX Research Alerts`, letta il 13 novembre 2026. La copia non altera il prompt originale né l'automazione.

Il prompt V3 resta la fonte editoriale per il secondo motore: ricerca ampia e globale, priorità temporale, 6 ambiti informativi, metodo Serafini, interpretazione cross-asset, fonti con date, 3–6 notizie quando fondate, anti-duplicazione e stile italiano chiaro.

## Separazione obbligatoria

- **ChatGPT**: task, cadenza, notifiche, configurazione, accessi e cronologia invariati. Nessun tool `Automations.update` o nuova task ChatGPT.
- **GitHub**: workflow e motore AI autonomi, isolati dai workflow di certificazione/orchestrazione e dagli alert ChatGPT esistenti. Non importare `MACRO_MARKET_ALERTS_DESK.json` come se fosse una cronologia reale: al momento è vuoto.
- **Sito FX Quant Next**: consuma solo una proiezione *di lettura* degli output GitHub; non invia alert ChatGPT e non blocca la pubblicazione del resto del sito se il nuovo feed non si aggiorna.

## Adattamento tecnico, non editoriale

Il prompt ChatGPT parla di utilizzare ricerche e pubblicare un messaggio in chat. Su GitHub servono:
1. Raccolta indipendente di notizie da fonti ufficiali/affidabili, con data del fatto, data della pubblicazione, provenienza e deduplicazione. Le serie interne NEWS_PULSE/Calendar/Rates/Risk/Commodities sono un punto di partenza, non una ricerca web globale completa.
2. **Inferenza AI indipendente** con OpenAI Responses API e ricerca web, autorizzata solo dal segreto GitHub `FXQ_MARKET_DESK_API_KEY`. GitHub Models è stato definitivamente ritirato il 30 luglio 2026 e non è una soluzione. Lo script passa il prompt V3 integrale, contesto datato e istruzioni aggiuntive esclusivamente tecniche sul formato JSON e sulla verifica delle fonti.
3. Guardrail di pubblicazione: nessuna notizia o reazione inventata; output datato, fonti tracciabili, classificazione nuova/follow-up/anteprima, continuità rispetto all'edizione precedente.
4. Il workflow indipendente `.github/workflows/next-independent-ai-hourly-desk-v1.yml` è pianificato al minuto 17 di ogni ora, con test offline su pull request. Se il segreto manca, non pubblica. Se l'AI fallisce, il JSON precedente su `gh-pages` resta intatto. GitHub Actions può eseguire con ritardo. L'output previsto è solo `site/fx-quant-v2/next/hourly-market-desk-current.json` sul ramo Pages; la Panoramica non deve utilizzarlo come feed live finché non esiste almeno un'edizione verificata dal runtime reale.

**Stato: prompt copiato, workflow AI indipendente e verifiche offline sviluppati. Le inferenze reali e la pubblicazione richiedono la configurazione del segreto e un'esecuzione GitHub di prova.** L'automazione ChatGPT rimane totalmente intatta.
