# Macro V2 — USD CPI / CHF disoccupazione: 2 stime di ricerca, non first-release

**27 ottobre 2026 · Stato: integrazione di qualità dati, non Core Forex.**

Dopo la PR #712 il motore dispone di **22/24 finestre numericamente continue costruite con prime pubblicazioni web documentate**. Le due incomplete sono `USD.inflation` (24 periodi precedenti non documentati come prime pubblicazioni nel ledger) e `CHF.labour` (22 periodi precedenti non documentati nel ledger).

Questa PR NON pretende di recuperare quei 46 record originali. Aggiunge invece **due descrittori stimati, esplicitamente separati** dal precedente audit. Così le 24 componenti hanno informazioni utili a una lettura descrittiva, ma resta **22/24** la completezza numerica delle finestre first-web e **0/24** la certificazione completa dei dati originali e delle revisioni per training storico congiunto.

## 🇺🇸 USD — inflazione

- La fonte canonica è l'indice **CPIAUCSL destagionalizzato** trasformato in variazione su 12 mesi. NON è lo stesso valore pubblicato nel titolo mensile come CPI-U *non destagionalizzato* YoY.
- La storia nel `MACRO_SERIES.json` è la **serie oggi revisionata**, non i valori memorizzati nei singoli istanti di prima pubblicazione degli anni scorsi.
- La pubblicazione generale del CPI di **ottobre 2025 non è mai avvenuta** per lo shutdown. Il BLS spiega che non è disponibile una stima «all items» di quel mese: <https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm> e <https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm>.
- Il nostro modulo già validato `v2_us_shutdown_gap_research_v1.py` consente un'intensità **solo descrittiva e stimata**, basata su **24 mesi effettivamente osservati dentro 25 mesi di calendario**. Ottobre 2025 non viene interpolato, modificato né dichiarato pubblicato.
- Ho tentato di recuperare i 25 originali direttamente dall'indice BLS <https://www.bls.gov/bls/news-release/cpi.htm> usando un workflow di ricerca. Il server BLS ha risposto **HTTP 403 già sulla pagina indice**. Il workflow temporaneo e lo script di importazione non sono stati mantenuti, quindi **nessun falso archivio di 25 release** è stato aggiunto.

## 🇨🇭 CHF — disoccupazione

- Il valore ufficiale pubblicato da SECO a un decimale per settembre 2026 è **3,1% destagionalizzato**, compatibile con un tasso preciso fra **3,05% incluso e 3,15% escluso**. Questo non documenta la precisa prima pubblicazione del valore attualmente presente nella serie SNB.
- Il nuovo descrittore usa **24 mesi precedenti consecutivi dello storico corrente SNB** per una statistica robusta *retrospettiva*. Rimane una **stima**, perché i valori destagionalizzati possono essere ricalcolati ad ogni nuova osservazione.
- Il livello SNB revisionato a più decimali **non viene sostituito** con il valore SECO arrotondato nel calcolo; i due sono mostrati separatamente per non introdurre una falsa precisione.
- Le dichiarazioni originali SECO di prima pubblicazione per tutti i 24 mesi precedenti e lo storico esatto SNB con timestamp originario rimangono da reperire. Quindi non sono stati recuperati **22 first-release originali** per CHF.

## Controlli e protezione

`validation/macro/v2_g8_us_cpi_chf_labour_quality_proxies_v1.py` richiede il taglio fisso **2026-10-26T23:59:59Z**, impedendo di far sembrare che i valori oggi revisionati fossero noti in date passate. Le variabili sono etichettate:
- USD: `ESTIMATE_REVISED_CPIAUCSL_24_OBS_IN_25_MONTHS_NOT_PIT`.
- CHF: `ESTIMATE_REVISED_SNB_RETROSPECTIVE_24M_NOT_FIRST_RELEASE`.

Sono disponibili **2 descrittori stimati**, non 2 nuovi storici primi comunicati. La PR aggiunge test automatici contro osservazioni BLS ottobre 2025 inventate, mesi storici CHF mancanti, timestamp arbitrari, equivalenza tra NSA e SA, modifica a `D.json` e alle 28 coppie.

**Non modifica `D.json`, i 28 ranking FX, la dashboard, Beta, Forward, i pesi Macro, Rates, OIS o CB Pricing.** È un avanzamento sulla disponibilità descrittiva e sulla trasparenza, non sulla certificazione punto-per-punto storica.

## Passo seguente

1. Per USD: acquisire gli originali dell'indice **SA** effettivamente disponibile in ciascun comunicato e salvare byte e data, senza sostituirlo con CPI-U NSA; la mancanza dell'ottobre 2025 resta strutturale.
2. Per CHF: ottenere un archivio SECO delle **prime tabelle mensili**, più eventuali snapshot SNB originali; se mancano, usare l'alternativa arrotondata SECO etichettandola come tale.
3. Validare le definizioni degli altri otto casi problematici e il successivo calcolo dei pilastri: completezza numerica e prova di conoscibilità storica sono test distinti.
