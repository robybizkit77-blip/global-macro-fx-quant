'use strict';
/*
 * FX Quant Next · Editorial Research Companion V7
 * Source-backed interpretation for each studio. Read-only: no model, signal or trade writes.
 * Selected currency and pair always drive the story; same-session claims require matching dates.
 */
(function(){
 function create(api){
  const {get,state,caseNow,finite,validDay,fmt,sign,date,dayNow,esc,NAMES}=api;
  const country=state.ccy||'USD',other=(state.csOther&&state.csOther!==country?state.csOther:(country==='EUR'?'USD':'EUR'));
  const names=NAMES||{},pairs=get('pairs')?.pairs||{},rates=get('rates')||{},macro=get('macro')?.currencies||{};
  const ois=get('ois')?.currencies||{},cot=get('cot')||{},risk=get('risk')?.streams||{};
  const raw=String;
  const showPeriod=x=>typeof x==='string'&&/^\d{4}-\d{2}$/.test(x)?x.slice(5,7)+'/'+x.slice(0,4):date(x);
  const isDate=x=>validDay(x)&&x<=dayNow();
  const isWithin=(x,n)=>isDate(x)&&(Date.parse(dayNow()+'T12:00:00Z')-Date.parse(x+'T12:00:00Z'))/864e5<=n;
  const move=x=>finite(x)?sign(x,1,' pb'):'non quantificata';
  const latest=x=>x?.as_of||x?.date||null;
  const frag=x=>raw(x||'').replace(/[.!?]+$/,'');
  const cLabel=c=>names[c]||c;
  const sourceLabel=x=>isDate(x)?date(x)+(isWithin(x,8)?'':' · storico'):showPeriod(x||'');
  const caseIntro={
   stress:'L’ipotesi generale è che il premio richiesto per detenere rischio si stia muovendo. Questa pagina deve dirci se il movimento è anche economico, monetario o valutario.',
   relief:'La distensione di volatilità e credito suggerisce un recupero dell’appetito per il rischio, ma non dimostra che la crescita sia migliorata. Qui cerchiamo una verifica indipendente.',
   'bond-rally':'I rendimenti governativi stanno scendendo. Non possiamo concludere che il mercato stia prezzando tagli senza leggere anche strumenti monetari comparabili.',
   'yield-selloff':'I rendimenti sono in rialzo. La domanda è se si muovano le attese della banca centrale o i premi legati a inflazione, durata e offerta.',
   'fx-divergence':'Il movimento relativo tra tassi e dollaro non è lineare: le altre economie, i flussi e il rischio possono avere un ruolo importante.',
   mixed:'Le ultime fonti non mostrano un unico regime convincente. Per questo separiamo le osservazioni dalle ipotesi che restano aperte.'
  }[caseNow?.kind||'mixed'];
  function macroEssay(){
   const i=macro[country]?.inflation,l=macro[country]?.labour,r=rates[country],o=ois[country]?.horizons?.['6m'];
   const dh=Array.isArray(i?.history)&&i.history.length>=2&&finite(i.history.at(-1))&&finite(i.history.at(-2))?i.history.at(-1)-i.history.at(-2):null;
   const dl=Array.isArray(l?.history)&&l.history.length>=2&&finite(l.history.at(-1))&&finite(l.history.at(-2))?l.history.at(-1)-l.history.at(-2):null;
   const inflation=finite(i?.latest_value)?'l’inflazione headline è '+fmt(i.latest_value,2)+'% ('+showPeriod(i.as_of)+')'+(finite(dh)?' e cambia di '+sign(dh,2,' punti percentuali')+' rispetto alla rilevazione precedente':''):'non è disponibile una lettura validata dell’inflazione';
   const labour=finite(l?.latest_value)?'la disoccupazione è '+fmt(l.latest_value,2)+'% ('+showPeriod(l.as_of)+')'+(finite(dl)?' e cambia di '+sign(dl,2,' punti percentuali')+' rispetto alla rilevazione precedente':''):'non è disponibile una lettura validata della disoccupazione';
   const tension=finite(dh)&&finite(dl)
    ?dh>.05&&dl>.05?'Prezzi più persistenti e disoccupazione in aumento descrivono una tensione tra rischio inflattivo e rischio di crescita. Sarebbe prematuro tradurla direttamente in una decisione di politica monetaria.'
    :dh>.05&&dl<=0?'L’inflazione si sta rafforzando mentre la disoccupazione non peggiora. Il mercato potrebbe rivedere il sentiero monetario, ma il dato decisivo è la sorpresa rispetto alle attese e la sua persistenza.'
    :dh<-.05&&dl>.05?'Inflazione più debole e lavoro meno solido rendono plausibile una discussione sulla domanda, ma non dimostrano che la banca centrale cambierà rotta.'
    :dh<-.05&&dl<=0?'Inflazione in diminuzione senza un nuovo aumento della disoccupazione è un mix potenzialmente più favorevole. Non equivale però a un segnale FX: servono differenziali e prezzi.'
    :'Le variazioni sono modeste o contrastanti. Il livello da solo non ci informa su un turning point del ciclo.'
    :'Manca una sequenza di osservazioni sufficiente a distinguere livello e accelerazione. Non costruisco una svolta macro a partire da un solo numero.';
   const ratesSentence=r&&finite(r.chg2_bp)&&isDate(r.date)
    ?'Il rendimento governativo 2Y di '+country+' si muove di '+move(r.chg2_bp)+' al '+date(r.date)+'. È un prezzo di mercato, non una misura pura di aspettative OIS.'
    :'Non abbiamo una variazione del 2Y sufficientemente datata per confrontarla con la lettura macro.';
   const check=o&&finite(o.change_1d_bp)&&isDate(o.as_of)
    ?'Il 6M del mercato monetario indica '+move(o.change_1d_bp)+' al '+date(o.as_of)+', ma il legame con una pubblicazione macro richiede stesso intervallo e orario.'
    :'Sul 6M manca una variazione giornaliera omogenea, quindi il repricing della banca centrale resta da dimostrare.';
   return {scope:cLabel(country),title:'È il ciclo economico a cambiare, oppure il modo in cui lo leggiamo?',
    paragraphs:[
     'Per '+cLabel(country)+' l’ultima fotografia disponibile dice che '+inflation+', mentre '+labour+'. Le due serie possono riferirsi a mesi differenti: non sono uno shock simultaneo.',
     tension+' '+ratesSentence,
     caseIntro+' '+check+' Nel laboratorio sottostante i grafici delle serie aiutano a verificare la sequenza dei movimenti; composizione, salari e nuove sorprese possono cambiare il giudizio.'
    ],asof:showPeriod(i?.as_of)+' · lavoro '+showPeriod(l?.as_of),next:'rates',nextLabel:'Confronta con Tassi & OIS'};
  }
  function ratesEssay(){
   const c=country,r=rates[c],h=ois[c]?.horizons?.['6m'],o=ois[c],rO=rates[state.against]||null;
   const rOK=r&&finite(r['2Y'])&&finite(r['10Y'])&&finite(r.chg2_bp)&&finite(r.chg10_bp)&&isDate(r.date);
   const front=rOK?r.chg2_bp:null,long=rOK?r.chg10_bp:null;
   const both=finite(front)&&finite(long)&&(front>0&&long>0||front<0&&long<0);
   const curve=both?(front<0?(front<long?'bull steepening':'bull flattening'):(front>long?'bear flattening':'bear steepening')):'movimento di curva non univoco';
   const description=rOK?'Al '+date(r.date)+' il governativo 2Y di '+c+' è '+fmt(r['2Y'],3)+'%, il 10Y '+fmt(r['10Y'],3)+'%; le variazioni sono '+move(front)+' e '+move(long)+'. La lettura di forma è '+curve+'.'
    :'Per '+c+' non abbiamo contemporaneamente livelli e variazioni verificabili di 2Y e 10Y, quindi non assegniamo un nuovo regime alla curva.';
   const repricing=h&&finite(h.rate)&&isDate(h.as_of)
    ?'Il riferimento 6M è '+fmt(h.rate,3)+'% al '+date(h.as_of)+' ('+(o.kind||'strumento non specificato')+', '+(o.quality||'qualità da verificare')+'). '+(finite(h.change_1d_bp)?'La sua variazione a un giorno è '+move(h.change_1d_bp)+'.':'Non è disponibile una variazione 1D validata: il livello non racconta come sono cambiate oggi le attese.')
    :'Il 6M non presenta data e livello validati: non deduciamo il repricing dai soli governativi.';
   const spread=rOK&&rO&&finite(rO['2Y'])&&rO.date===r.date
    ?'Il differenziale governativo 2Y '+c+'–'+state.against+' è '+sign((r['2Y']-rO['2Y'])*100,1,' pb')+' sulla medesima data. È uno spread osservato, non il rendimento atteso di un cross FX.'
    :'Il differenziale tra governativi non è confrontabile sulla stessa data oppure manca uno dei due benchmark: non mostriamo uno spread come simultaneo.';
   const alternatives=front<0?'Un 2Y in calo può riflettere attese di tassi più bassi oppure una domanda di duration. Il 10Y, i real yields e il credito aiutano a distinguere le spiegazioni.'
    :front>0?'Un 2Y in rialzo può derivare da aspettative monetarie più restrittive, ma il long-end può essere guidato anche da crescita, term premium e offerta.'
    :'Con variazioni piccole o non osservate non esiste una direzione monetaria credibile da inferire.';
   return {scope:cLabel(c),title:'La curva si muove. Ma quale aspettativa è davvero cambiata?',
    paragraphs:[description+' '+alternatives,repricing+' Non sovrapponiamo futures, OIS e titoli governativi come se fossero lo stesso contratto.',spread+' '+caseIntro+' Se OIS, spread e prezzo FX non convergono, la nostra interpretazione deve restare aperta.'],
    asof:sourceLabel(r?.date),next:'currencies',nextLabel:'Verifica la reazione FX'};
  }
  function currenciesEssay(){
   const c=country,against=other,forward=pairs[c+against],reverse=pairs[against+c],selected=forward||reverse;
   const pair=selected?.canonical_pair||selected?.setup?.pair||(forward?c+'/'+against:against+'/'+c);
   const frame=selected?.decision_frame||selected?.setup?.structural||{};
   const r=rates[c],b=rates[against];
   const alignment=r&&b&&finite(r['2Y'])&&finite(b['2Y'])&&r.date===b.date&&isDate(r.date);
   const spread=alignment?'Tra '+c+' e '+against+' il differenziale dei rendimenti governativi 2Y è '+sign((r['2Y']-b['2Y'])*100,1,' pb')+' al '+date(r.date)+'. È un confronto tra livelli, non la misura di una sorpresa monetaria.':'I governativi di '+c+' e '+against+' non consentono un differenziale 2Y con date coincidenti. La lettura resta relativa, ma non attribuiamo uno spread attuale.';
   const contrast=frame.relation
    ?'Nel dossier '+pair+' il modello rileva: «'+frag(frame.relation)+'». '+(frame.priceNote||'La verifica del prezzo è ancora aperta.')
    :'Per il confronto selezionato non è disponibile un giudizio strutturale certificato nel motore delle 28 coppie. Non sostituiamo questa assenza con un ranking inventato.';
   const cpi=macro[c]?.inflation,otherCpi=macro[against]?.inflation;
   const compare=finite(cpi?.latest_value)&&finite(otherCpi?.latest_value)
    ?'La fotografia d’inflazione differisce: '+c+' '+fmt(cpi.latest_value,2)+'% ('+showPeriod(cpi.as_of)+'), '+against+' '+fmt(otherCpi.latest_value,2)+'% ('+showPeriod(otherCpi.as_of)+'). Non sono sorprese confrontabili se periodi e definizioni non coincidono.'
    :'Il confronto macro tra le due economie è parziale: non possiamo trasformarlo in una forza valutaria certa.';
   const cost=selected?.decision_frame?.missing?'Il modello considera ancora aperto questo punto: '+frag(selected.decision_frame.missing)+'.':'La tesi dovrebbe essere controllata sui differenziali, sul prezzo e su possibili cambiamenti del contesto globale.';
   return {scope:c+'/'+against,title:'Una valuta non è forte da sola: conta contro chi la confrontiamo.',
    paragraphs:[compare+' '+spread,contrast+' La coppia quotata nel dossier può avere verso opposto alla selezione: la direzione va letta rispettando numeratore e denominatore.',caseIntro+' '+cost+' Nei dati di prezzo qui sotto verifica se il movimento è una continuazione, un recupero o una divergenza, non un ingresso automatico.'],
    asof:sourceLabel(get('pairs')?.price_asof),next:'pairs',nextLabel:'Leggi la tesi relativa completa'};
  }
  function pairsEssay(){
   const k=state.pair||'EURUSD',p=pairs[k],f=p?.decision_frame||p?.setup?.structural||{},s=p?.setup||{};
   const priceDate=get('pairs')?.price_asof,macroDate=get('pairs')?.macro_baseline_asof;
   const headline=p?frag(f.relation||s.structural?.relation||'Il modello non identifica un vantaggio pulito'):'Nessuna valutazione verificata per la coppia selezionata';
   const fav=f.fav&&f.fav!=='—'?f.fav:(s.structuralFav||null);
   const pText=f.priceNote||s.price?.text||'Il prezzo non è classificato';
   const tension=p?'La struttura attribuisce '+(fav?'un vantaggio relativo a '+fav:'nessun vantaggio relativo confermato')+'. Il giudizio sui prezzi è distinto: '+frag(pText)+'.':'Non è disponibile una valutazione della coppia che soddisfi il contratto dati.';
   const missing=f.missing||'Non abbiamo una conferma indipendente da macro, tassi e prezzi.';
   const cth=get('cot')?.[k.slice(0,3)],cth2=get('cot')?.[k.slice(3)];
   const contrarian=cth?.signal&&cth2?.signal?'Il posizionamento non equivale alla forza della coppia: '+k.slice(0,3)+' '+cth.signal+', '+k.slice(3)+' '+cth2.signal+'. Si tratta di futures valutari, non di flussi spot sincronizzati con il fixing.':'Il COT di entrambe le valute non è disponibile su base verificabile.';
   return {scope:k.slice(0,3)+'/'+k.slice(3),title:fav?'Una direzione favorita non è ancora un buon trade.':'Non sempre il mercato offre un vantaggio da sfruttare.',
    paragraphs:['Il punto di partenza del dossier '+k.slice(0,3)+'/'+k.slice(3)+' è questo: «'+headline+'». '+tension,
     'L’ipotesi si indebolirebbe se la parte oggi favorita perdesse il vantaggio di Macro o Pricing, oppure se il prezzo non riuscisse a confermarlo. Il controllo più immediato è: '+frag(missing)+'. '+contrarian,
     caseIntro+' Il prezzo è riferito al '+sourceLabel(priceDate)+(macroDate?', mentre la baseline macro del motore è '+sourceLabel(macroDate):'')+'. Non confondiamo la solidità della tesi con l’attrattività di un ingresso ai prezzi attuali.'],
    asof:sourceLabel(priceDate),next:'cot',nextLabel:'Esamina il posizionamento'};
  }
  function cotEssay(){
   const s=cot[country],series=get('cotHistory')?.[country],d=series?.dates||[],n=d.length;
   const check=Array.isArray(d)&&n>=5&&['net','long','short','percentile'].every(k=>Array.isArray(series?.[k])&&series[k].length===n)
    &&validDay(d.at(-1))&&d.at(-1)<=dayNow();
   const current=check?{date:d.at(-1),net:series.net.at(-1),long:series.long.at(-1),short:series.short.at(-1),percentile:series.percentile.at(-1),
     d1:series.net.at(-1)-series.net.at(-2),l1:series.long.at(-1)-series.long.at(-2),s1:series.short.at(-1)-series.short.at(-2)}:null;
   const flow=current?
    'Il netto è '+(current.net>=0?'long':'short')+' per '+fmt(Math.abs(current.net),0)+' contratti, al percentile P'+fmt(current.percentile,1)+' delle ultime 104 settimane. Nell’ultima rilevazione il netto cambia di '+sign(current.d1,0,' contratti')+', con long '+sign(current.l1,0)+' e short '+sign(current.s1,0)+'.':
    'Lo storico CFTC non è abbastanza coerente per calcolare stock, long e short della stessa rilevazione: l’interpretazione del flusso è sospesa.';
   const cause=current
    ?current.d1>0&&current.s1<0&&current.l1<=0?'Il miglioramento del netto proviene soprattutto dalla riduzione degli short, non da nuovi acquisti netti di long.'
     :current.d1>0&&current.l1>0?'I nuovi long contribuiscono al miglioramento del netto; controlla comunque se esistono anche ricoperture.'
     :current.d1<0&&current.s1>0?'L’aumento degli short contribuisce al deterioramento del netto.'
     :current.d1<0&&current.l1<0?'La liquidazione di long contribuisce al peggioramento del netto.'
     :'I flussi si compensano: il segno del saldo non racconta da solo tutti i movimenti.':'Non deduciamo nuovi long, nuovi short o coperture da un dato aggregato non validato.';
   const priceDoc=get('cotPrice'),priceRow=priceDoc?.currencies?.[country];
   const priceAligned=current&&priceDoc?.price_alignment===current.date&&priceRow?.as_of===current.date&&priceRow.net===current.net;
   return {scope:country,title:'Il vero cambiamento non è soltanto dove sono i fondi, ma che cosa stanno facendo.',
    paragraphs:['Per '+country+' la fotografia settimanale CFTC del '+sourceLabel(current?.date)+' dice: '+flow+' '+cause,
     'Un estremo storico può persistere: l’affollamento non dà un segnale di inversione. '+(priceAligned?'Esiste una serie prezzo collegata alla stessa rilevazione CFTC, ma per parlare di conferma servono ancora intervalli coerenti e variazioni osservate.':'Il prezzo non è validato sulla stessa sequenza CFTC: non possiamo dire che il movimento spot abbia già confermato o negato questo flusso.'),
     caseIntro+' Nei grafici sotto confronta la persistenza su più settimane, il netto normalizzato e la composizione long/short. Prima di parlare di FX, torna ai differenziali e al movimento della coppia scelta.'],
    asof:sourceLabel(current?.date),next:'pairs',nextLabel:'Confronta con il prezzo della coppia'};
  }
  function riskEssay(){
   const n=risk.NASDAQCOM||{},v=risk.VIX||{},h=risk.HY_OAS||{},sp=risk.SP500||{};
   const aligned=isDate(n.date)&&n.date===v.date&&n.date===h.date&&finite(n.change_1d_pct)&&finite(v.value)&&finite(v.previous)&&finite(h.value)&&finite(h.previous);
   const observation=aligned?'Nella seduta del '+date(n.date)+' il Nasdaq ha registrato '+sign(n.change_1d_pct,2,'%')+', il VIX '+sign(v.value-v.previous,2,' punti')+' e lo spread HY '+sign((h.value-h.previous)*100,0,' pb')+'.'
    :'Nasdaq, VIX e credito non hanno tutte osservazioni datate della stessa seduta: non è possibile misurare una risposta simultanea senza ulteriori dati.';
   const breadth=aligned&&finite(sp.change_1d_pct)&&sp.date===n.date?'L’S&P 500 si è mosso di '+sign(sp.change_1d_pct,2,'%')+' nella stessa seduta: la distanza tra i due indici aiuta a distinguere un problema concentrato nel tech da una pressione più ampia.':'Manca un confronto verificato con l’indice ampio sulla stessa data.';
   const thesis=aligned&&n.change_1d_pct<0&&v.value>v.previous&&h.value>h.previous
    ?'La combinazione è coerente con un aumento della domanda di protezione e del premio per il credito, ma non dimostra l’origine dello shock.'
    :aligned&&n.change_1d_pct>0&&v.value<v.previous&&h.value<h.previous
    ?'Il quadro è coerente con una distensione del rischio, non necessariamente con una riaccelerazione della crescita.'
    :'I segnali non convergono in una diagnosi unica: può trattarsi di differenze di timing, di shock settoriali o di dinamiche tecniche.';
   return {scope:'Cross-asset',title:'La differenza fra una correzione e uno stress sistemico è nel credito.',
    paragraphs:[observation+' '+breadth,thesis+' Il VIX misura aspettative di volatilità azionaria; lo spread HY misura il premio richiesto sui bond speculativi. Non sono due modi per rappresentare la stessa cosa.',caseIntro+' Questa ipotesi sarebbe indebolita da una normalizzazione persistente del VIX e da spread HY in restringimento; sarebbe rafforzata da un peggioramento esteso e duraturo. I grafici sottostanti permettono di guardare le serie separatamente.'],
    asof:sourceLabel(n.date),next:'rates',nextLabel:'Verifica il movimento dei Treasury'};
  }
  function newsEssay(){
   const feed=get('news')||{},items=Array.isArray(feed.items)?feed.items:[];
   const valid=items.filter(x=>isDate(x.as_of)&&x.as_of<=dayNow()).sort((a,b)=>b.as_of.localeCompare(a.as_of));
   const selected=valid.find(x=>x.ccy===country)||valid[0];
   const event=selected?'Nel flusso datato al '+date(selected.as_of)+' compare questa notizia: «'+frag(selected.title||selected.category||'Evento')+'». '+frag(selected.detail||'La fonte riporta un aggiornamento che richiede un confronto con il prezzo')+'.':
    'Non sono disponibili eventi con data verificabile: una notizia non può essere usata per giustificare il movimento dei prezzi senza una fonte.';
   const hasSurprise=selected?.category&&/SURPRISE|RELEASE/.test(selected.category);
   const what=hasSurprise?'Anche quando conosciamo il dato pubblicato, dobbiamo verificare quale consenso fosse disponibile prima della release e se vi siano revisioni.':'Una headline sui tassi o sui futures non misura da sola la sorpresa economica: contiene già l’interpretazione di uno strumento o di una fonte.';
   return {scope:selected?.ccy||'Mercati',title:'Un titolo di giornale diventa ricerca soltanto quando cambia una tesi.',
    paragraphs:[event,what+' Per attribuire una reazione servono strumenti, prezzo prima e dopo e orari coerenti; in loro assenza il nesso resta una possibilità, non un fatto.',caseIntro+' La domanda utile è se la notizia modifica una delle prove centrali della ricerca. Se non muove aspettative, posizionamento o prezzo, può essere interessante senza essere operativamente decisiva.'],
    asof:sourceLabel(selected?.as_of||feed.content_as_of),next:'overview',nextLabel:'Torna alla ricerca principale'};
  }
  const renderers={macro:macroEssay,rates:ratesEssay,currencies:currenciesEssay,pairs:pairsEssay,cot:cotEssay,risk:riskEssay,news:newsEssay};
  function render(route){
   const build=renderers[route];if(!build)return '';
   const item=build();
   const asof=item.asof||'Data da validare';
   const link=item.next&&item.next!=='overview'?item.next:'overview';
   const ps=item.paragraphs||[];
   return '<section class="research-essay research-essay-dashboard" aria-label="Interpretazione editoriale '+esc(route)+'">'
    +'<div class="essay-top"><span>FX QUANT / LETTURA DEL DESK</span><span>'+esc(item.scope||'Mercati')+' · '+esc(asof)+'</span></div>'
    +'<div class="essay-dashboard-grid"><div><h2>'+esc(item.title)+'</h2><div class="essay-prose"><p>'+esc(ps[0]||'Non abbiamo una lettura sufficientemente verificata.')+'</p>'
    +'<details class="essay-details"><summary>Approfondisci il ragionamento <span aria-hidden="true">＋</span></summary>'
    +ps.slice(1).map(p=>'<p>'+esc(p)+'</p>').join('')+'</details></div></div>'
    +'<aside class="essay-visual-guide"><span>IL LABORATORIO QUI SOTTO</span><strong>Prima osserva i dati.</strong><p>I grafici, le curve e le tabelle restano al centro di questa pagina. La lettura del desk spiega cosa cercare, quali limiti considerare e come verificare la tesi.</p><a href="#'+link+'">'+esc(item.nextLabel||'Torna alla ricerca')+' ↗</a></aside></div>'
    +'<div class="essay-foot"><span>Fonti con date proprie. Analisi descrittiva, non raccomandazione di trading.</span></div></section>';
  }
  return {render};
 }
 if(typeof window!=='undefined')window.FXQuantResearchEditorial={create};
 if(typeof module!=='undefined'&&module.exports)module.exports={create};
})();