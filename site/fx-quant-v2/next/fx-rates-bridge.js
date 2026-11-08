'use strict';
/* NEXT V13: observational FX-vs-sovereign-2Y rates evidence.
 * ONLY exact common source dates. No OIS history, causality, return forecasts,
 * price interpolation, pseudo-correlation or use of post-snapshot market data.
 */
(function(){
 const isDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const isNum=x=>typeof x==='number'&&Number.isFinite(x);
 const days=(a,b)=>isDay(a)&&isDay(b)?Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;
 function commonObservations(rateData,prices,pair,modelDate,now){
  if(!/^[A-Z]{6}$/.test(pair||'')||!isDay(modelDate)||modelDate>now||
   !Array.isArray(prices?.rows))return [];
  const base=pair.slice(0,3),quote=pair.slice(3),a=rateData?.[base],b=rateData?.[quote];
  if(!a||!b||!isDay(a.date)||!isDay(b.date)||
    !/^FULL_CURRENT_OFFICIAL/.test(a.quality||'')||
    !/^FULL_CURRENT_OFFICIAL/.test(b.quality||''))return [];
  const makeMap=r=>{
   const d=r.history2?.dates,v=r.history2?.values,acc=new Map();
   if(!Array.isArray(d)||!Array.isArray(v)||d.length!==v.length)return null;
   for(let i=0;i<d.length;i++){
    if(isDay(d[i])&&d[i]<=r.date&&d[i]<=modelDate&&d[i]<=now&&isNum(v[i]))acc.set(d[i],v[i]);
   }
   return acc;
  };
  const x=makeMap(a),y=makeMap(b);
  if(!x||!y)return [];
  const rows=new Map();
  for(const r of prices.rows){
   const d=r?.Date,u=r?.[base],v=r?.[quote];
   if(!isDay(d)||d>prices.last_as_of||d>modelDate||d>now||!x.has(d)||!y.has(d)||
    !isNum(u)||u<=0||!isNum(v)||v<=0)continue;
   const spot=v/u,spread=(x.get(d)-y.get(d))*100; // bp: sovereign 2Y base - quote
   if(isNum(spot)&&spot>0&&isNum(spread))rows.set(d,{date:d,spot,spread});
  }
  return [...rows.values()].sort((p,q)=>p.date.localeCompare(q.date));
 }
 function metrics(rows,n,maxSpan){
  if(rows.length<n+1)return null;
  const last=rows.at(-1),start=rows.at(-(n+1)),span=days(start.date,last.date);
  if(span===null||span>maxSpan)return null;
  const fx=(last.spot/start.spot-1)*100,bp=last.spread-start.spread;
  const direction=(Math.abs(fx)<1e-10||Math.abs(bp)<1e-10)?'NEUTRO':fx*bp>0?'STESSO SEGNO':'SEGNO OPPOSTO';
  return {n,start:start.date,end:last.date,days:span,fxPct:fx,spreadBp:bp,direction};
 }
 function snapshot(rateData,prices,pair,modelDate,now){
  const base=String(pair||'').slice(0,3),quote=String(pair||'').slice(3,6);
  const a=rateData?.[base],b=rateData?.[quote],rows=commonObservations(rateData,prices,pair,modelDate,now),latest=rows.at(-1);
  const lag=latest?days(latest.date,modelDate):null,age=latest?days(latest.date,now):null;
  const sourceOK=Boolean(a&&b&&/^FULL_CURRENT_OFFICIAL/.test(a.quality||'')&&/^FULL_CURRENT_OFFICIAL/.test(b.quality||''));
  const ready=Boolean(latest&&sourceOK&&lag!==null&&lag>=0&&lag<=3&&age!==null&&age>=0&&age<=5);
  const short=ready?metrics(rows,5,12):null;
  const medium=ready?metrics(rows,20,45):null;
  const reason=!sourceOK?'Mancano due rendimenti governativi 2Y ufficiali confrontabili come serie di origine.'
    :!latest?'Non esistono abbastanza fixing BCE e rendimenti 2Y sulle stesse date.'
    :!ready?'Ultima osservazione FX/2Y comune troppo vecchia per confrontare i movimenti recenti.'
    :!short?'Storico troppo discontinuo: cinque osservazioni comuni coprono più di 12 giorni o sono insufficienti.'
    :'';
  return {pair,base,quote,rows,latest,age,lag,ready:ready&&Boolean(short),
   short,medium,reason,
   firstSource:a?.source||'',secondSource:b?.source||'',
   // This series is a relative sovereign yield difference; never an OIS spread.
   kind:'2Y GOV · DIFFERENZIALE INDICATIVO (NON OIS)'};
 }
 function build(api){
  const {get,state,plot,fmt,sign,date,esc,dayNow}=api;
  const pair=state.pair||'EURUSD',doc=get('pairs');
  const r=snapshot(get('rates'),get('currencyPrices'),pair,doc?.price_asof,dayNow());
  function read(x){
   if(!x)return 'Non verificabile con la copertura attuale.';
   const direction=x.direction==='STESSO SEGNO'?'si sono mossi nello stesso verso'
    :x.direction==='SEGNO OPPOSTO'?'si sono mossi in versi opposti'
    :'non danno un confronto direzionale conclusivo';
   return 'Tra '+date(x.start)+' e '+date(x.end)+' ('+x.n+' osservazioni comuni, '+x.days+' giorni) prezzo FX e differenziale 2Y '+direction+'.';
  }
  function render(){
   if(!r.ready)return '<section class="decision-rates-bridge" aria-label="Conferma tassi e prezzo"><div class="decision-rates-heading"><span>PREZZO FX / TASSI 2Y</span><h2>La verifica sui tassi non è disponibile.</h2></div><p class="decision-rate-unavailable">'+esc(r.reason)+'</p><small>Per evitare una falsa divergenza non confrontiamo serie di date diverse o osservazioni troppo distanti. Le curve OIS storiche non sono disponibili qui.</small></section>';
   const sel=[20,60,120].includes(Number(state.pairPriceWindow))?Number(state.pairPriceWindow):60;
   const line=r.rows.slice(-sel).map(x=>({label:x.date,value:x.spread}));
   const figure=plot({lines:[{name:r.base+' 2Y − '+r.quote+' 2Y',color:'#e2b985',values:line}],precision:1,unit:' bp',label:'Differenziale rendimenti governativi 2 anni '+r.base+' meno '+r.quote});
   const pill=x=>x?'<div class="decision-rate-horizon" data-horizon="'+x.n+'"><span>'+x.n+' DATE COMUNI · '+x.days+' GIORNI</span><strong>'+sign(x.fxPct,2,'%')+' FX <b>vs</b> '+sign(x.spreadBp,1,' bp')+' 2Y</strong><small>'+esc(x.direction)+' · '+date(x.start)+' → '+date(x.end)+'</small></div>':'';
   const short=r.short;
   const verdict=short.direction==='STESSO SEGNO'?'Il prezzo e il differenziale dei governativi 2Y si sono mossi nello stesso verso sulle cinque osservazioni comuni.'
    :short.direction==='SEGNO OPPOSTO'?'Il prezzo si è mosso in senso opposto al differenziale 2Y sulle cinque osservazioni comuni. Questa divergenza va verificata, non trasformata automaticamente in un trade.'
    :'Le cinque osservazioni comuni non mostrano una direzione congiunta conclusiva.';
   const recentDifferent=r.lag>0?' Attenzione: il grafico si ferma al '+date(r.latest.date)+', mentre lo snapshot FX arriva al '+date(doc?.price_asof)+'. Il fixing più recente NON è stato abbinato a un tasso di un altro giorno.':'';
   return '<section class="decision-rates-bridge" aria-label="Prezzo e repricing 2Y" data-rate-asof="'+esc(r.latest.date)+'">'
    +'<div class="decision-rates-heading"><div><span>PREZZO FX / PRICING RELATIVO</span><h2>'+esc(r.base+'/'+r.quote)+' · i tassi confermano il prezzo?</h2><p>Due evidenze sullo stesso calendario, senza mischiare scale: fixing BCE e differenziale governativo 2Y.</p></div><a href="#rates" class="decision-rates-link">Apri Tassi & OIS</a></div>'
    +'<div class="decision-rates-body"><div class="decision-rates-visual"><span>GRAFICO · '+esc(r.base)+' 2Y − '+esc(r.quote)+' 2Y</span>'+figure+'<small>Rendimenti governativi 2Y ufficiali. Spread espresso in punti base, non OIS né differenziale di carry. Visualizzazione sulle ultime '+line.length+' date comuni.</small></div>'
    +'<div class="decision-rates-analysis"><span>COSA CONFERMANO I DATI?</span><h3>'+esc(short.direction==='STESSO SEGNO'?'Movimenti concordi, ma non prova causale.':short.direction==='SEGNO OPPOSTO'?'Il prezzo non segue il differenziale 2Y.':'Segnale di conferma non conclusivo.')+'</h3>'
    +pill(short)
    +(r.medium?pill(r.medium):'<p class="decision-rate-data-gap">Orizzonte 20 date comuni non comparabile: osservazioni troppo rade o intervallo superiore a 45 giorni.</p>')
    +'<p class="decision-rates-verdict">'+esc(verdict+recentDifferent)+'</p></div></div>'
    +'<details class="decision-rates-method"><summary>Fonti, date e limiti del confronto</summary><p>'+esc(read(short))+' '+esc(read(r.medium))+'</p>'
    +'<p>'+esc(r.base)+': '+esc(r.firstSource)+'; '+esc(r.quote)+': '+esc(r.secondSource)+'. I benchmark governativi e le metodologie possono differire (par, spot, zero-coupon): lo spread è indicativo. Non stiamo confrontando curve OIS e non inferiamo che i tassi causino il movimento FX.</p></details></section>';
  }
  return {data:r,render};
 }
 if(typeof window!=='undefined')window.FXQuantRatesBridge={snapshot,commonObservations,metrics,build};
 if(typeof module!=='undefined'&&module.exports)module.exports={snapshot,commonObservations,metrics,build};
})();