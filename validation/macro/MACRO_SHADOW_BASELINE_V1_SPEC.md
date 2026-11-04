# FX Quant V2 — Macro Shadow Baseline V1 (research-only)

## Ipotesi economica (non un segnale)

Un bilancio descrittivo di crescita corrente, slack del lavoro e momentum
dell'inflazione può aiutare ad organizzare Macro → Rates → Prezzo. Non misura
forza della valuta, sorpresa di politica monetaria, rendimento atteso o edge
dimostrato.

Input: il dataset osservativo Macro V3 già esistente, dopo validazione di
8 economie, 24 misure e 28 contesti di coppia. Lo storico è rivisto, non
costituisce un archivio point-in-time dei primi rilasci. Date dei periodi
economici e date dei comunicati non sono equivalenti.

## Formula fissa, riproducibile sul medesimo snapshot

Per ogni economia:

- G = clip(PIL reale QoQ NON annualizzato / 1,0 punto percentuale, -1, 1).
  Il livello di crescita dell'ultimo trimestre NON è accelerazione.
  I dati SAAR sono convertiti upstream nella Macro V3, senza confonderli
  con percentuali QoQ.
- L = clip(-variazione disoccupazione sugli ultimi TRE intervalli osservati
  / 0,5 punti percentuali, -1, 1). Disoccupazione in aumento = maggiore
  slack ciclico. Gli intervalli possono essere trimestrali o mensili.
- I = clip(-variazione headline inflation sugli ultimi TRE intervalli
  osservati / 1,0 punto percentuale, -1, 1). Inflazione in accelerazione =
  maggiore pressione sulla stabilità prezzi, ma non necessariamente FX
  debole: il mercato potrebbe prezzare tassi più alti.
- Indice shadow = 100 × (G + L + I) / 3, compreso tra -100 e +100.

I pesi 1/3 sono fissi. Le scale 1,0/0,5/1,0 pp sono **ipotesi
euristiche dichiarate in questa V1**, non fit sui 24 punteggi del vecchio
D.json né ottimizzazione su ritorni FX. Il modello mescola un livello
della crescita e due variazioni; non è un puro indice momentum. I numeri
non costituiscono classifica di forza FX: cicli, basket di inflazione,
mercati del lavoro, vintage e periodi differiscono tra Paesi.

Accelerazione del PIL (QoQ ultimo meno QoQ precedente): solo se esistono
due trimestri consecutivi con unità identiche; visualizzata, mai inclusa
nell'indice V1. In data 04-11-2026 è disponibile soltanto per USD ed EUR.
Non si tratta il trimestre mancante come zero. Per le 28 coppie sono
esposte le letture delle due gambe e flag di comparabilità dei periodi;
NON viene calcolato un differenziale di forza FX o un trade bias.

## Sensibilità ed evidenza richiesta

Per ogni economia si pubblicano minimo/massimo in 7 configurazioni:
pesi uniformi 1/3, tre scenari 50/25/25, tre scenari che escludono un
pilastro e dividono i pesi 50/50. L'intervallo è sensibilità alle scelte
dei pesi, **non** un intervallo di confidenza né una prova di stabilità.

Input futuri, incompleti o semanticamente incoerenti: rifiutati, non
imputati a zero. I test verificano 8 economie × 3 componenti, 28 coppie
senza segnali, determinismo, variazione del segno economico, dati futuri,
periodi invalidi e immutabilità di D.json e PAIR_SETUP_OPERATIONAL_VIEW.

Prima di eventuale uso in segnali servono: archivio first-release PIT,
più cicli economici, freeze delle regole, split temporale, walk-forward/
out-of-sample, stress delle revisioni, confronto contro baseline semplici,
verifica rates/pricing, positioning, prezzo, costi e turnover, Sharpe e
drawdown, test di falsificazione. Nessuna di queste validazioni è
attualmente soddisfatta.

## Aggiornamento e isolamento

La pagina Macro V2 legge la Macro V3 già pubblicata e ricalcola sul
browser l'indice con formula versionata. Il workflow QA giornaliero
genera un JSON e un riepilogo testuale come artifact, SENZA commit sul
Core né su D.json. Non crea nuovi provider, non modifica la grafica
esistente, i 28 segnali, V10, OIS o backtest. La baseline storica del
motore 25-09-2026 rimane separata e non riprodotta.
