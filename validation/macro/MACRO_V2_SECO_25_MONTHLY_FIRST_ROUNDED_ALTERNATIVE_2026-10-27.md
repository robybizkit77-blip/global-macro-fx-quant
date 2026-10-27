# Macro V2 — SECO 25 mesi pubblicati: disoccupazione registrata destagionalizzata

**27 ottobre 2026 · prima pubblicazione ufficiale a un decimale, NON vintage esatto SNB.**

## Risultato verificabile

Per la componente 🇨🇭 CHF.labour abbiamo recuperato **21 PDF ufficiali SECO diversi** — gennaio 2025…settembre 2026 — dal portale [Statistiche mercato del lavoro SECO](https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen). I file sono stati scaricati realmente il 27 ottobre 2026; per ognuno il materiale di lavoro include **hash SHA-256 del PDF**, URL, data stampata sul rapporto, valore originalmente pubblicato dell'**Arbeitslosenquote saisonbereinigt** a un decimale, e controllo sul testo *Kurzübersicht* (più la tabella 1 quando chiaramente leggibile).

C'è un errore di estrazione che i test hanno intercettato e impedito: il PDF distingue disoccupati registrati, **cercatori di lavoro** e posti vacanti. Una prima lettura automatica aveva selezionato per sbaglio il tasso di cercatori di lavoro (4,5%). Il sistema è stato corretto imponendo la frase ufficiale «Die saisonbereinigte Arbeitslosenquote» e verificando manualmente gli ancoraggi: **gennaio 2025 2,7%**, **gennaio 2026 2,9%**, **settembre 2026 3,1%**. Il vecchio numero errato non è stato salvato nell'archivio.

Il quadro di 25 mesi settembre 2024–settembre 2026 si completa con **quattro valori dei primi rapporti 2024 indicizzati dagli originali PDF SECO**, tutti **2,6%**:
- Settembre 2024 · rapporto 4 ottobre;
- Ottobre 2024 · rapporto 5 novembre;
- Novembre 2024 · rapporto 5 dicembre;
- Dicembre 2024 · rapporto 10 gennaio 2025.

Questi quattro vecchi URL ora restituiscono **HTTP 404**, perciò **non hanno hash di PDF scaricati oggi**. La ricerca pubblica ne conserva indicizzate le tabelle originali, ma il peso probatorio è inferiore a quello dei 21 PDF acquisiti. Non attribuire loro un SHA, un originale conservato byte-per-byte né un timestamp intraday dimostrato.

## Perché questo non certifica il Core CHF.labour

La metrica dei primi rapporti SECO è un **tasso arrotondato a 0,1 punti percentuali**; quella del Core `CH_UNEMP_RATE_history_value` è il valore **preciso oggi revisionato** trasportato dal cube SNB `amarbma`. Le serie condividono il concetto generale di disoccupazione registrata destagionalizzata, ma differiscono nella precisione e nell'accessibilità dei *vintage*. La serie destagionalizzata viene ricalcolata periodicamente.

La finestra SECO offre **24 mesi precedenti di primi tassi arrotondati** con qualità mista (20 documenti originari PDF riscaricati per la finestra precedente, 4 documenti precedenti soltanto indicizzati) e una **25ª osservazione corrente settembre 2026** anch'essa in PDF.

Questo abilita esclusivamente una **statistica descrittiva di ricerca del tasso arrotondato originale SECO**, non una forza CHF, non il confronto dei rate SNB esatti alle date di allora e non un backtest forex PIT validato.

Restano invariati:
- **22/24** finestre numericamente complete basate sulle prime evidenze dei rispettivi dossier;
- **2/24** incompiute per i valori *esatti della metrica canonica* (USD CPIAUCSL / CHF SNB), **46 periodi** first-release mancanti in quei rispettivi ledger;
- **0/24** storici congiunti certificati per training backtest Macro-FX, **0** punteggi autorizzati;
- `D.json` settembre 2026, 28 coppie, sito, Beta e Forward non modificati.

## Qualità delle date

La data sul rapporto ufficiale + 1 giorno alle 00:00 UTC è un **gate prudente**. Non è la prova dell'istante effettivo di caricamento in rete né del momento di prima disponibilità dei valori esatti SNB. Il file salvato il 27 ottobre NON viene spacciato per un'acquisizione HTTP fatta nell'anno del singolo rapporto.

## Moduli

- `validation/macro/fixtures/seco_chf_sa_registered_unemployment_25_first_monthly_reports_2024_09_2026_09.json`: 21 prime pubblicazioni PDF scaricate, SHA-256 attuale, quattro vecchi mesi esplicitamente irraggiungibili.
- `validation/macro/v2_chf_seco_first_month_rounded_alternative_v1.py`: controllo di 25 tassi originali arrotondati, qualità a due livelli, normalizzazione robusta della fonte alternativa e **blocco di ogni promozione automatica**.
- `validation/macro/test_v2_chf_seco_first_month_rounded_alternative_v1.py`: falsificazione su periodi, arrotondamenti, sorgenti, hash disponibili, chiavi e nessuna modifica al Core.
- `validation/macro/v2_g8_24_axis_training_history_gap_audit_v1.py`: incorpora la fonte alternativa separata e preserva **22/24** senza riqualificarla come prima precisione SNB.

**Nessun nuovo schedule.** Il workflow temporaneo per recuperare i PDF è stato eliminato dopo il successo e il caricamento dei file in branch. Prossimo target: periodo CPI USA effettivamente pubblicato nell'indice SA originale, distinto dal CPI NSA di titolo; ottobre 2025 resta un periodo assente per lo shutdown.
