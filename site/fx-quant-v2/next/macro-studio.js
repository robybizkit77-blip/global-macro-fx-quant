'use strict';
/**
 * FX Quant NEXT — Macro Dynamics Research Studio
 *
 * Two deliberately separate evidence layers:
 * (1) MACRO_SERIES: source-labelled dated observations, often revised;
 *     compute descriptive 1-observation and 3-observation changes only.
 * (2) MACRO_THERMOMETER_DATA: country-specific historical percentiles,
 *     two separate dimensions (inflation and unemployment), no FX ranking.
 * No consensus/surprises, probabilistic forecasts, causal claims or PIT backtests.
 */
(function(root){
function build(api){
 const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow}=api;
 const mdata=get('macro')?.currencies||{},catalog=get('macroSeries')||{},locDate=dayNow();
 const categories=['Crescita','Inflazione','Lavoro','Housing','Credito','Liquidità','Condizioni finanziarie','Rates','Lead / survey'];
 const country=FX.includes(state.ccy)?state.ccy:'USD';
 const monthKey=s=>{
   if(typeof s!=='string')return '';
   if(/^\d{4}-\d{2}(?:-\d{2})?$/.test(s))return s.slice(0,7);
   if(/^\d{4}Q[1-4]$/.test(s))return s.slice(0,4)+'-'+String(Number(s.slice(-1))*3).padStart(2,'0');
   return '';
 };
 const eligible=s=>!!s&&Array.isArray(s.dates)&&Array.isArray(s.values)&&s.dates.length===s.values.length&&s.dates.length>2;
 const list=ccy=>(Array.isArray(catalog[ccy])?catalog[ccy]:[]).filter(eligible);
 const valid=s=>!!s&&eligible(s)&&s.values.some(finite);
 const history=s=>{
   if(!valid(s))return [];
   const pairs=s.dates.map((p,i)=>({period:p,value:s.values[i],idx:i}))
    .filter(x=>finite(x.value)&&!!monthKey(x.period)&&monthKey(x.period)<=locDate.slice(0,7));
   // Preserve source ordering (quarterly, monthly and mixed ISO labels).
   return pairs;
 };
 const available=()=>list(country);
 const allCats=()=>categories.filter(c=>available().some(s=>s.category===c));
 const category=()=>allCats().includes(state.msCategory)?state.msCategory:allCats()[0]||'Inflazione';
 const preferred=(series,cat)=>{
   if(cat==='Inflazione')return series.find(s=>/CPI headline|HICP headline|CPI core/i.test(s.label))||series[0];
   if(cat==='Lavoro')return series.find(s=>/Disoccupazione/i.test(s.label))||series[0];
   if(cat==='Crescita')return series.find(s=>/PIL reale|Consumi reali|Produzione industriale/i.test(s.label))||series[0];
   return series[0];
 };
 const selectedSeries=()=>{
   const arr=available().filter(s=>s.category===category());
   return arr.find(s=>s.id===state.msSeriesId)||preferred(arr,category())||null;
 };
 const measure=s=>{
   const u=String(s?.unit||'').trim();
   return /%|percent|percentage/i.test(u)?'p.p.':u?'unità originali':'unità (metadato fonte incompleto)';
 };
 function stats(s){
   const h=history(s),cur=h.at(-1),pr=h.at(-2),pr2=h.at(-3),four=h.at(-4);
   const x=cur?.value,p=pr?.value,v=pr2?.value;
   const d1=finite(x)&&finite(p)?x-p:null,dprev=finite(p)&&finite(v)?p-v:null;
   const speed=finite(d1)&&finite(dprev)?d1-dprev:null;
   const span=finite(x)&&finite(four)?x-four.value:null;
   const percent=finite(x)&&finite(p)&&p!==0?(x/p-1)*100:null;
   const turn=finite(d1)&&finite(dprev)&&Math.sign(d1)!==0&&Math.sign(dprev)!==0&&Math.sign(d1)!==Math.sign(dprev);
   return {h,cur,pr,d1,dprev,speed,span,percent,turn,unit:measure(s),quality:eligible(s)&&h.length>=3};
 }
 function n(v,d=2){return finite(v)?fmt(v,d):'—'}
 function labelDirection(delta){
   return !finite(delta)?'Dati insufficienti':delta>0?'IN AUMENTO':delta<0?'IN CALO':'INVARIATO';
 }
 function explDelta(s,st){
   const f=s?.frequency||'frequenza non dichiarata';
   return 'Serie '+(s?.label||'')+': '+labelDirection(st.d1).toLowerCase()+', '+(finite(st.d1)?sign(st.d1,2,' '+st.unit):'variazione non calcolabile')+
    ' fra le ultime due osservazioni ('+String(st.pr?.period||'n.d.')+' → '+String(st.cur?.period||'n.d.')+'). Frequenza '+f+'.';
 }
 function dynamics(st){
   if(!finite(st.d1)||!finite(st.dprev))return 'Servono tre osservazioni per parlare di accelerazione o decelerazione della variazione.';
   const a=st.d1,b=st.dprev;
   if(a===0)return 'La variazione fra le ultime due osservazioni è nulla; il trend non è automaticamente terminato.';
   const speed=Math.abs(a)-Math.abs(b);
   if(Math.sign(a)!==Math.sign(b)&&b!==0)return 'Possibile cambio di direzione fra le ultime due variazioni. È soltanto un candidato turning point, non un’inversione confermata.';
   if(Math.abs(speed)<0.0000001)return 'La dimensione dell’ultima variazione è simile alla precedente: velocità relativamente costante nel campione osservato.';
   return speed>0?'Il movimento nella stessa direzione sta acquistando ampiezza rispetto alla variazione precedente.':'Il movimento continua nella stessa direzione, ma perde ampiezza: possibile decelerazione, da confermare.';
 }
 function fmtPeriod(p){
   return typeof p==='string'?p:'n.d.';
 }
 function countryStrip(){
   return '<div class="macro-country-strip" role="group" aria-label="Scegli economia G8">'+FX.map(ccy=>{
     const x=mdata[ccy],c=list(ccy).length;
     return '<button type="button" data-ms-country="'+ccy+'" class="macro-country '+(ccy===country?'active':'')+'" aria-pressed="'+String(ccy===country)+'">'
       +'<span>'+FLAGS[ccy]+' '+ccy+'</span><strong>'+c+'</strong><small>serie storiche</small></button>';
   }).join('')+'</div>';
 }
 function thermoRecord(ccy,k){
   const x=mdata[ccy]?.[k];
   return x&&finite(x.latest_value)&&finite(x.percentile)?x:null;
 }
 function thermo(ccy,k){
   const x=thermoRecord(ccy,k);
   const name=k==='inflation'?'INFLAZIONE':'DISOCCUPAZIONE';
   if(!x)return '<div class="macro-temperature"><span>'+name+'</span><strong>—</strong><small>Termometro non validato</small></div>';
   return '<div class="macro-temperature"><div><span>'+name+' / '+esc(ccy)+'</span><strong>'+fmt(x.latest_value,2)+'%</strong><small>'+esc(x.as_of)+' · '+esc(x.source||'fonte da verificare')+'</small></div>'
   +'<div class="macro-thermometer"><span style="--pct:'+Math.max(0,Math.min(100,x.percentile))+'%"></span></div><div class="macro-temp-bottom"><span>'+esc(x.temperature_label||'—').replace(/_/g,' ')+'</span><b>P'+fmt(x.percentile,1)+'</b></div>'
   +'<p>Direzione: '+esc(x.direction||'—')+' · Velocità: '+esc(x.acceleration||'—')+'</p></div>';
 }
 function usdHouseholdEvidence(){
   // A revised BEA/FRED vintage can describe today; it is never historical PIT.
   const pce=list('USD').find(x=>x.id==='US_PCEC96_history_value');
   const dpi=list('USD').find(x=>x.id==='US_DSPIC96_history_DSPIC96');
   const certified=(r,id)=>r&&valid(r)&&r.frequency==='M'&&
     r.unit==='Billions of Chained 2017 Dollars SAAR'&&
     r.current_vintage_provenance?.status==='BEA_REVISED_HISTORY_VIA_FRED_CURRENT_NOT_PIT'&&
     r.current_vintage_provenance?.issuer==='US_BEA'&&
     r.current_vintage_provenance?.source_series_id===id&&
     r.current_vintage_provenance?.source_series_first_release_PIT_certified===false;
   if(!certified(pce,'PCEC96')||!certified(dpi,'DSPIC96'))return null;
   const p=history(pce),d=history(dpi);
   if(p.length<3||d.length<2)return null;
   const ord=s=>Number(s.slice(0,4))*12+Number(s.slice(5,7));
   const period=monthKey(p.at(-1).period),current=locDate.slice(0,7);
   if(!period||period!==monthKey(d.at(-1).period)||
      period!==monthKey(pce.last_date)||period!==monthKey(dpi.last_date)||
      ord(current)-ord(period)<0||ord(current)-ord(period)>3||
      ord(period)-ord(monthKey(p.at(-2).period))!==1||
      ord(period)-ord(monthKey(d.at(-2).period))!==1||
      ord(monthKey(p.at(-2).period))-ord(monthKey(p.at(-3).period))!==1)return null;
   const [p0,p1,p2]=[p.at(-1).value,p.at(-2).value,p.at(-3).value];
   const [d0,d1]=[d.at(-1).value,d.at(-2).value];
   if(![p0,p1,p2,d0,d1].every(x=>finite(x)&&x>0))return null;
   const pc=(p0/p1-1)*100,prior=(p1/p2-1)*100,dc=(d0/d1-1)*100;
   const pct=x=>{const r=Math.round(x*10)/10;return (r>0?'+':r<0?'−':'')+fmt(Math.abs(r),1)+'%';};
   const months=['gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto',
                 'settembre','ottobre','novembre','dicembre'];
   const time=months[Number(period.slice(5,7))-1]+' '+period.slice(0,4);
   const soft=Math.abs(pc)<.05,falling=dc<-.05;
   return {
     title:soft&&falling?'I consumi reali frenano, il reddito arretra.':
       'Consumi e reddito reali: cosa sta cambiando?',
     facts:'A '+time+' i consumi reali variano '+pct(pc)+' sul mese (contro '+
       pct(prior)+' nel mese precedente); il reddito disponibile reale varia '+
       pct(dc)+'. Sono valori al netto dei prezzi.',
     why:soft&&falling?
       'La spesa reale perde slancio mentre il reddito disponibile reale cala: è un segnale di cautela sulla domanda, non la prova di una recessione. Un mese non basta per confermare una svolta.':
       'Il confronto fra spesa e reddito reali aiuta a leggere la domanda; composizione e persistenza vanno ancora verificate. Una sola pubblicazione non dimostra una svolta.',
     limit:'I dati BEA/FRED sono storici revisionati, non prime pubblicazioni point-in-time. Non dimostrano da soli variazioni nelle attese Fed, nei futures OIS o nell’USD.',
     verdict:soft&&falling?'DOMANDA REALE / FRENO DA CONFERMARE':
       'DOMANDA REALE / QUADRO DA CONFERMARE',
     watch:'Controlla le prossime letture di spesa reale, redditi e servizi, poi inflazione core e lavoro. Una tesi USD richiede anche conferme da aspettative Fed, tassi e prezzo.'
   };
 }
 function countryNarrative(){
   const i=thermoRecord(country,'inflation'),l=thermoRecord(country,'labour');
   const ih=Array.isArray(i?.history)?i.history:[],lh=Array.isArray(l?.history)?l.history:[];
   const di=ih.length>1?ih.at(-1)-ih.at(-2):null,dl=lh.length>1?lh.at(-1)-lh.at(-2):null;
   const id=finite(di)?di>0.025?1:di<-.025?-1:0:null;
   const ld=finite(dl)?dl>.025?1:dl<-.025?-1:0:null;
   const title=id===1&&ld===1?'L’inflazione risale, mentre il lavoro perde terreno.'
     :id===1&&ld===-1?'L’inflazione risale, ma il lavoro per ora tiene.'
     :id===-1&&ld===1?'La pressione sui prezzi cala; il lavoro si indebolisce.'
     :id===-1&&ld===-1?'L’inflazione rallenta senza un netto deterioramento del lavoro.'
     :id===0&&ld===1?'Prezzi quasi fermi, ma la disoccupazione sale.'
     :id===1&&ld===0?'La pressione dei prezzi aumenta; il lavoro è più stabile.'
     :id===-1&&ld===0?'I prezzi rallentano, il lavoro non cambia molto.'
     :'I dati non indicano ancora una direzione unica.';
   const countryName=({USD:'Negli Stati Uniti',EUR:'Nell’Eurozona',GBP:'Nel Regno Unito',JPY:'In Giappone',CHF:'In Svizzera',AUD:'In Australia',NZD:'In Nuova Zelanda',CAD:'In Canada'})[country]||'Nel Paese selezionato';
   const a=finite(i?.latest_value)?'l’inflazione è '+fmt(i.latest_value,2)+'% al '+(i.as_of||'n.d.')+(finite(di)?' ('+sign(di,2,' punti percentuali')+' dalla rilevazione precedente)':'')
     :'non abbiamo un dato d’inflazione validato';
   const b=finite(l?.latest_value)?'la disoccupazione è '+fmt(l.latest_value,2)+'% al '+(l.as_of||'n.d.')+(finite(dl)?' ('+sign(dl,2,' punti percentuali')+' dalla rilevazione precedente)':'')
     :'non abbiamo un dato di disoccupazione validato';
   const facts=countryName+' '+a+', mentre '+b+'. I periodi possono essere diversi: è una fotografia macro, non una reazione a una singola pubblicazione.';
   const why=id===1&&ld===1?'È un mix delicato: prezzi più persistenti possono limitare lo spazio per tagliare, mentre un lavoro meno solido aumenta il rischio sulla crescita.'
     :id===1&&ld===-1?'Un lavoro che non peggiora insieme a prezzi in risalita rende meno immediata una lettura monetaria accomodante.'
     :id===-1&&ld===1?'La combinazione rende più plausibile una pressione verso politiche meno restrittive, ma il mercato potrebbe averla già anticipata.'
     :id===-1&&ld===-1?'Un’inflazione meno forte con disoccupazione in calo può migliorare il quadro senza implicare automaticamente tagli dei tassi.'
     :id===1?'La pressione inflazionistica merita attenzione, ma un singolo dato non basta a determinare la prossima decisione della banca centrale.'
     :ld===1?'Il lavoro manda un segnale di cautela. Servono conferme da occupazione, salari e credito.'
     :'Non forzo una narrativa unica: aspetterei conferme dagli altri indicatori e da come reagiscono i tassi.';
   const r=get('rates')?.[country],validR=r&&finite(r.chg2_bp)&&validDay(r.date)&&r.date<=dayNow();
   const reading=validR?'Intanto il rendimento governativo 2Y '+country+' ha registrato '+sign(r.chg2_bp,1,' pb')+' nel feed, al '+date(r.date)+'. Questo movimento non misura da solo il repricing OIS.':'Per questa economia non abbiamo una variazione 2Y sufficientemente datata per confermare il repricing.';
   const verdict=id===1&&ld===1?'TENSIONE PREZZI / LAVORO'
     :id===1&&ld===-1?'PRESSIONE INFLAZIONISTICA'
     :id===-1&&ld===1?'POSSIBILE ALLENTAMENTO'
     :id===-1&&ld===-1?'MIX PIÙ COSTRUTTIVO':'QUADRO DA CONFERMARE';
   const watch='Prossima verifica: inflazione core, occupazione e salari; poi curva OIS e risposta del 2Y. Senza sorpresa rispetto al consenso, questa è una lettura di contesto, non una previsione.';
   if(country==='USD'){
     const demand=usdHouseholdEvidence();
     if(demand)return {
       title:demand.title,
       facts:facts+' '+demand.facts,
       why:demand.why,
       reading:reading+' '+demand.limit,
       verdict:demand.verdict,
       watch:demand.watch
     };
   }
   return {title,facts,why,reading,verdict,watch};
 }
 function countryHero(){
   const story=countryNarrative(),i=thermoRecord(country,'inflation'),l=thermoRecord(country,'labour');
   return '<section class="macro-country-hero macro-narrative-edition"><div class="macro-country-narrative">'
     +'<span class="chapter-kicker">IL DESK LEGGE / '+FLAGS[country]+' '+esc(NAMES[country])+'</span>'
     +'<span class="macro-verdict-line"><i></i>'+esc(story.verdict)+'</span>'
     +'<h2>'+esc(story.title)+'</h2>'
     +'<p class="macro-opening">'+esc(story.facts)+'</p>'
     +'<p class="macro-why">'+esc(story.why)+'</p>'
     +'<p class="macro-market-note">'+esc(story.reading)+'</p>'
     +'<div class="macro-next-evidence"><strong>CHE COSA CAMBIEREBBE IL GIUDIZIO</strong><p>'+esc(story.watch)+'</p></div>'
     +'</div><div class="macro-two-thermometers">'+thermo(country,'inflation')+thermo(country,'labour')+'</div></section>';
 }
 function sourceChart(s,st){
   const mode=state.msView||'level',window=Number(state.msWindow||24),pts=st.h.slice(-window);
   const derived=pts.map((x,i)=>mode==='change'?(i?{label:x.period,value:x.value-pts[i-1].value}:null):mode==='velocity'?(i>=2?{label:x.period,value:(x.value-pts[i-1].value)-(pts[i-1].value-pts[i-2].value)}:null):{label:x.period,value:x.value})
     .filter(x=>x&&finite(x.value));
   const legend=mode==='level'?'Valore osservato':mode==='change'?'Δ osservazione precedente':'ΔΔ variazione';
   const unit=mode==='level'?String(s.unit||'unità non specificata'):(st.unit==='p.p.'?'p.p.':'unità originali');
   return '<div class="macro-chart-heading"><div><span class="micro-over">SERIE STORICA / '+esc(s.frequency||'frequenza non dichiarata')+'</span><h3>'+esc(s.label)+'</h3></div>'
    +'<span class="data-date">Ultimo periodo '+esc(fmtPeriod(st.cur?.period))+'</span></div>'
    +'<div class="macro-graph-controls"><div class="pill-controls">'
    +[['level','Livello'],['change','Variazione'],['velocity','Accelerazione']].map(([v,l])=>'<button type="button" data-ms-view="'+v+'" aria-pressed="'+String(mode===v)+'" class="pill '+(mode===v?'active':'')+'">'+l+'</button>').join('')+'</div><div class="pill-controls">'
    +[12,24,60,240].map(w=>'<button type="button" data-ms-window="'+w+'" aria-pressed="'+String(window===w)+'" class="pill '+(window===w?'active':'')+'">'+(w===240?'Tutto':w)+' </button>').join('')+'</div></div>'
    +plot({lines:[{name:legend,color:mode==='level'?'#80d4c2':mode==='change'?'#8bcbe9':'#e6bb79',values:derived}],label:s.label+' / '+legend,precision:3})
    +'<div class="macro-chart-caption">Asse orizzontale: periodi originali della fonte ('+esc(st.h.at(0)?.period||'—')+' → '+esc(st.cur?.period||'—')+'). Finestra: ultime '+Math.min(window,st.h.length)+' osservazioni disponibili. Un grafico trimestrale non è convertito artificialmente in mensile.</div>'
    +'<div class="macro-datatype">Fonte: '+esc(s.source_file||'metadati non disponibili')+' · Unità '+esc(unit)+' · Frequenza '+esc(s.frequency||'non specificata')+'. Dati storici revisionabili, non archiviati point-in-time.</div>';
 }
 function macroResearch(){
   const s=selectedSeries();const cat=category(),arr=available().filter(x=>x.category===cat);
   if(!s)return '<div class="empty"><strong>Serie mancanti</strong><p>Per questa economia non sono presenti indicatori validati.</p></div>';
   const st=stats(s),labels=allCats(),direction=labelDirection(st.d1);
   const categoryButtons=labels.map(cat=>'<button type="button" data-ms-category="'+esc(cat)+'" aria-pressed="'+String(cat===category())+'" class="macro-category-pill '+(cat===category()?'active':'')+'">'+esc(cat)+'</button>').join('');
   const options=arr.map(x=>'<option value="'+esc(x.id)+'" '+(x.id===s.id?'selected':'')+'>'+esc(x.label)+' ('+esc(x.frequency||'n.d.')+')</option>').join('');
   return '<section class="macro-research"><div class="macro-section-head"><div><span class="chapter-kicker">02 / INDICATOR EXPLORER</span><h2>Scopri cosa sta cambiando. <em>Indicatore per indicatore.</em></h2></div>'
    +'<p>Passa da crescita a lavoro, credito o liquidità. Tutte le serie mantengono il periodo e l’unità originali.</p></div>'
    +'<div class="macro-category-line">'+categoryButtons+'</div>'
    +'<div class="macro-search-select"><label>INDICATORE · '+arr.length+' SERIE DISPONIBILI<select id="ms-series" class="select">'+options+'</select></label>'
    +'<span>'+esc(s.series_id||s.id)+' · '+esc(s.frequency||'frequenza non dichiarata')+'</span></div>'
    +'<div class="macro-core-grid"><div class="macro-main-chart">'+sourceChart(s,st)+'</div>'
    +'<aside class="macro-dynamic-reading"><span class="micro-over">FATTI / CAMBIAMENTO</span>'
    +'<h3>Non basta sapere<br><em>quanto vale.</em></h3>'
    +'<div class="macro-dynamic-kpi"><span>ULTIMO LIVELLO</span><strong>'+n(st.cur?.value,2)+'</strong><small>'+esc(s.unit||'unità non indicata')+' · '+esc(st.cur?.period||'n.d.')+'</small></div>'
    +'<div class="macro-mini-stats"><div><span>DIREZIONE</span><b>'+esc(direction)+'</b></div><div><span>Δ ULTIMA OSS.</span><b>'+sign(st.d1,3,' '+st.unit)+'</b></div><div><span>ΔΔ VARIAZIONE</span><b>'+sign(st.speed,3,' '+st.unit)+'</b></div></div>'
    +'<p><strong>La lettura del grafico:</strong> '+esc(explDelta(s,st)+' '+dynamics(st))+'</p><div class="macro-reading-caveat">Un cambiamento fra osservazioni non è una sorpresa rispetto al consenso né la conferma di un turning point economico.</div></aside></div></section>';
 }
 function interpretation(){
   const s=selectedSeries(),st=stats(s||{});if(!s)return '';
   let source=s.source_file||'dato senza fonte registrata';
   const rows=[
    ['01','LIVELLO','Che cosa vediamo?', 'Il valore di '+s.label+' è '+n(st.cur?.value,3)+' ('+(s.unit||'unità non indicata')+') nel periodo '+(st.cur?.period||'n.d.')+'. La fonte registrata è '+source+'.'],
    ['02','DIREZIONE','Come sta cambiando?',explDelta(s,st)],
    ['03','VELOCITÀ','Sta accelerando o decelerando?',dynamics(st)],
    ['04','TURNING POINT','È davvero un punto di svolta?',st.turn?'L’ultima variazione ha invertito il segno rispetto alla precedente: candidato turning point da confermare con nuove osservazioni e indicatori indipendenti.':'Non emerge un’inversione di segno fra le ultime due variazioni; ciò non esclude una svolta futura.'],
    ['05','MARKET PRICING','Il mercato lo sta prezzando?', 'Il feed macro non contiene consenso, sorpresa di pubblicazione né reazioni intraday. Confronta separatamente le curve OIS/futures e i rendimenti osservati alla data giusta. Non attribuire causalità a una sola serie.']
   ];
   return '<section class="macro-explain"><div class="macro-section-head"><div><span class="chapter-kicker">03 / LENTE INVESTIGATIVA</span><h2>Dalla rilevazione <em>alla tesi verificabile.</em></h2></div><p>Ogni frase distingue osservazione, trasformazione e interpretazione; nessun giudizio FX senza tassi e prezzo.</p></div>'
    +'<div class="macro-explain-grid">'+rows.map(([n,k,h,p])=>'<article><span class="macro-step">'+n+'</span><span class="micro-over">'+k+'</span><h3>'+esc(h)+'</h3><p>'+esc(p)+'</p></article>').join('')+'</div></section>';
 }
 function datedAudit(){
   const s=selectedSeries();if(!s)return '';
   const st=stats(s),a=st.h.slice(-12).reverse(),original=st.h;
   return '<section class="macro-audit"><div class="macro-section-head"><div><span class="chapter-kicker">04 / HISTORICAL AUDIT</span><h2>Le osservazioni <em>che contano.</em></h2></div><p>Non solo l’ultimo valore: confronta le ultime 12 rilevazioni, le loro differenze e le unità.</p></div>'
    +'<div class="table-wrap"><table class="data-table macro-table"><thead><tr><th>Periodo originale</th><th>Livello</th><th>Δ precedente</th><th>ΔΔ</th><th>Unità</th><th>Frequenza</th></tr></thead><tbody>'
    +a.map(r=>{const i=original.findIndex(x=>x.idx===r.idx),p=original[i-1],p2=original[i-2],d=p?r.value-p.value:null,dp=p&&p2?p.value-p2.value:null;
      return '<tr><td>'+esc(r.period)+'</td><td>'+fmt(r.value,3)+'</td><td>'+sign(d,3)+'</td><td>'+sign(finite(d)&&finite(dp)?d-dp:null,3)+'</td><td>'+esc(s.unit||'n.d.')+'</td><td>'+esc(s.frequency||'n.d.')+'</td></tr>';
    }).join('')+'</tbody></table></div></section>';
 }
 function heatUniverse(){
   const f=state.msHeat||'inflation',t=state.msHeatSort||'ccy',asc=state.msHeatAsc!==false;
   let rows=FX.map(c=>({c,a:thermoRecord(c,f),b:thermoRecord(c,f==='inflation'?'labour':'inflation'),n:list(c).length}));
   rows.sort((x,y)=>t==='ccy'?FX.indexOf(x.c)-FX.indexOf(y.c):((t==='level'?x.a?.latest_value||0:x.a?.percentile||0)-(t==='level'?y.a?.latest_value||0:y.a?.percentile||0))*(asc?1:-1));
   return '<section class="macro-universe"><div class="macro-section-head"><div><span class="chapter-kicker">05 / G8 MACRO HEATMAP</span><h2>Otto economie. <em>Contesti differenti.</em></h2></div><p>Il percentile confronta ogni serie con il proprio passato, non l’economia USD con l’economia EUR. Nessuna classifica di forza valutaria.</p></div>'
    +'<div class="macro-heat-controls"><div class="pill-controls">'+[['inflation','Inflazione'],['labour','Disoccupazione']].map(([v,l])=>'<button type="button" data-ms-heat="'+v+'" aria-pressed="'+String(f===v)+'" class="pill '+(v===f?'active':'')+'">'+l+'</button>').join('')+'</div><div class="pill-controls">'+[['ccy','Paese'],['percentile','Percentile'],['level','Livello']].map(([v,l])=>'<button type="button" data-ms-heat-sort="'+v+'" aria-pressed="'+String(t===v)+'" class="pill '+(v===t?'active':'')+'">'+l+'</button>').join('')+'</div></div>'
    +'<div class="macro-heat-grid">'+rows.map(({c,a,n})=>'<button class="macro-heat-row '+(c===country?'active':'')+'" type="button" data-ms-country="'+c+'"><div class="macro-heat-meta"><span>'+FLAGS[c]+' '+c+'</span><b>'+fmt(a?.latest_value,2)+'%</b><small>'+esc(a?.as_of||'n.d.')+'</small></div>'
     +'<div class="macro-heat-bar"><i style="width:'+Math.max(0,Math.min(100,a?.percentile||0))+'%"></i></div><div class="macro-heat-bottom"><span>'+esc(a?.temperature_label||'NON CLASSIFICATO').replace(/_/g,' ')+'</span><b>P'+fmt(a?.percentile,1)+'</b></div></button>').join('')+'</div>'
    +'<p class="macro-footnote">Fonte: Macro Heatmap V1. I percentili sono storici entro Paese/serie; i livelli non sono misure equivalenti di momentum FX. Inflazione e lavoro hanno date diverse e le definizioni nazionali possono non essere perfettamente armonizzate.</p></section>';
 }
 function relativePanel(){
   const c=country,other=FX.includes(state.msOther)&&state.msOther!==c?state.msOther:FX.find(k=>k!==c),x=mdata[c],y=mdata[other];
   const f=state.msCompareMetric||'inflation';
   const a=thermoRecord(c,f),b=thermoRecord(other,f);
   const mode=f==='inflation'?'inflazione':'disoccupazione';
   return '<section class="macro-relative"><div class="macro-section-head"><div><span class="chapter-kicker">06 / FX RELATIVE MACRO</span><h2>Due Paesi, <em>due traiettorie da investigare.</em></h2></div><p>La differenza di livelli non dimostra una valuta più forte. Confrontiamo contesto e date, poi tassi e prezzo.</p></div>'
   +'<div class="macro-compare-select"><label>ECONOMIA A<select class="select" id="ms-primary">'+FX.map(k=>'<option value="'+k+'" '+(k===c?'selected':'')+'>'+FLAGS[k]+' '+k+'</option>').join('')+'</select></label>'
   +'<label>ECONOMIA B<select class="select" id="ms-other">'+FX.filter(k=>k!==c).map(k=>'<option value="'+k+'" '+(k===other?'selected':'')+'>'+FLAGS[k]+' '+k+'</option>').join('')+'</select></label>'
   +'<div class="pill-controls">'+[['inflation','Inflazione'],['labour','Disoccupazione']].map(([k,l])=>'<button type="button" data-ms-compare="'+k+'" class="pill '+(k===f?'active':'')+'" aria-pressed="'+String(k===f)+'">'+l+'</button>').join('')+'</div></div>'
   +'<div class="macro-relative-grid">'+[[c,a],[other,b]].map(([k,z])=>'<div><span>'+FLAGS[k]+' '+k+' · '+esc(mode)+'</span><strong>'+fmt(z?.latest_value,2)+'%</strong><small>'+esc(z?.as_of||'n.d.')+' · direzione '+esc(z?.direction||'n.d.')+'</small><p>Percentile storico: P'+fmt(z?.percentile,1)+' · '+esc(z?.temperature_label||'n.d.').replace(/_/g,' ')+'</p></div>').join('')+'</div>'
   +'<div class="macro-relative-reading"><b>Lettura comparativa</b><p>'+(a&&b?'La differenza numerica degli ultimi livelli è '+sign(a.latest_value-b.latest_value,2,' punti percentuali')+', ma le due pubblicazioni sono datate '+esc(a.as_of)+' e '+esc(b.as_of)+'. Solo dati coerenti per periodo e definizione permettono una comparazione più forte.':'Dati macro incompleti: non calcoliamo un differenziale.')+
   ' Per l’FX controlla in seguito differenziali OIS/governativi e andamento della coppia.</p></div><a href="#rates" class="action-minimal">Continua sui tassi ↗</a></section>';
 }
 function glossary(){
   const entries=[
    ['Livello','Valore osservato nel periodo di riferimento. Non descrive da solo il cambiamento.'],
    ['Direzione (Δ)','Ultimo valore meno penultima osservazione. La differenza è in unità originali (punti percentuali se la serie è una percentuale).'],
    ['Velocità / ampiezza','Quanto si muove la serie fra osservazioni. Per misurare crescita economica serve interpretare la frequenza e la trasformazione della serie.'],
    ['Accelerazione (ΔΔ)','Variazione più recente meno variazione precedente. È una differenza seconda descrittiva, non una previsione.'],
    ['Turning point','Un cambio di segno nelle variazioni può essere un candidato, ma richiede conferma e può essere rumore statistico.'],
    ['Percentile storico','Collocazione rispetto alla distribuzione della stessa serie storica dentro il Paese, non un confronto diretto fra economie.'],
    ['Frequenza e date','Mensile (M) e trimestrale (Q) mantengono la loro struttura. Il nome del periodo non equivale necessariamente alla data di pubblicazione.'],
    ['Revisioni e point-in-time','Gli storici possono essere revisionati. Non sono automaticamente idonei a backtest senza archivio di vintage e timestamp di rilascio.'],
    ['Sorpresa macro','Effettivo meno consenso rilevato prima del rilascio. Nel feed attuale il consenso per ogni serie non è disponibile, quindi non viene inventato.'],
    ['Fonte / unità','Le metriche hanno fonti e unità differenti. La variazione di un indice o del PIL nominale non è direttamente confrontabile con la variazione di un tasso percentuale.']
   ];
   return '<section class="macro-glossary"><div class="macro-section-head"><div><span class="chapter-kicker">07 / METODO</span><h2>Capire bene <em>ogni indicatore.</em></h2></div><p>Un terminale di ricerca deve spiegare i concetti, non limitarsi a mostrarli.</p></div><div class="macro-definitions">'
    +entries.map(([x,y])=>'<details><summary>'+esc(x)+'<span>＋</span></summary><p>'+esc(y)+'</p></details>').join('')+'</div></section>';
 }
 function render(){
   const count=FX.reduce((acc,k)=>acc+list(k).length,0),cat=category(),s=selectedSeries(),st=stats(s||{});
   return pageHero('GLOBAL MACRO / ANALISI','Macro Lab. <em>Prima la lettura, poi i dati.</em>','Scegli un’economia: trovi il quadro in parole semplici, il grafico utile e, soltanto se vuoi, tutto l’archivio storico.')
    +'<div class="macro-studio-status"><span>◉ MACRO DYNAMICS · '+count+' SERIE STORICHE G8</span><span>FONTE REVISIONABILE · PERIODI INDIPENDENTI · NON POINT-IN-TIME</span></div>'
    +countryStrip()+countryHero()+macroResearch()
    +'<details class="macro-advanced" '+(state.msAdvanced?'open':'')+'><summary><span><strong>Vuoi andare più a fondo?</strong><small>Tabella storica, heatmap G8, confronto tra economie e definizioni: disponibili quando ti servono.</small></span><b>Apri gli approfondimenti ↗</b></summary><div class="macro-advanced-content">'
    +datedAudit()+heatUniverse()+relativePanel()+glossary()+'</div></details>'
    +'<section class="macro-endnote"><div><span class="chapter-kicker">DAL DATO AL MERCATO</span><h2>Macro → Pricing → Posizionamento → Prezzo.</h2><p>La narrativa macro è un’ipotesi. Diventa una tesi più solida soltanto quando cambiamento dei dati, aspettative monetarie e risposta del mercato sono coerenti.</p></div><a class="action-primary" href="#rates">Apri Rates & OIS <span>↗</span></a></section>'
    +'<p class="source-caption">Archivi: MACRO_SERIES.json (periodi, unità e serie storiche originali) e MACRO_THERMOMETER_DATA.json (percentili storici descrittivi). Nessun valore sintetico viene introdotto nel motore Core delle 28 coppie; mancano consenso puntuale e timestamp di rilascio per stimare le sorprese.</p>';
 }
 return render();
}
root.FXQuantMacro={render:build};
})(window);
