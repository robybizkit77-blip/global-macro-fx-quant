# Macro · acquisizione rapida ufficiale 30 ottobre 2026 — senza fingere puntualità garantita

**Ambito:** soltanto i due eventi per i quali il consenso era già stato congelato
il 28 ottobre 2026 con identificativo e orario di rilascio verificati.

- 🇺🇸 **Employment Cost Index USA (Q3)**: previsione secondaria archiviata +0,8%.
- 🇨🇦 **PIL mensile Canada (agosto)**: previsione secondaria archiviata +0,2%.

**Orario programmato di pubblicazione:** venerdì **30 ottobre 2026,
12:30 UTC = 13:30 Europe/Rome (CET)**. È solo l'orario dichiarato
dall'istituto; non prova che una pagina sia già stata pubblicata.

## Problema che si elimina

La pipeline principale Calendar/News verifica alle **04:17 UTC**
nei feriali e alle **06:17 UTC** tutti i giorni. Se dopo le 13:30
italiane esce un dato, il successivo ciclo potrebbe verificarsi
soltanto la mattina successiva. Per il test operativo del 30 ottobre
non vogliamo attendere il giorno dopo senza tentare un recupero.

## Intervento eseguito

Workflow dedicato, *soltanto data 30 ottobre 2026*, per ridurre
il ritardo potenziale:

| Tentativo previsto | UTC | Europa/Roma (CET) |
|---|---|---|
| Primo controllo | 12:37 | **13:37** |
| Secondo controllo | 12:57 | **13:57** |
| Terzo controllo | 13:27 | **14:27** |
| Quarto controllo | 14:07 | **15:07** |

Il trigger GitHub Actions ha **ritardi e code non garantibili**.
Questi sono orari di richiesta *alla piattaforma*, NON
promesse di ricezione o pubblicazione puntuale.
Il runner registra l'orario vero di partenza e lo mostra nel
riepilogo dell'esecuzione.

Cron GitHub non supporta l'anno; il programma controlla **2026**,
quindi nei futuri 30 ottobre non acquisisce alcun dato e non
scrive sul repository. Il workflow potrà essere rimosso nella
bonifica finale, evitando l'accumulo di schedulazioni inattive.

### Regola di sicurezza

Ogni volta che il job parte:
1. legge l'archivio immodificabile del **consenso
   pre-pubblicazione**, con due hash e le date UTC;
2. verifica la data esatta 30/10/2026, l'istante corrente dopo
   **12:30 UTC**, e quali actual ufficiali sono ancora mancanti;
3. se non manca nulla, **non scarica né riscrive nulla**;
4. se manca un actual prova soltanto la pagina primaria **BLS**
   e/o **Statistics Canada**, con controlli già collaudati su
   metrica, periodo, unità, data del comunicato e fonte;
5. se la pagina è indisponibile o non verificabile, dice
   **«non osservato»**: non produce numero sostitutivo,
   consenso scambiato per actual o revisione retroattiva;
6. aggiorna il **ledger ufficiale first-seen** e il livello
   informativo del **News Pulse**, separato dagli alert orari;
7. può salvare **solo** il file del ledger ufficiale e
   \`NEWS_PULSE_OPERATIONAL.json\`, non il modello di forza o
   le 28 coppie;
8. serializza la scrittura con il workflow Calendar/News
   tramite la **stessa concurrency group** per evitare
   push concorrenti. Se \`main\` è cambiato prima del commit,
   non forza la pubblicazione.

Il collaudo PR si esegue *senza* chiamare i siti degli
actual futuri. Controlla anche l'intervallo 12:29→12:30 UTC,
i tentativi previsti, la conclusione quando entrambi i valori
sono archiviati, le manomissioni dei forecast e il blocco
per gli anni successivi.

### Cosa NON viene promesso

- **Non** si tratta di una notifica ChatGPT alle 13:37 o
  di un nuovo alert orario; l'utente può consultare l'esito
  della run GitHub e il News Pulse aggiornato.
- **Non** certifica il millisecondo di prima pubblicazione
  sul sito dell'istituto; registra la prima lettura GitHub.
- **Non** dimostra che una variazione giornaliera del 2Y,
  del fixing BCE o del futures 6M sia stata causata dal dato:
  manca la prova con timestamp di mercato *prima/dopo*.
- **Non** significa OIS ufficiale USA: il 6M USD è
  indicativo, mentre il 6M Canada deriva da futures CORRA.
- **Non** modifica Core D, ranking G8, le 28 tesi, Beta o
  Forward Test; non genera posizioni FX.

Questo è un passo di **tempi di acquisizione**, non una
validazione quantitativa di alpha o della previsione FX.

**File tecnico**
- \`validation/macro/one_date_oct30_official_actual_fast_poll_gate_v1.py\`
- \`validation/macro/test_one_date_oct30_official_actual_fast_poll_gate_v1.py\`
- \`.github/workflows/macro-official-actual-fast-poll-20261030.yml\`

**Controllo locale:** \`python -m unittest
validation.macro.test_one_date_oct30_official_actual_fast_poll_gate_v1 -v\`.
