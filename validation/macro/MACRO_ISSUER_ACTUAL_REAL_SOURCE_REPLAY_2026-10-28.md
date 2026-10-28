# Collaudo acquisizione actual ufficiali BLS/Statistics Canada — 28 ottobre 2026

## Perché serve questa fase prima del 30 ottobre

Le PR #733–#735 hanno collegato i consensi pre-release già congelati,
le pagine ufficiali e quattro richieste di aggiornamento GitHub Actions
venerdì 30 ottobre (13:37 / 13:57 / 14:27 / 15:07 CET).
Un test con comunicati sintetici non prova però che i documenti reali
dei due istituti siano raggiungibili e leggibili dai runner GitHub.

La pubblicazione BLS del **terzo trimestre 2026** è calendarizzata
per il 30 ottobre, 08:30 di New York = 12:30 UTC = 13:30 CET.
L'actual **non esiste ancora** il 28 ottobre.

### Debolezza reale corretta

Nel comunicato **Statistics Canada del 29 settembre** relativo
al PIL **luglio 2026**, il dato nazionale effettivo è **0,0%**:
la testata dice *0.0% (monthly change)* e il testo dice
*Real gross domestic product (GDP) was essentially unchanged in July*.
Il precedente parser richiedeva sempre "grew/rose/increased/... N%"
e avrebbe potuto perdere un valore zero autentico.

Ora zero è ammesso solo se coincidono:
- data del comunicato ufficiale;
- titolo e mese/anno del *PIL reale nazionale per industria*;
- riga narrativa "essenzialmente invariato";
- intestazione dello stesso periodo con **0,0% (monthly change)**.

Nessun campo mancante o pagina scaduta diventa zero.
Un eventuale "unchanged" senza intestazione numerica verificata
rimane dato **NON DISPONIBILE**, non actual=0.

Per BLS il controllo conserva embargo e trimestre del documento,
e isola il costo totale dei lavoratori civili (3 mesi
destagionalizzati), non salari/settori oppure variazione annuale.
È stata prevista una seconda pagina ufficiale BLS di riepilogo,
senza accettare altri host o provider secondari.

Per Statistics Canada il controllo esamina fino a otto pagine
candidate **solo sotto l'host ufficiale e il giorno esatto
del comunicato** (da suffisso a ad h). Il nome effettivo della
pagina del 30 ottobre non è ancora dichiarato: nessun URL
candidato costituisce prova che l'actual sia pubblicato.

### Collaudo reale online, separato dai modelli

Nuova prova CI sui due **documenti storici originali**:
- BLS Employment Cost Index 31 luglio 2026,
  totale civili 3M SA = **+0,9%**;
- Statistics Canada The Daily 29 settembre 2026,
  PIL reale luglio m/m SA = **0,0%**.

Lo script usa il medesimo parser della pipeline produttiva,
con **solo date storiche esplicite**, e registra come ricevuta
temporanea l'URL, SHA256 dei byte scaricati dal GitHub runner,
numero di byte e valore osservato.

Se un istituto blocca le richieste o cambia formato,
il controllo reale **fallisce**, anziché spacciarsi per riuscito.
Il download storico oggi NON prova la raggiungibilità futura:
è il collaudo concreto massimo possibile prima dei nuovi dati.

Non cambia l'actual ufficiale dei due eventi futuri, i consensi
archiviati, Core D, ranking 28 coppie, Beta, Forward,
News Pulse o politiche di repricing.

**Comandi**
- \`python -m unittest validation.macro.test_capture_official_postrelease_actuals_v1 -v\`
- \`python -m validation.macro.replay_real_publisher_html_eci_gdp_v1 --out /tmp/official-issuer-replay.json\`
