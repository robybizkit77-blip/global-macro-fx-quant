'use strict';
/**
 * FX Quant NEXT — Rates & Monetary Pricing Research Studio.
 * Read-only: official sovereign 2Y/10Y data and instrument-labelled future pricing.
 * No mixed-date curve lines, no fabricated OIS/term premium/market-implied probabilities.
 */
(function(root){
function make(api){
 const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow}=api;
 const TERMS=['3m','6m','12m'],PAIR_MODES=['2y','10y','slope','spread2y'];
 const dataR=c=>get('rates')?.[c],dataO=c=>get('ois')?.currencies?.[c],dataB=c=>get('cb')?.[c];
 const dateDiff=(a,b)=>validDay(a)&&validDay(b)?Math.abs((Date.parse(a+'T12:00:00Z')-Date.parse(b+'T12:00:00Z'))/864e5):null;
 const freshness=d=>{let days=dateDiff(d,dayNow());return days===null?'DATA ASSENTE':days>12?'STORICO':days>5?'DA VERIFICARE':'RECENTE';};
 function usable(c){
   const r=dataR(c);
   return r&&finite(r['2Y'])&&finite(r['10Y'])&&validDay(r.date)&&r.date<=dayNow()?r:null;
 }
 function sovereignRows(c){
   const r=usable(c);if(!r)return [];
   const a=r.history2,b=r.history10;
   if(!a?.dates?.length||!b?.dates?.length)return [];
   const m=new Map();
   (b.dates||[]).forEach((d,i)=>{const v=b.values?.[i];if(validDay(d)&&finite(v))m.set(d,v)});
   return a.dates.map((d,i)=>({date:d,y2:a.values?.[i],y10:m.get(d)}))
     .filter(x=>validDay(x.date)&&x.date<=r.date&&x.date<=dayNow()&&finite(x.y2)&&finite(x.y10))
     .sort((x,y)=>x.date.localeCompare(y.date));
 }
 function alignedRows(a,b){
   const ar=sovereignRows(a),br=sovereignRows(b);
   const bm=new Map(br.map(x=>[x.date,x]));
   return ar.filter(x=>bm.has(x.date)).map(x=>({date:x.date,a:x,b:bm.get(x.date)}));
 }
 function rpRate(c,k){
   const h=dataO(c)?.horizons?.[k];
   return h&&finite(h.rate)&&validDay(h.as_of)&&h.as_of<=dayNow()?h:null;
 }
 function cbRate(c){const z=dataB(c);return finite(z?.rate)?z.rate:null}
 function quality(c){let o=dataO(c);return o?(o.kind||'STRUMENTO NON DEFINITO')+' · '+(o.quality||'QUALITÀ NON DEFINITA'):'MERCATO NON VALIDATO'}
 function sameTenorDate(c){
   const vals=TERMS.map(k=>rpRate(c,k)?.as_of);
   return vals.every(validDay)&&new Set(vals).size===1;
 }
 function selectedReading(c){
   const r=usable(c),o=dataO(c),b=dataB(c),rows=sovereignRows(c),last=rows.at(-1),prev=rows.at(-2);
   const f2=last&&prev?(last.y2-prev.y2)*100:null;
   const f10=last&&prev?(last.y10-prev.y10)*100:null;
   const shape=finite(f2)&&finite(f10)?(f2<0&&f10<0?'bull':f2>0&&f10>0?'bear':'mixed'):'none';
   let movement='';
   if(shape==='bull')movement=f2<f10?'Bull steepening':'Bull flattening';
   else if(shape==='bear')movement=f2>f10?'Bear flattening':'Bear steepening';
   else movement='Movimenti non univoci';
   const policy=cbRate(c);
   const h6=rpRate(c,'6m');
   const d1=h6?.change_1d_bp,d7=h6?.change_1w_bp;
   const genuine=finite(d1)||finite(d7);
   const intro=!r?'Nessun rendimento verificabile alla data richiesta.':('L’ultimo 2Y '+c+' è '+fmt(r['2Y'],3)+'% e il 10Y '+fmt(r['10Y'],3)+'% (rilevazione '+date(r.date)+').');
   const desk=root.FXQuantRatesEconomic?.read?.({
     country:c,now:dayNow(),asof:last?.date,previous:prev?.date,bp2:f2,bp10:f10,
     kind:o?.kind,quality:o?.quality,h6
   })||{headline:'La curva va verificata prima di concludere.',
     meaning:'L’interpretazione economica non è disponibile; restano validi i dati datati sotto.',
     pricing:'Non attribuiamo un repricing senza una verifica temporale.',
     watch:'Esaminare le fonti originali prima di assumere una tesi.'};
   return {
     ...desk,intro,
     gov:finite(f2)&&finite(f10)?'Tra le ultime due date comuni dei rendimenti: 2Y '+sign(f2,1,' pb')+', 10Y '+sign(f10,1,' pb')+'; '+movement+'.':'Non bastano due date comuni per misurare il movimento della curva.',
     pricing:genuine?'Nel feed '+(o?.kind||'pricing')+' la scadenza 6M registra '+(finite(d1)?sign(d1,1,' pb in 1D'):'variazione 1D non disponibile')+' e '+(finite(d7)?sign(d7,1,' pb in 1W'):'variazione 1W non disponibile')+' (riferimento '+date(h6.as_of)+').'
       :'Per il 6M non ci sono variazioni 1D/1W validate: dai livelli delle scadenze non possiamo ricostruire un repricing avvenuto oggi.',
     caution:!sameTenorDate(c)?'I punti 3M, 6M e 12M riportano date diverse; non costituiscono una curva simultanea.':'Le tre scadenze hanno la stessa data, ma il tipo di strumento resta '+(o?.kind||'non specificato')+'.',
     monitor:'Per testare una tesi FX confronta uno spread coerente con l’altra valuta, OIS/futures comparabili e la conferma del prezzo. Il mercato dei governativi incorpora anche premi e rischi diversi.',
     policy:finite(policy)?fmt(policy,3)+'%':b?.rate_text||'—'
   };
 }
 function fxRelativeEvidence(c,other){
  const model=get('pairs'),universe=model?.pairs||{};
  const direct=c+other,reverse=other+c;
  const pair=universe[direct]?direct:universe[reverse]?reverse:null;
  const r=usable(c),peer=usable(other),o=dataO(c),h=rpRate(c,'6m');
  const asof=model?.price_asof;
  const pricing=h?'6M '+c+' · '+(o?.kind||'strumento non specificato')+
   ' · '+(o?.quality||'qualità da verificare')+' · '+date(h.as_of)+'. '+
   (finite(h.change_1d_bp)?'Variazione 1D '+sign(h.change_1d_bp,1,' pb')+'.':
   'Variazione 1D assente: non attribuiamo alcun repricing.') :
   '6M '+c+' non disponibile: non attribuiamo un repricing.';
  let status='unavailable',headline='Il confronto tra tassi e cambio non è ancora verificabile.';
  let observation='Occorrono rendimenti governativi 2Y e fixing BCE su date comuni, abbastanza recenti.';
  let proof='Rendimenti '+c+' '+date(r?.date)+' · '+other+' '+date(peer?.date)+
   ' · fixing del modello '+date(asof)+'.';
  if(pair&&root.FXQuantRatesBridge?.snapshot){
   const x=root.FXQuantRatesBridge.snapshot(
    get('rates'),get('currencyPrices'),pair,asof,dayNow(),
    get('audDailyResearch'),get('chfResearch'),get('nzdPostroll'));
   if(x?.ready&&x.short&&x.latest?.date){
    status='ready';
    const m=x.short,d=m.direction;
    headline=d==='STESSO SEGNO'?'Prezzo FX e spread 2Y si sono mossi nello stesso verso.':
     d==='SEGNO OPPOSTO'?'Prezzo FX e spread 2Y si sono mossi in versi opposti.':
     'La relazione tra prezzo FX e spread 2Y non è conclusiva.';
    observation='Fra '+date(m.start)+' e '+date(m.end)+
     ' ('+m.n+' intervalli, '+(m.n+1)+' date comuni): '+pair.slice(0,3)+'/'+pair.slice(3)+
     ' '+sign(m.fxPct,2,'%')+'; spread governativo 2Y ('+pair.slice(0,3)+
     ' − '+pair.slice(3)+') '+sign(m.spreadBp,1,' pb')+'.';
    proof='Dati allineati al '+date(x.latest.date)+'. '+
     (x.lag>0?'Il fixing più recente ('+date(asof)+') NON è stato abbinato a un tasso di un altro giorno. ':'')+
     (x.medium&&x.medium.direction!==d?'Sui 20 intervalli il segno cambia: persistenza da verificare. ':'')+
     x.kind+'.';
   }else if(x?.reason){observation=x.reason;}
  }
  const link=pair?'<button type="button" data-rates-openpair="'+esc(pair)+'" '+
   'aria-label="Apri '+esc(pair.slice(0,3)+'/'+pair.slice(3))+' nel dossier FX">'+
   'Apri '+esc(pair.slice(0,3)+'/'+pair.slice(3))+' <span aria-hidden="true">↗</span></button>':'';
  return '<section class="rates-fx-handoff rates-fx-'+status+'" data-fx-proof="'+status+
   '" data-fx-pair="'+esc(pair||'')+'" aria-label="Tassi e prezzo Forex su date comuni">'+
   '<div class="rates-fx-heading"><span class="chapter-kicker">DAL CALENDARIO AL FOREX · '+esc(c)+' VS '+esc(other)+'</span>'+
   '<h2>Il differenziale di tasso <em>trova conferma nel cambio?</em></h2></div>'+
   '<div class="rates-fx-content"><div class="rates-fx-story"><span class="micro-over">'+
   (status==='ready'?'PROVA OSSERVATA · DATE COMUNI':'PROVA NON DISPONIBILE')+'</span>'+
   '<h3>'+esc(headline)+'</h3><p>'+esc(observation)+'</p><small>'+esc(proof)+'</small></div>'+
   '<aside class="rates-fx-pricing"><span class="micro-over">ASPETTATIVE / 6M</span><p>'+esc(pricing)+
   '</p><small>I rendimenti 2Y sono governativi, NON OIS. Direzioni concordi o discordi non dimostrano causalità né indicano un trade.</small></aside></div>'+
   '<div class="rates-fx-actions">'+link+
   '<a href="#currencies">Confronta '+esc(c)+' nel G8 <span aria-hidden="true">↗</span></a>'+
   '<span>Coppia di ricerca, non segnale operativo</span></div></section>';
 }
 function govCard(c){
   const r=usable(c),row=sovereignRows(c),first=row[0],last=row.at(-1),prev=row.at(-2),f=selectedReading(c);
   const spread=last?(last.y10-last.y2)*100:null;
   return '<div class="rates-stats">'
      +[['Gov 2Y',r?fmt(r['2Y'],3)+'%':'—','Rif. '+date(r?.date)],
        ['Gov 10Y',r?fmt(r['10Y'],3)+'%':'—','Rif. '+date(r?.date)],
        ['10Y − 2Y',finite(spread)?sign(spread,1,' pb'):'—','Calcolo sulle date comuni'],
        ['Tasso ufficiale',f.policy,dataB(c)?.bank||'Banca centrale']].map(([a,b,d])=>
         '<div class="rates-stat"><span>'+esc(a)+'</span><strong>'+esc(b)+'</strong><small>'+esc(d)+'</small></div>').join('')+'</div>';
 }
 function countrySelect(){
   return '<div class="rates-country-strip" role="group" aria-label="Seleziona la valuta G8">'
      +FX.map(k=>{const r=usable(k),o=dataO(k);return '<button class="rates-country '+(k===state.ccy?'selected':'')+'" type="button" data-rate-ccy="'+k+'" aria-pressed="'+String(k===state.ccy)+'">'
        +'<span>'+FLAGS[k]+' '+k+'</span><strong>'+fmt(r?.['2Y'],2)+'%</strong><small>'+esc(freshness(r?.date))+' · '+date(r?.date)+'</small></button>'}).join('')+'</div>';
 }
 function govPlot(c){
   const rows=sovereignRows(c).slice(-Number(state.rsWindow||60)),mode=state.rsGovMode||'both';
   let lines=[];
   if(mode==='both'||mode==='2y')lines.push({name:'Government 2Y',color:'#9bd4ec',values:rows.map(x=>({label:x.date,value:x.y2}))});
   if(mode==='both'||mode==='10y')lines.push({name:'Government 10Y',color:'#f27b8c',values:rows.map(x=>({label:x.date,value:x.y10}))});
   if(mode==='slope')lines=[{name:'10Y − 2Y',color:'#e8c07c',values:rows.map(x=>({label:x.date,value:(x.y10-x.y2)*100}))}];
   return '<div class="rates-graph-head"><div><span class="micro-over">SOVEREIGN YIELD HISTORY / '+esc(c)+'</span><h3>'
     +(mode==='slope'?'Pendenza della curva 10Y–2Y':'Rendimenti governativi 2Y / 10Y')+'</h3></div><span class="data-date">'+rows.length+' date comuni</span></div>'
     +'<div class="rates-controls"><div class="pill-controls">'+[['both','2Y + 10Y'],['2y','Solo 2Y'],['10y','Solo 10Y'],['slope','Slope 10Y−2Y']].map(([k,l])=>
       '<button type="button" data-rs-gov="'+k+'" class="pill '+(mode===k?'active':'')+'" aria-pressed="'+String(mode===k)+'">'+l+'</button>').join('')+'</div>'
     +'<div class="pill-controls">'+[20,60,120,300].map(w=>'<button type="button" data-rs-window="'+w+'" class="pill '+(w===Number(state.rsWindow||60)?'active':'')+'" aria-pressed="'+String(w===Number(state.rsWindow||60))+'">'+w+' sedute</button>').join('')+'</div></div>'
     +plot({lines,unit:mode==='slope'?' pb':'%',precision:mode==='slope'?1:3,label:'Storico governativi '+c})
     +'<p class="rates-plot-note">Solo osservazioni con data comune fra 2Y e 10Y e non successive alla data valida della valuta. Finestra di osservazioni, non periodo temporale fisso.</p>';
 }
 function historicalSovereign(c){
   const rows=sovereignRows(c),last=rows.at(-1),prev=rows.at(-2);
   const bp2=prev&&last?(last.y2-prev.y2)*100:null,bp10=prev&&last?(last.y10-prev.y10)*100:null;
   const asof=last?.date;
   return '<div class="rates-qa-panel"><span class="micro-over">COSA STA CAMBIANDO</span><h3>Movimento della curva</h3>'
     +'<div class="rates-shift-row"><span>2Y · ultima rilevazione</span><b>'+sign(bp2,1,' pb')+'</b></div>'
     +'<div class="rates-shift-row"><span>10Y · ultima rilevazione</span><b>'+sign(bp10,1,' pb')+'</b></div>'
     +'<div class="rates-shift-row"><span>Data confronto</span><b>'+date(asof)+'</b></div>'
     +'<p>'+esc(selectedReading(c).gov)+'</p>'
     +'<p class="rates-warning">Il movimento della curva classifica ciò che è successo, non dimostra quale shock l’abbia causato.</p></div>';
 }
 function shapeBars(c){
   const o=dataO(c),terms=TERMS.map(k=>({k,h:rpRate(c,k)})),vals=terms.map(x=>x.h?.rate).filter(finite);
   if(!vals.length)return '<div class="empty"><strong>Pricing non disponibile</strong><p>Il feed non contiene scadenze datate utilizzabili.</p></div>';
   const min=Math.min(0,...vals),max=Math.max(...vals,0)+.4,span=max-min||1;
   const bars=terms.map((x,i)=>{
     const v=x.h?.rate,ratio=finite(v)?Math.max(0,Math.min(100,(v-min)/span*100)):0;
     const hat=x.h?'al '+date(x.h.as_of):'non disponibile';
     return '<div class="rates-shape-col"><div class="rates-shape-slot"><span class="rates-shape-bar" style="height:'+ratio+'%"></span></div><strong>'+fmt(v,3)+'%</strong><b>'+x.k.toUpperCase()+'</b><small>'+esc(hat)+'</small></div>';
   }).join('');
   const same=sameTenorDate(c);
   const quality=o?.quality||'Non classificato';
   return '<div class="rates-figure"><div class="rates-graph-head"><div><span class="micro-over">STRUMENTO · '+esc(o?.kind||'DA VERIFICARE')+'</span><h3>Livelli per tenore, non una curva OIS inventata</h3></div><span class="badge '+(same?'info':'warning')+'">'+(same?'DATE COMUNI':'DATE MISTE')+'</span></div>'
     +'<div class="rates-shape">'+bars+'</div>'
     +'<p class="rates-plot-note">'+esc(selectedReading(c).caution)+' Le barre rappresentano i valori pubblicati nel feed ('+esc(quality)+'), non una previsione certa del tasso ufficiale né una probabilità di decisione.</p></div>';
 }
 function oisAudit(c){
   const o=dataO(c),b=dataB(c);
   return '<div class="rates-instrument-card"><div class="rates-graph-head"><div><span class="micro-over">PERCORSO DI POLICY / FONTE</span><h3>'+esc(o?.kind||'Mercato da validare')+'</h3></div>'
     +'<span class="badge '+(/STIMA|PROXY/i.test(o?.quality||'')?'warning':'info')+'">'+esc(o?.quality||'NON VALIDATO')+'</span></div>'
     +'<p class="rates-smalltext">Tasso ufficiale '+esc(b?.bank||'CB')+': <strong>'+esc(b?.rate_text||'—')+'</strong> · Ultima decisione '+date(b?.last_date)
     +' · Prossima riunione '+date(b?.next_meeting)+'. Il tasso ufficiale e il pricing a termine non sono direttamente la stessa variabile.</p>'
     +'<div class="table-wrap"><table class="data-table rates-curve-table"><thead><tr><th>Tenore</th><th>Livello</th><th>Δ 1D</th><th>Δ 1W</th><th>Rif. / Contratto</th><th>Rilevazione</th></tr></thead><tbody>'
     +TERMS.map(k=>{let h=rpRate(c,k);return '<tr><td>'+k.toUpperCase()+'</td><td>'+fmt(h?.rate,3)+'%</td><td>'+sign(h?.change_1d_bp,1,' pb')+'</td><td>'+sign(h?.change_1w_bp,1,' pb')+'</td><td>'+esc(h?.contract||o?.kind||'—')+'</td><td>'+date(h?.as_of)+'</td></tr>'}).join('')+'</tbody></table></div>'
     +'<p class="rates-plot-note">'+esc(o?.source||'Fonte non disponibile')+' · Qualità: '+esc(o?.quality||'n.d.')+'. Le celle «—» indicano un repricing non disponibile, non una variazione nulla.</p></div>';
 }
 function repricing(c){
   const o=dataO(c),rows=TERMS.map(k=>({k,h:rpRate(c,k)}));
   const any=rows.some(x=>finite(x.h?.change_1d_bp)||finite(x.h?.change_1w_bp));
   const header='<div class="rates-graph-head"><div><span class="micro-over">MARKET REPRICING · '+c+'</span><h3>Quanto sono cambiate le aspettative?</h3></div><span class="badge '+(any?'info':'warning')+'">'+(any?'VARIAZIONI DATATE':'VARIAZIONI ASSENTI')+'</span></div>';
   if(!any)return '<div class="rates-reprice">'+header+'<div class="rates-missing">Questo feed contiene livelli dei tenori, ma <strong>non le variazioni storiche 1D/1W</strong>. Non deduciamo il repricing confrontando i livelli 3M e 12M: quel confronto descrive una forma a termine, non il cambiamento avvenuto oggi.</div></div>';
   return '<div class="rates-reprice">'+header+'<div class="rates-repricing-cards">'+rows.map(x=>
     '<div><span>'+x.k.toUpperCase()+' · '+date(x.h?.as_of)+'</span><strong>'+sign(x.h?.change_1d_bp,1,' pb')+'</strong><small>1 seduta</small>'
     +'<strong>'+sign(x.h?.change_1w_bp,1,' pb')+'</strong><small>1 settimana</small></div>').join('')+'</div>'
     +'<p class="rates-plot-note">Le variazioni sono riportate dal feed per ciascun contratto/scadenza. Verifica la qualità dello strumento prima di interpretarle come repricing della banca centrale.</p></div>';
 }
 function spread(c,other){
   const ar=alignedRows(c,other),window=Number(state.rsWindow||60),rows=ar.slice(-window),mode=state.rsDiffMode||'2y';
   const label=mode==='2y'?'Spread governativi 2Y ('+c+' − '+other+')':'Spread governativi 10Y ('+c+' − '+other+')';
   const value=x=>mode==='2y'?(x.a.y2-x.b.y2)*100:(x.a.y10-x.b.y10)*100;
   let current=rows.at(-1),prev=rows.at(-2),d=current?value(current):null,delta=prev&&current?value(current)-value(prev):null;
   const meta=usable(c)?.date===usable(other)?.date;
   return '<div class="rates-spread"><div class="rates-graph-head"><div><span class="micro-over">FX / CROSS-COUNTRY · DATI COMUNI</span><h3>'+esc(label)+'</h3></div>'
     +'<span class="badge '+(meta?'info':'warning')+'">'+(meta?'DATE DI SNAPSHOT UGUALI':'SNAPSHOT NON COINCIDENTI')+'</span></div>'
     +'<div class="rates-compare-controls"><div class="pill-controls">'+[['2y','Spread 2Y'],['10y','Spread 10Y']].map(([m,t])=>'<button type="button" data-rs-diff="'+m+'" aria-pressed="'+String(mode===m)+'" class="pill '+(mode===m?'active':'')+'">'+t+'</button>').join('')+'</div>'
     +'<strong>'+sign(d,1,' pb')+'</strong><span>'+date(current?.date)+' · '+rows.length+' date comuni</span></div>'
     +plot({lines:[{name:label,color:'#85d4d0',values:rows.map(x=>({label:x.date,value:value(x)}))}],unit:' pb',precision:1,label})
     +'<p class="rates-plot-note">Variazione dello spread sull’ultima data comune: '+sign(delta,1,' pb')+'. Il grafico usa esclusivamente osservazioni esistenti in entrambe le serie. '+(meta?'Le date degli snapshot correnti coincidono.':'I latest snapshot non sono simultanei: l’ultima osservazione comune potrebbe essere precedente.')+' Uno spread sovrano non è uno spread OIS né un segnale FX.</p></div>';
 }
 function countryControls(){
   return '<div class="rates-compare-select"><label>PAESE PRINCIPALE<select id="rs-country" class="select">'
      +FX.map(k=>'<option value="'+k+'" '+(state.ccy===k?'selected':'')+'>'+FLAGS[k]+' '+k+' · '+NAMES[k]+'</option>').join('')+'</select></label>'
      +'<label>CONFRONTA CON<select id="rs-other" class="select">'
      +FX.filter(k=>k!==state.ccy).map(k=>'<option value="'+k+'" '+(state.against===k?'selected':'')+'>'+FLAGS[k]+' '+k+' · '+NAMES[k]+'</option>').join('')+'</select></label></div>';
 }
 function tableUniverse(){
   return '<section class="rates-universe"><div class="rates-section-head"><div><span class="chapter-kicker">05 / G8 RESEARCH MONITOR</span><h2>Otto valute. <em>Otto fonti da contestualizzare.</em></h2></div><p>Filtra cliccando una valuta. Tutti i valori conservano data e qualità; gli strumenti monetari non sono automaticamente intercambiabili.</p></div>'
     +'<div class="table-wrap"><table class="data-table rates-universe-table"><thead><tr><th>Valuta</th><th>Gov 2Y</th><th>Gov 10Y</th><th>10Y−2Y</th><th>Data GOV</th><th>Pricing 3M</th><th>6M</th><th>12M</th><th>Tipo e qualità</th></tr></thead><tbody>'
     +FX.map(k=>{const r=usable(k),o=dataO(k),z=sovereignRows(k).at(-1);
      return '<tr class="'+(k===state.ccy?'active':'')+'"><td><button type="button" data-rate-ccy="'+k+'">'+FLAGS[k]+' '+k+'</button></td><td>'+fmt(r?.['2Y'],3)+'%</td>'
       +'<td>'+fmt(r?.['10Y'],3)+'%</td><td>'+sign(z?(z.y10-z.y2)*100:null,1,' pb')+'</td><td>'+date(r?.date)+'</td>'
       +TERMS.map(t=>{const h=rpRate(k,t);return '<td><span class="rates-cell">'+fmt(h?.rate,3)+'%<small>'+date(h?.as_of)+'</small></span></td>'}).join('')
       +'<td>'+esc(o?.kind||'—')+'<small>'+esc(o?.quality||'n.d.')+'</small></td></tr>';
     }).join('')+'</tbody></table></div>'
     +'<p class="rates-plot-note">Differenze nei benchmark dei governativi e nei contratti futures. Le cifre 3M/6M/12M non costituiscono una curva OIS comune a tutto il G8. Le righe CHF/NZD possono conservare storici governativi molto più vecchi.</p></section>';
 }
 function explanations(c){
   const r=selectedReading(c);
   const cards=[
     ['01','FATTO OSSERVATO','Cosa è successo?',r.intro+' '+r.gov],
     ['02','PRICING','Cosa ha davvero repricizzato?',r.pricing+' '+r.caution],
     ['03','INTERPRETAZIONE','Come leggere il 2Y rispetto al 10Y?','Il 2Y riflette prevalentemente aspettative di tassi a breve e premi. Il 10Y risente anche di crescita, aspettative d’inflazione, rendimenti reali, term premium, deficit/supply e domanda di duration. Non confondere una classificazione di curva con una causa dimostrata.'],
     ['04','TESI FALSIFICABILE','Cosa confermerebbe o smentirebbe?',r.monitor]
   ];
   return '<section class="rates-explanations"><div class="rates-section-head"><div><span class="chapter-kicker">04 / INTERPRETAZIONE</span><h2>Il numero è un punto di partenza. <em>Non una conclusione.</em></h2></div><p>Una lettura macro professionale richiede osservazione, pricing, spiegazione e condizioni di verifica.</p></div>'
      +'<div class="rates-explain-grid">'+cards.map(([n,l,h,p])=>'<article><span class="rates-index">'+n+'</span><span class="micro-over">'+l+'</span><h3>'+h+'</h3><p>'+esc(p)+'</p></article>').join('')+'</div></section>';
 }
 function glossary(){
   const rows=[
      ['Rendimento governativo 2Y','Rendimento del benchmark sovrano a due anni. È sensibile alle aspettative di policy, ma non coincide con la curva OIS.'],
      ['Rendimento governativo 10Y','È influenzato dal percorso dei tassi, crescita, inflazione, rendimenti reali, term premium, rischio sovrano e domanda di duration.'],
      ['10Y − 2Y (slope)','Pendenza della curva in punti base. Positiva significa 10Y sopra 2Y; negativa significa curva invertita.'],
      ['Bull / Bear steepening e flattening','Bull: rendimenti in discesa; Bear: in salita. Steepening: 10Y − 2Y aumenta; Flattening: diminuisce. Movimenti misti vanno descritti senza forzature.'],
      ['OIS','Overnight Indexed Swap: contratto su aspettative del tasso overnight di riferimento. Non equivale a un rendimento governativo.'],
      ['Futures monetari','Contratti con sottostante, scadenze e convenzioni proprie. Possono aiutare a stimare policy pricing ma non sono automaticamente OIS.'],
      ['Proxy e stime','Livelli indicativi derivati da uno strumento secondario. Utili per contesto, non trattabili come curve ufficiali certificate.'],
      ['Repricing 1D / 1W','Variazione dello stesso tenore/instrumento fra due date. La differenza fra 3M e 12M è struttura a termine, non repricing temporale.'],
      ['Differenziale 2Y FX','Sottrazione di due rendimenti sovrani con date comuni. È un indicatore relativo, non un rendimento carry replicabile né uno spread OIS.']
   ];
   return '<section class="rates-glossary"><div class="rates-section-head"><div><span class="chapter-kicker">06 / GUIDA E METODO</span><h2>Tassi e OIS, <em>senza ambiguità.</em></h2></div><p>Le definizioni restano consultabili mentre lavori, senza interrompere il flusso dell’analisi.</p></div>'
    +'<div class="rates-definitions">'+rows.map(([k,v])=>'<details><summary>'+esc(k)+'<span>＋</span></summary><p>'+esc(v)+'</p></details>').join('')+'</div></section>';
 }
 function render(){
   const c=state.ccy,other=FX.includes(state.against)&&state.against!==c?state.against:FX.find(k=>k!==c);
   const r=usable(c),o=dataO(c),cb=dataB(c),m=selectedReading(c),dates=TERMS.map(k=>rpRate(c,k)?.as_of).filter(validDay);
   return pageHero('GLOBAL RATES / RESEARCH STUDIO','Il mercato dei tassi, <em>spiegato e misurato.</em>','Front-end, long-end, curve, market pricing e differenziali FX. Un laboratorio G8 che separa i rendimenti osservati dalle aspettative ufficiali, futures e stime.')
    +'<div class="rates-status"><span>◉ RATES & POLICY LAB · '+FLAGS[c]+' '+c+'</span><span>GOV '+date(r?.date)+' · PRICING '+date(o?.as_of)+' · '+esc(o?.kind||'strumento da verificare')+'</span></div>'
    +countrySelect()
    +'<section class="rates-hero"><div class="rates-hero-title"><span class="chapter-kicker">01 / '+FLAGS[c]+' '+esc(NAMES[c])+' · FRONT-END VS LONG-END</span>'
    +'<h2>'+esc(m.headline)+'</h2>'
    +'<p class="rates-economic-observation"><strong>Cosa vediamo.</strong> '+esc(m.meaning)+'</p>'
    +'<p class="rates-economic-pricing"><strong>Cosa è prezzato.</strong> '+esc(m.pricingEvidence)+'</p>'
    +'<p class="rates-economic-watch"><strong>Cosa monitorare.</strong> '+esc(m.watch)+'</p>'
    +'<div class="rates-chipline"><span class="badge '+(freshness(r?.date)==='STORICO'?'warning':'info')+'">'+esc(freshness(r?.date))+'</span><span>'+esc(r?.quality||'QUALITÀ DA VERIFICARE')+'</span></div></div>'
    +'<div class="rates-hero-side"><div class="rates-hero-orbit"><span>CURVE SLOPE</span><strong>'+sign(r?(r['10Y']-r['2Y'])*100:null,1)+'</strong><small>punti base · '+date(r?.date)+'</small></div></div></section>'
    +govCard(c)
    +fxRelativeEvidence(c,other)
    +'<section class="rates-chapter"><div class="rates-section-head"><div><span class="chapter-kicker">02 / SOVEREIGN CURVE LAB</span><h2>Quali scadenze <em>stanno cambiando?</em></h2></div><p>Ogni grafico nasce dalle osservazioni 2Y e 10Y comuni. Cambia periodo e misura la pendenza, senza confondere la forma con il driver economico.</p></div>'
    +'<div class="rates-research-grid"><div class="rates-primary-plot">'+govPlot(c)+'</div>'+historicalSovereign(c)+'</div></section>'
    +'<section class="rates-chapter"><div class="rates-section-head"><div><span class="chapter-kicker">03 / CENTRAL BANK PRICING</span><h2>Le aspettative non sono <em>il tasso ufficiale.</em></h2></div><p>Confronta i livelli 3M, 6M e 12M senza mescolare OIS e futures. Guarda quali scadenze hanno una variazione 1D/1W verificabile.</p></div>'
    +'<div class="rates-pricing-grid">'+shapeBars(c)+oisAudit(c)+'</div>'+repricing(c)+'</section>'
    +'<section class="rates-chapter"><div class="rates-section-head"><div><span class="chapter-kicker">03B / FX RELATIVE RATES</span><h2>Due economie. <em>Un differenziale da verificare.</em></h2></div><p>Confronta governativi coerenti per data. La direzione dello spread è contesto FX, non la prova di un futuro movimento del cambio.</p></div>'
    +countryControls()+spread(c,other)+'</section>'
    +explanations(c)+tableUniverse()+glossary()
    +'<div class="rates-end-note"><div><span class="chapter-kicker">DALLA RICERCA ALLA TESI FX</span><h2>Macro → Pricing → Positioning → Prezzo.</h2><p>La divergenza tra front-end, OIS/futures e prezzo è un problema da investigare. Non trasformiamo automaticamente ogni variazione di yield in un trade.</p></div><a href="#pairs" class="action-primary">Vai alle coppie FX <span>↗</span></a></div>'
    +'<p class="source-caption">Rendimenti governativi: NATIVE_RATES_DATA; Policy rate: NATIVE_CB_DATA; pricing per tenore: ois-pricing-snapshot.json. Data e qualità possono differire. Nessun dato da questo laboratorio modifica il motore operativo FX.</p>';
 }
 return render();
}
root.FXQuantRates={render:make};
})(window);
