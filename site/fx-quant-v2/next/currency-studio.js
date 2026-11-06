'use strict';
/**
 * FX Quant Next — G8 Country Deep Dive.
 * Source-based research, not an automated FX trade signal.
 *
 * ECB rates: one EUR buys row[ccy] units of currency. A/B = row[B]/row[A].
 * Yield differentials: match 2Y observations on identical session dates.
 * CFTC positioning: dated Tuesday report; futures size differs by contract.
 * Monetary pricing: preserve tenor's instrument, date and quality.
 */
(function(root){
function make(api){
 const {get,FX,FLAGS,NAMES,state,plot,pageHero,esc,fmt,sign,date,finite,validDay,dayNow}=api;
 const c=FX.includes(state.ccy)?state.ccy:'USD';
 const other=FX.includes(state.csOther)&&state.csOther!==c?state.csOther:FX.find(k=>k!==c);
 const RATES=get('rates')||{},CB=get('cb')||{},MACRO=get('macro')?.currencies||{};
 const OIS=get('ois')?.currencies||{},COT=get('cotHistory')||{},PAIR=get('pairs')?.pairs||{};
 const PRICES=get('currencyPrices'),SERIES=get('macroSeries')||{};
 const opts={escape:esc,fmt,sign,date};
 const safeDay=d=>validDay(d)&&d<=dayNow();
 const q=(k)=>{const r=RATES[k];return r&&safeDay(r.date)&&finite(r['2Y'])&&finite(r['10Y'])?r:null;};
 function forexRows(a,b){
  if(!PRICES||!Array.isArray(PRICES.rows)||PRICES.source!=='ECB euro foreign exchange reference rates')return [];
  return PRICES.rows.filter(x=>safeDay(x.Date)&&finite(x[a])&&finite(x[b])&&x[a]>0&&x[b]>0)
   .map(x=>({label:x.Date,value:x[b]/x[a]}))
   .sort((x,y)=>x.label.localeCompare(y.label));
 }
 function ret(rows,n){
  if(rows.length<=n||!finite(rows.at(-1)?.value)||!finite(rows.at(-n-1)?.value)||!rows.at(-n-1).value)return null;
  return (rows.at(-1).value/rows.at(-n-1).value-1)*100;
 }
 const rows=forexRows(c,other),latest=rows.at(-1),rateA=q(c),rateB=q(other);
 const govHistory=k=>{
   const r=q(k);if(!r||!r.history2?.dates||!r.history10?.dates)return [];
   const m=new Map(r.history10.dates.map((d,i)=>[d,r.history10.values?.[i]]));
   return r.history2.dates.map((d,i)=>({label:d,v2:r.history2.values?.[i],v10:m.get(d)}))
    .filter(x=>safeDay(x.label)&&x.label<=r.date&&finite(x.v2)&&finite(x.v10))
    .sort((a,b)=>a.label.localeCompare(b.label));
 };
 const spreadRows=(a,b)=>{
   const br=new Map(govHistory(b).map(x=>[x.label,x.v2]));
   return govHistory(a).filter(x=>finite(br.get(x.label))).map(x=>({label:x.label,value:(x.v2-br.get(x.label))*100}));
 };
 const bondDiff=spreadRows(c,other),bondLast=bondDiff.at(-1),bondPrev=bondDiff.at(-2);
 const f2=q(c)?.chg2_bp;
 const ois=o=>OIS[o],cot=o=>COT[o],macro=o=>MACRO[o];
 function qualify(priceDate,rateDate){
   if(!safeDay(priceDate)||!safeDay(rateDate))return 'Date non disponibili';
   return priceDate===rateDate?'Stessa data del fixing':'Date differenti: non conferma simultanea';
 }
 const percDay=(v)=>typeof v==='string'&&/^\d{4}-\d{2}$/.test(v)?v:v||'n.d.';
 const describePolicy=k=>{
   const a=CB[k],r=q(k),p=OIS[k];
   return {
    bank:a?.bank||k,rate:a?.rate_text||'—',action:a?.action||'Decisione non registrata',
    stance:a?.stance||'Da verificare',meeting:a?.next_meeting||'n.d.',
    date:a?.last_date||'n.d.',pName:p?.kind||'Strumento non indicato',
    pQuality:p?.quality||'NON CLASSIFICATO',rDate:r?.date||'',r2:r?.['2Y'],
    r10:r?.['10Y'],source:p?.source||'n.d.'
   };
 };
 const policy=describePolicy(c);
 function dataStatus(k){
   const dates=[q(k)?.date,macro(k)?.inflation?.as_of,cot(k)?.dates?.at(-1),ois(k)?.horizons?.['6m']?.as_of];
   return dates.map(d=>String(d||'—')).join(' · ');
 }
 function countrySelector(){
   return '<div class="currency-studio-selector" role="group" aria-label="Valuta del dossier">'+FX.map(k=>{
     const r=q(k),mc=macro(k)?.inflation?.latest_value,ct=cot(k),p=ct?.percentile?.at(-1);
     return '<button type="button" data-cs-country="'+k+'" aria-pressed="'+String(c===k)+'" class="cs-country '+(c===k?'active':'')+'">'
      +'<span>'+FLAGS[k]+' '+k+'</span><strong>'+fmt(r?.['2Y'],2)+'%</strong><small>2Y · '+date(r?.date)+'</small>'
      +'<i>CPI '+fmt(mc,1)+'% · COT P'+fmt(p,0)+'</i></button>';
   }).join('')+'</div>';
 }
 function economicText(){
   const m=macro(c),inF=m?.inflation,lab=m?.labour,r=q(c),p=ois(c);
   const x=finite(inF?.latest_value)?'inflazione '+fmt(inF.latest_value,2)+'% ('+percDay(inF.as_of)+')':'inflazione non validata';
   const y=finite(lab?.latest_value)?'disoccupazione '+fmt(lab.latest_value,2)+'% ('+percDay(lab.as_of)+')':'lavoro da verificare';
   return 'Per '+NAMES[c]+' i dati disponibili mostrano '+x+' e '+y+
    '. Il 2Y governativo è '+(r?fmt(r['2Y'],3)+'% al '+date(r.date):'non aggiornato con data affidabile')+
    '. Questo quadro non dimostra, da solo, un vantaggio del '+c+' sul mercato Forex.';
 }
 function hero(){
   return '<section class="cs-hero"><div class="cs-hero-narrative"><span class="chapter-kicker">01 / '+FLAGS[c]+' '+esc(NAMES[c]).toUpperCase()+' · COUNTRY INTELLIGENCE</span>'
    +'<h2>Una valuta.<br><em>Cinque prove da mettere insieme.</em></h2><p>'+esc(economicText())+'</p>'
    +'<div class="cs-hero-actions"><a href="#macro" class="action-minimal">Macro Lab ↗</a><a href="#rates" class="action-minimal">Rates & OIS ↗</a><a href="#cot" class="action-minimal">COT Research ↗</a></div></div>'
    +'<div class="cs-hero-fx"><span class="micro-over">PREZZO / BCE FIXING</span><strong>'+esc(c)+'/'+esc(other)+'</strong><b>'+fmt(latest?.value,5)+'</b>'
    +'<small>1 '+c+' = '+other+' · '+date(latest?.label)+'</small><div class="cs-hero-return"><span>20 sedute</span><strong>'+sign(ret(rows,20),2,'%')+'</strong></div>'
    +'<p>Quotazione ricostruita dalla tabella BCE, non spot intraday.</p></div></section>';
 }
 function chooseCounterparty(){
   return '<div class="cs-compare-line"><div><span class="micro-over">CONTROVALUTA DA INVESTIGARE</span><h3>'+FLAGS[c]+' '+c+' / '+FLAGS[other]+' '+other+'</h3></div>'
     +'<label>Confronta con <select class="select" id="cs-other">'+FX.filter(k=>k!==c).map(k=>'<option value="'+k+'" '+(k===other?'selected':'')+'>'+FLAGS[k]+' '+k+' — '+NAMES[k]+'</option>').join('')+'</select></label></div>';
 }
 function strip(){
   const cotA=cot(c),lastC=cotA?.dates?.at(-1);
   const products=[
     ['Rendimento 2Y',finite(rateA?.['2Y'])?fmt(rateA['2Y'],3)+'%':'—',date(rateA?.date),'#rates'],
     ['Variazione 2Y',sign(f2,1,' pb'),date(rateA?.date),'#rates'],
     ['Inflazione',fmt(macro(c)?.inflation?.latest_value,2)+'%',percDay(macro(c)?.inflation?.as_of),'#macro'],
     ['COT percentile','P'+fmt(cotA?.percentile?.at(-1),1),date(lastC),'#cot'],
     ['Prezzo '+c+'/'+other,fmt(latest?.value,4),date(latest?.label),'#pairs']
   ];
   return '<div class="cs-factstrip">'+products.map(([a,b,d,l])=>'<a href="'+l+'"><span>'+esc(a)+'</span><strong>'+esc(b)+'</strong><small>'+esc(d)+'</small></a>').join('')+'</div>';
 }
 function section(head,title,sub){
   return '<div class="cs-section-heading"><div><span class="chapter-kicker">'+esc(head)+'</span><h2>'+title+'</h2></div><p>'+esc(sub)+'</p></div>';
 }
 function priceGraph(){
   const w=Number(state.csPriceWindow||60),p=rows.slice(-w),asof=latest?.label;
   const windows=[20,60,120,300,560],r1=ret(rows,5),r20=ret(rows,20),r60=ret(rows,60);
   return '<div class="cs-chart-head"><div><span class="micro-over">FX / BCE DAILY FIXING · QUOTAZIONE '+esc(c)+'/'+esc(other)+'</span><h3>Il prezzo conferma il contesto?</h3></div><span class="data-date">Al '+date(asof)+'</span></div>'
     +'<div class="cs-chart-controls"><div class="pill-controls">'+windows.map(n=>'<button type="button" data-cs-pricewindow="'+n+'" class="pill '+(w===n?'active':'')+'" aria-pressed="'+String(w===n)+'">'+(n===560?'Tutto':n+' sedute')+'</button>').join('')+'</div>'
     +'<span class="cs-chart-quality">Fonte BCE · Non intraday</span></div>'
     +plot({lines:[{name:c+'/'+other,color:'#88d8c3',values:p}],precision:5,label:'ECB fixing '+c+'/'+other})
     +'<div class="cs-return-strip">'+[['5 sedute',r1],['20 sedute',r20],['60 sedute',r60]].map(([k,x])=>'<div><span>'+k+'</span><strong class="'+(finite(x)&&x<0?'cs-negative':'')+'">'+sign(x,2,'%')+'</strong></div>').join('')+'</div>'
     +'<p class="cs-caveat">Questa serie è calcolata dai fixing EUR BCE: A/B = unità B per un’unità A. Un valore crescente significa apprezzamento di '+c+' rispetto a '+other+'. La variazione indica performance passata, non una previsione né un prezzo tradabile in tempo reale.</p>';
 }
 function ratesGraph(){
   const mode=state.csRatesMode||'spread',w=Number(state.csRatesWindow||60),h=govHistory(c);
   const spread=bondDiff.slice(-w);
   const lines=mode==='spread'?[{name:c+' − '+other+' (2Y)',color:'#f0c07a',values:spread}]
     :[{name:c+' Gov 2Y',color:'#9fcfe7',values:h.slice(-w).map(x=>({label:x.label,value:x.v2}))},
       {name:c+' Gov 10Y',color:'#ec7887',values:h.slice(-w).map(x=>({label:x.label,value:x.v10}))}];
   const lastDate=mode==='spread'?spread.at(-1)?.label:h.at(-1)?.label;
   return '<div class="cs-chart-head"><div><span class="micro-over">SOVEREIGN RATES · BENCHMARK</span><h3>'+(mode==='spread'?'Differenziale 2Y su date comuni':'Rendimenti '+c+' a 2Y e 10Y')+'</h3></div><span class="data-date">'+date(lastDate)+'</span></div>'
    +'<div class="cs-chart-controls"><div class="pill-controls">'+[['spread','Spread 2Y'],['curve','Curva 2Y / 10Y']].map(([v,n])=>
       '<button type="button" data-cs-ratesmode="'+v+'" aria-pressed="'+String(mode===v)+'" class="pill '+(v===mode?'active':'')+'">'+n+'</button>').join('')+'</div>'
    +'<div class="pill-controls">'+[20,60,120].map(n=>'<button type="button" data-cs-rateswindow="'+n+'" aria-pressed="'+String(w===n)+'" class="pill '+(w===n?'active':'')+'">'+n+'</button>').join('')+'</div></div>'
    +plot({lines,unit:mode==='spread'?' pb':'%',precision:mode==='spread'?1:3,label:mode==='spread'?'Differenziale '+c+' '+other:'Governativi '+c})
    +'<p class="cs-caveat">'+(mode==='spread'?'Spread sovrano 2Y calcolato soltanto sulle date comuni a '+c+' e '+other+'. Ultimo valore: '+sign(bondLast?.value,1,' pb')+' al '+date(bondLast?.label)+'. Non equivale a uno spread OIS né è un segnale FX.':'Rendimenti governativi da fonti nazionali, non tassi OIS. Il long-end incorpora fattori diversi dalla sola banca centrale.')+'</p>';
 }
 function marketCharts(){
   return section('02 / PREZZO & DIFFERENZIALI','Il mercato <em>conferma o smentisce?</em>','Due grafici distinti per non mescolare unità e timing. Il prezzo FX e i rendimenti possono reagire a driver differenti.')
     +'<div class="cs-two-charts"><div class="cs-chart-panel">'+priceGraph()+'</div><div class="cs-chart-panel">'+ratesGraph()+'</div></div>';
 }
 function macroSeries(k){
   const records=Array.isArray(SERIES[c])?SERIES[c]:[];
   const matched=records.filter(s=>s.category===k&&Array.isArray(s.values)&&Array.isArray(s.dates)&&s.values.length===s.dates.length);
   return k==='Inflazione'?(matched.find(x=>/headline/i.test(x.label))||matched[0])
    :(matched.find(x=>/Disoccupazione/i.test(x.label))||matched[0]);
 }
 function macroCard(){
   const m=macro(c),choices=['inflation','labour'],key=state.csMacroMode==='labour'?'labour':'inflation',one=m?.[key];
   const series=macroSeries(key==='inflation'?'Inflazione':'Lavoro'),u=String(series?.unit||'metadato unità assente');
   const points=(series?.dates||[]).map((x,i)=>({label:x,value:series.values?.[i]})).filter(x=>finite(x.value)&&String(x.label).slice(0,7)<=dayNow().slice(0,7)).slice(-Number(state.csMacroWindow||36));
   const metric=key==='inflation'?'Inflazione':'Disoccupazione';
   return '<div class="cs-panel-head"><div><span class="micro-over">MACRO / LIVELLO E DINAMICA</span><h3>'+esc(metric)+' · '+FLAGS[c]+' '+c+'</h3></div><a href="#macro" class="action-minimal">Macro Lab ↗</a></div>'
    +'<div class="cs-macro-stats">'+['inflation','labour'].map(x=>{const z=m?.[x];return '<button type="button" data-cs-macro="'+x+'" class="'+(x===key?'active':'')+'" aria-pressed="'+String(x===key)+'"><span>'+esc(x==='inflation'?'Inflazione':'Disoccupazione')+'</span><strong>'+fmt(z?.latest_value,2)+'%</strong><small>'+esc(z?.direction||'—')+' · '+esc(z?.acceleration||'—')+' · '+esc(z?.as_of||'n.d.')+'</small></button>'}).join('')+'</div>'
    +'<div class="cs-chart-controls"><span class="micro-over">'+esc(series?.label||'Storico da verificare')+' · '+esc(series?.frequency||'M')+'</span><div class="pill-controls">'+[12,36,84].map(n=>'<button type="button" data-cs-macrowindow="'+n+'" class="pill '+(n===Number(state.csMacroWindow||36)?'active':'')+'">'+n+' obs.</button>').join('')+'</div></div>'
    +plot({lines:[{name:series?.label||metric,color:key==='inflation'?'#ecb77b':'#94c4e5',values:points}],precision:2,label:'Storico fonte '+metric})
    +'<p class="cs-caveat">Il termometro sopra è in percentuale e si riferisce al periodo '+esc(one?.as_of||'n.d.')+'. Il grafico sottostante conserva l’unità originale della serie '+esc(series?.label||'')+' ('+esc(u)+') e non è necessariamente la stessa trasformazione YoY. Non attribuiamo date di pubblicazione agli intervalli storici.</p>';
 }
 function cotPanel(){
   const x=cot(c),last=x?.dates?.length-1,prev=last>=1?x.net[last-1]:null;
   const current=last>=0?x.net[last]:null,pct=last>=0?x.percentile[last]:null;
   const delta=finite(current)&&finite(prev)?current-prev:null,netoi=last>=0?x.netoi[last]:null;
   const rows=last>=0?x.dates.map((d,i)=>({label:d,value:x.net[i]})).slice(-Number(state.csCotWindow||26)):[];
   const position=current>0?'net long':current<0?'net short':'non verificata';
   return '<div class="cs-panel-head"><div><span class="micro-over">CFTC / NON-COMMERCIAL</span><h3>Posizionamento '+FLAGS[c]+' '+c+'</h3></div><a href="#cot" class="action-minimal">COT Studio ↗</a></div>'
    +'<div class="cs-position-head"><div><span>NET</span><strong>'+sign(current,0)+'</strong><small>'+esc(position)+' · '+date(x?.dates?.[last])+'</small></div>'
    +'<div><span>Δ 1 SETTIMANA</span><strong>'+sign(delta,0)+'</strong><small>Contratti, non performance FX</small></div>'
    +'<div><span>PERCENTILE 104W</span><strong>P'+fmt(pct,1)+'</strong><small>Net/OI '+sign(netoi,1,'%')+'</small></div></div>'
    +'<div class="cs-chart-controls"><span class="micro-over">104 SETTIMANE DI STORICO</span><div class="pill-controls">'+[13,26,52,104].map(n=>'<button type="button" data-cs-cotwindow="'+n+'" class="pill '+(n===Number(state.csCotWindow||26)?'active':'')+'">'+n+'W</button>').join('')+'</div></div>'
    +plot({lines:[{name:'Net long − short',color:'#a3d4bd',values:rows}],precision:0,label:'COT weekly net '+c})
    +'<p class="cs-caveat">Ultimo CFTC: '+date(x?.dates?.[last])+'. Percentile elevato = posizione alta rispetto alla storia, non necessariamente net long. Il COT USD usa contratti su dollar index: non è direttamente confrontabile come ammontare con i futures delle altre sette valute.</p>';
 }
 function evidencePanel(){
   return section('03 / MACRO & POSITIONING','Il cambiamento <em>dietro al prezzo.</em>','Inflazione, lavoro e futures CFTC mostrano prospettive differenti. Frequenze e periodi sono indicati, senza combinarli in un punteggio arbitrario.')
    +'<div class="cs-evidence-grid"><section class="cs-chart-panel">'+macroCard()+'</section><section class="cs-chart-panel">'+cotPanel()+'</section></div>';
 }
 function cbTable(){
   const z=OIS[c],b=CB[c],rows=['3m','6m','12m'];
   return '<div class="cs-policy-box"><div class="cs-panel-head"><div><span class="micro-over">CENTRAL BANK / POLICY DECISION</span><h3>'+esc(policy.bank)+' · tasso ufficiale '+esc(policy.rate)+'</h3></div><a href="#rates" class="action-minimal">Rates Studio ↗</a></div>'
     +'<p>'+esc(policy.action)+' · '+esc(policy.stance)+'. Ultima decisione '+date(policy.date)+'. Prossima riunione: '+date(policy.meeting)+'.</p>'
     +'<div class="cs-policy-status"><span>Strumento: '+esc(policy.pName)+'</span><strong>'+esc(policy.pQuality)+'</strong></div>'
     +'<div class="table-wrap"><table class="data-table cs-tenor-table"><thead><tr><th>Tenore</th><th>Livello</th><th>1D</th><th>1W</th><th>Contratto</th><th>Rilevazione</th></tr></thead><tbody>'
     +rows.map(k=>{const t=z?.horizons?.[k];return '<tr><td>'+k.toUpperCase()+'</td><td>'+fmt(t?.rate,3)+'%</td><td>'+sign(t?.change_1d_bp,1,' pb')+'</td><td>'+sign(t?.change_1w_bp,1,' pb')+'</td><td>'+esc(t?.contract||'n.d.')+'</td><td>'+date(t?.as_of)+'</td></tr>'}).join('')+'</tbody></table></div>'
     +'<p class="cs-caveat">I livelli OIS/futures/proxy sono informativi e non costituiscono automaticamente probabilità delle decisioni. '+esc(policy.pName)+' · '+esc(policy.source)+'. Controlla la data di ogni singolo tenore: le scadenze possono non essere simultanee.</p></div>';
 }
 function crossTable(){
   const vals=FX.filter(k=>k!==c).map(k=>{
     const h=forexRows(c,k),rate=spreadRows(c,k).at(-1);
     return {k,p:h.at(-1),d5:ret(h,5),d20:ret(h,20),d60:ret(h,60),spread:rate?.value,spreadDate:rate?.label};
   });
   const sort=state.csSort||'currency';
   vals.sort((a,b)=>sort==='d20'?(finite(b.d20)?b.d20:-Infinity)-(finite(a.d20)?a.d20:-Infinity):sort==='yield'?(finite(b.spread)?b.spread:-Infinity)-(finite(a.spread)?a.spread:-Infinity):a.k.localeCompare(b.k));
   return section('05 / 7 VALUTE RELATIVE','Sette confronti. <em>Nessun ranking inventato.</em>','Il prezzo è ricostruito dai fixing BCE; lo spread è fra governativi 2Y su date comuni. Non sono classifiche di forza macro o segnali di acquisto.')
    +'<div class="cs-cross-table"><div class="cs-chart-controls"><span class="micro-over">'+FLAGS[c]+' '+c+' CONTRO LE ALTRE G8</span><div class="pill-controls">'
    +[['currency','Valuta'],['d20','Variazione 20S'],['yield','Spread 2Y']].map(([v,l])=>'<button type="button" data-cs-sort="'+v+'" class="pill '+(sort===v?'active':'')+'" aria-pressed="'+String(v===sort)+'">'+l+'</button>').join('')+'</div></div>'
    +'<div class="table-wrap"><table class="data-table cs-pair-table"><thead><tr><th>Coppia</th><th>Fixing BCE</th><th>5 sedute</th><th>20 sedute</th><th>60 sedute</th><th>Gov spread 2Y</th><th>Data spread</th><th>Esplora</th></tr></thead><tbody>'
    +vals.map(x=>'<tr class="'+(x.k===other?'active':'')+'"><td><button data-cs-other="'+x.k+'" type="button">'+c+'/'+x.k+'</button></td><td>'+fmt(x.p?.value,5)+'</td><td>'+sign(x.d5,2,'%')+'</td><td>'+sign(x.d20,2,'%')+'</td><td>'+sign(x.d60,2,'%')+'</td><td>'+sign(x.spread,1,' pb')+'</td><td>'+date(x.spreadDate)+'</td><td><button type="button" data-cs-openpair="'+c+x.k+'">Dossier ↗</button></td></tr>').join('')+'</tbody></table></div>'
    +'<p class="cs-caveat">7 confronti × orizzonti 5/20/60 sedute. La quotazione '+c+'/X è sempre unità X per 1 '+c+'. Per alcune valute lo spread è storico perché non tutti i benchmark sono recenti. È il rischio da verificare, non da nascondere.</p></div>';
 }
 function narrative(){
   const a=macro(c),infl=a?.inflation,lab=a?.labour,cb=CB[c],h6=OIS[c]?.horizons?.['6m'];
   const C=cot(c),j=C?.net?.length-1,cn=j>=0?C.net[j]:null,cp=j>=1?C.net[j-1]:null;
   const price20=ret(rows,20),rateSpread=bondLast?.value,one=PAIR[c+other]||PAIR[other+c],orient=!!PAIR[c+other];
   const po=one?.setup,frame=one?.decision_frame;
   const pString=finite(price20)?(price20>0?'si è apprezzata':price20<0?'si è deprezzata':'è rimasta invariata')+' del '+fmt(Math.abs(price20),2)+'%':'non ha una variazione verificata';
   const levelC=finite(infl?.latest_value)?fmt(infl.latest_value,2)+'%':'n.d.';
   const conf=frame?.priceNote||'Serve verificare la reazione del prezzo con la tesi macro e monetaria.';
   const track=[
     ['01','MACRO','Livello e dinamica','Inflazione '+levelC+' ('+percDay(infl?.as_of)+') · disoccupazione '+fmt(lab?.latest_value,2)+'% ('+percDay(lab?.as_of)+'). Direzione CPI '+esc(infl?.direction||'n.d.')+', lavoro '+esc(lab?.direction||'n.d.')+'.','macro'],
     ['02','PRICING','Banca centrale / aspettative',policy.bank+': '+policy.rate+'; ultima decisione '+date(policy.date)+'. Il 6M mostra '+fmt(h6?.rate,3)+'% ('+esc(policy.pName)+', '+date(h6?.as_of)+', '+esc(policy.pQuality)+').','rates'],
     ['03','POSITIONING','Stock e flusso','Net CFTC '+sign(cn,0)+' e variazione settimanale '+sign(finite(cn)&&finite(cp)?cn-cp:null,0)+' al '+date(C?.dates?.[j])+'. Non è un segnale autonomo.','cot'],
     ['04','PREZZO','Cosa conferma il cambio?',c+'/'+other+' '+pString+' nelle ultime 20 sedute fino al '+date(latest?.label)+'. Il differenziale sovrano 2Y è '+sign(rateSpread,1,' pb')+' al '+date(bondLast?.label)+'.','pairs']
   ];
   return section('06 / DALLA STORIA ALLA TESI','Una narrativa <em>che puoi falsificare.</em>','Quattro passaggi collegati ma con fonti, convenzioni e date differenti. Il mercato può smentire una lettura economica plausibile.')
    +'<div class="cs-story-grid">'+track.map(([n,tag,title,body,route])=>'<article><span class="cs-story-num">'+n+'</span><span class="micro-over">'+tag+'</span><h3>'+esc(title)+'</h3><p>'+esc(body)+'</p><a href="#'+route+'" class="action-minimal">Approfondisci ↗</a></article>').join('')+'</div>'
    +'<div class="cs-thesis-audit"><div><span class="micro-over">CORE / PAIR DIAGNOSTIC</span><h3>'+esc(one?.canonical_pair||c+'/'+other)+'</h3><p>'+esc(frame?.relation||'Valutazione relativa da verificare nel motore delle coppie.')+'</p></div>'
    +'<div><span class="micro-over">QUALITÀ DEL SETUP</span><strong>'+esc(po?.quality||'NON VALUTABILE')+'</strong><p>'+esc(conf)+'</p></div>'
    +'<div><span class="micro-over">COSA SMENTIREBBE / LIMITI</span><strong>Verifiche mancanti</strong><p>'+esc(frame?.missing||'Servono date allineate, prezzo e pricing coerenti.')+'</p></div></div>'
    +'<p class="cs-caveat">La tesi del motore è riferita alla coppia canonica '+esc(one?.canonical_pair||'non presente')+(orient?'':' (orientamento opposto a quello visualizzato)')+'. Baseline macro della coppia: '+date(get('pairs')?.macro_baseline_asof)+'. Non è una raccomandazione operativa e non aggiorna i segnali Core.</p>';
 }
 function explain(){
   const glossary=[
     ['FX cross e orientamento','Nel cambio A/B, il prezzo indica quante unità B servono per acquistare una unità A. Un aumento favorisce A; non è la stessa cosa del prezzo B/A.'],
     ['Fixing BCE','Cambio di riferimento giornaliero; non è un prezzo intraday né una garanzia di esecuzione. La serie cross è ottenuta dai due cambi EUR.'],
     ['Differenziale governativo','Il 2Y(A) − 2Y(B) è calcolato sulle stesse date delle due serie. Il dato sovrano include premi e convenzioni non identici agli OIS.'],
     ['Percorso 3M/6M/12M','I tenori provengono da OIS, futures o proxy con diverse qualità. Differenze tra livelli non dimostrano repricing nel tempo.'],
     ['Percentile COT','Percentile alto significa net positioning elevato rispetto alle 104 settimane della stessa valuta, non necessariamente netto positivo.'],
     ['Conferma/dissenso','Prezzi, curve e COT possono muoversi in direzioni differenti, su date diverse. Una coincidenza non prova causalità.'],
     ['Macro livello / direzione','Un livello CPI alto può decelerare; la disoccupazione può restare bassa mentre accelera verso l’alto. Non confondere livello e cambiamento.'],
     ['Ritardi e qualità','Il COT è riferito al martedì; FX e government yields hanno proprie chiusure; le stime non diventano osservazioni ufficiali.']
   ];
   return section('07 / GUIDA COUNTRY DESK','Tutti i numeri <em>hanno un significato.</em>','Definizioni sintetiche da consultare mentre analizzi il mercato.')
    +'<div class="cs-glossary">'+glossary.map(([a,b])=>'<details><summary>'+esc(a)+'<span>＋</span></summary><p>'+esc(b)+'</p></details>').join('')+'</div>';
 }
 function render(){
  return pageHero('FX G8 / COUNTRY RESEARCH STUDIO','Otto valute. <em>Un solo metodo.</em>','Dalla macro al prezzo: una ricerca multidimensionale con dati, grafici, confronti FX e condizioni da verificare. Seleziona una valuta e una controvaluta.')
    +'<div class="cs-sourceband"><span>◉ COUNTRY DEEP DIVE · '+FLAGS[c]+' '+c+'</span><span>ECB FIXING '+date(latest?.label)+' · GOV 2Y '+date(rateA?.date)+' · CFTC '+date(cot(c)?.dates?.at(-1))+'</span></div>'
    +countrySelector()+chooseCounterparty()+hero()+strip()+marketCharts()+evidencePanel()
    +section('04 / MONETARY POLICY','La banca centrale non è <em>la curva a termine.</em>','Decisione ufficiale, pricing dei tenori e qualità dello strumento in un unico audit leggibile.')
    +cbTable()+crossTable()+narrative()+explain()
    +'<div class="cs-final"><div><span class="chapter-kicker">COUNTRY DESK / IL PROSSIMO PASSO</span><h2>Hai una tesi? <em>Apri il dossier della coppia.</em></h2><p>Confronta macro, pricing, COT e prezzo per valutare cosa confermerebbe o indebolirebbe il vantaggio relativo.</p></div>'
    +'<button class="action-primary" type="button" data-cs-openpair="'+c+other+'">Vai al Pair Deep Dive ↗</button></div>'
    +'<p class="source-caption">Fonti: BCE EUR fixing (ECB_G8_PRICE_HISTORY, storico fino al '+date(PRICES?.last_as_of)+'); governativi NATIVE_RATES_DATA; NATIVE_CB_DATA; OIS/Futures/proxy ois-pricing-snapshot; CFTC Legacy V250; Macro thermometer e MACRO_SERIES; setup diagnostico delle 28 coppie. Nessun cambiamento al motore FX operativo.</p>';
 }
 return render();
}
root.FXQuantCurrencies={render:make};
})(window);
