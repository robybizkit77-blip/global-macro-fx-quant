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
2. **Inferenza AI** (ad esempio GitHub Models, se autorizzato e funzionante) che riceve il prompt V3 integrale e il contesto fattuale datato. Uno script deterministico che concatena indicatori non riproduce il metodo.
3. Guardrail di pubblicazione: nessuna notizia o reazione inventata; output datato, fonti tracciabili, classificazione nuova/follow-up/anteprima, continuità rispetto all'edizione precedente.
4. Solo dopo test end-to-end e revisione editoriale: workflow indipendente con ciclo orario, storico versionato e JSON di sola lettura per la Panoramica. GitHub Actions può partire in ritardo rispetto alla cron.

**Stato: prompt copiato e architettura fissata nel ramo. Il workflow AI e la pubblicazione periodica non sono ancora implementati né verificati.** Non attivare una pianificazione che rimpiazzi o alteri gli alert ChatGPT.
