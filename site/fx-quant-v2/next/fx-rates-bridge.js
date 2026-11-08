'use strict';
/* NEXT V13: observational FX-vs-sovereign-2Y rates evidence.
 * ONLY exact common source dates. No OIS history, causality, return forecasts,
 * price interpolation, pseudo-correlation or use of post-snapshot market data.
 */
(function(){
 const isDay=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const isNum=x=>typeof x==='number'&&Number.isFinite(x);
 const days=(a,b)=>isDay(a)&&isDay(b)?Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5):null;

 const isGovSource=r=>/^FULL_CURRENT_OFFICIAL/.test(r?.quality||'')||
  r?.quality==='OFFICIAL_RBA_F2_DAILY_RESEARCH_ONLY';
 // RBA daily observations remain independent research: no Core or FX engine writes.
 function researchRates(rateData,research,modelDate,now){
  const a=rateData?.AUD,o=research?.observations;
  if(!a||!/^FULL_CURRENT_OFFICIAL/.test(a.quality||'')||
    research?.schema!=='GMFQ_AUD_RBA_F2_DAILY_HISTORY_RESEARCH_V1'||
    research?.status!=='OFFICIAL_F2_DAILY_RESEARCH_ONLY_NOT_POINT_IN_TIME'||
    research?.source_url!=='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'||
    research?.series_2Y!=='FCMYGBAG2D'||research?.series_10Y!=='FCMYGBAG10D'||
    !/^[0-9a-f]{64}$/.test(research?.source_response_sha256||'')||
    research?.research_only!==true||research?.same_date_same_source!==true||
    research?.no_interpolation!==true||
    research?.eligible_for_core!==false||research?.eligible_for_fx_pair_engine!==false||
    research?.eligible_for_backtests!==false||
    !isDay(research?.publication_date)||research.publication_date>now||
    !isDay(research?.last_observation_date)||research.last_observation_date>modelDate||
    research.last_observation_date>research.publication_date||
    research.last_observation_date!==a.date||
    !Array.isArray(o)||o.length<30||o.length>150)return rateData;
  let previous='',valid=true;
  for(const item of o){
   if(!isDay(item?.date)||item.date<=previous||item.date>research.last_observation_date||
    !isNum(item['2Y'])||!isNum(item['10Y'])||
    !(item['2Y']>-5&&item['2Y']<25)||
    !(item['10Y']>-5&&item['10Y']<25)){valid=false;break}
   previous=item.date;
  }
  const last=o.at(-1);
  if(!valid||last.date!==research.last_observation_date||
   Math.abs(last['2Y']-a['2Y'])>0.00001||
   Math.abs(last['10Y']-a['10Y'])>0.00001)return rateData;
  return {...rateData,AUD:{...a,quality:'OFFICIAL_RBA_F2_DAILY_RESEARCH_ONLY',
   source:'Reserve Bank of Australia F2 · assessed government 2Y/10Y daily, research only',
   history2:{dates:o.map(v=>v.date),values:o.map(v=>v['2Y'])},
   researchOnly:true,sourcePublicationDate:research.publication_date}};
 }
 // Research-only CHF & NZD source context, never a market-grade confirmation.
 // No historical 2Y is merged into canonical rates; no interpolation or roll splice.
 function researchedSources(rateData,pair,modelDate,now,chfHistory,nzdPostroll){
  const notes=[],pairName=String(pair||'');
  const eligible=d=>isDay(d)&&d<=modelDate&&d<=now;
  if(pairName.includes('CHF')){
   const x=chfHistory,o=x?.observations,base=rateData?.CHF;
   if(x?.schema==='GMFQ_FXV2_CHF_SNB_PAIRED_HISTORY_V1'&&
     x?.quality==='SNB_OFFICIAL_OBSERVED_HISTORICAL_RESEARCH'&&
     x?.source_url==='https://data.snb.ch/api/cube/rendeiduebd/data/json/en'&&
     /^[0-9a-f]{64}$/.test(x?.source_response_sha256||'')&&
     x?.source_latest_vintage_not_point_in_time===true&&
     x?.current_session_government_rates_certified===false&&
     x?.eligible_for_core===false&&x?.eligible_for_fx_engine===false&&
     x?.eligible_for_backtests===false&&x?.eligible_for_automatic_promotion===false&&
     Array.isArray(o)&&o.length>=10&&o.length<=300&&o.length===x.observation_count&&
     /^FULL_CURRENT_OFFICIAL/.test(base?.quality||'')&&
     o[0]?.date===base?.date&&eligible(x?.last_observation_date)&&
     o.at(-1)?.date===x.last_observation_date&&
     Math.abs(o[0]['2Y']-base['2Y'])<0.00001&&
     Math.abs(o[0]['10Y']-base['10Y'])<0.00001){
    let valid=true,prev='';
    for(const r of o){
     if(!eligible(r.date)||r.date<=prev||
      !isNum(r['2Y'])||!isNum(r['10Y'])||
      Math.abs((r['10Y']-r['2Y'])*100-r.curve_bp)>0.01){valid=false;break}
     prev=r.date;
    }
    if(valid)notes.push({currency:'CHF',lastDate:x.last_observation_date,count:o.length,
     text:'CHF · SNB: '+o.length+' osservazioni 2Y/10Y sulla stessa data, ultima '+x.last_observation_date+
       ' (storico ufficiale di ricerca, non certificato come quotazione corrente).',
     status:'HISTORICAL_ONLY'});
   }
  }
  if(pairName.includes('NZD')){
   const x=nzdPostroll,o=x?.daily_observations;
   if(x?.schema==='GMFQ_NZD_RBNZ_B2_POSTROLL_WEB_RESEARCH_V1'&&
     x?.status==='PUBLIC_OFFICIAL_WEB_RESEARCH_NOT_XLSX_RECONCILED'&&
     x?.source_url==='https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'&&
     x?.source_capture_method==='PUBLIC_OFFICIAL_PAGE_MANUAL_RESEARCH_NOT_AUTOMATED_FETCH'&&
     x?.benchmark_roll_date==='2026-10-30'&&
     x?.benchmark_2Y==='April 2029'&&x?.benchmark_10Y==='April 2037'&&
     x?.before_roll_2Y==='May 2028'&&x?.before_roll_10Y==='May 2036'&&
     x?.official_web_display_observed===true&&x?.independent_xlsx_reconciled===false&&
     x?.historical_benchmark_roll_continuity===false&&x?.research_only===true&&
     x?.no_interpolation===true&&x?.eligible_for_core===false&&
     x?.eligible_for_fx_pair_engine===false&&x?.eligible_for_backtests===false&&
     x?.eligible_for_automatic_promotion===false&&
     eligible(x?.source_release_date)&&isDay(x?.source_capture_date)&&x.source_capture_date<=now&&
     Array.isArray(o)&&o.length>=2&&o.length<=15&&o[0]?.date===x.benchmark_roll_date&&
     eligible(o.at(-1)?.date)&&o.at(-1).date<=x.source_release_date){
    let valid=true,prev='';
    for(const r of o){
     if(!eligible(r.date)||r.date<=prev||r.date<x.benchmark_roll_date||
      !isNum(r['2Y'])||!isNum(r['10Y'])||
      !(r['2Y']>-5&&r['2Y']<25&&r['10Y']>-5&&r['10Y']<25)){valid=false;break}
     prev=r.date;
    }
    if(valid){
     const intervals=o.length-1,shortfall=Math.max(0,5-intervals);
     notes.push({currency:'NZD',lastDate:o.at(-1).date,count:o.length,intervals,
      status:'POST_ROLL_NOT_APPROVED',
      text:'NZD · RBNZ B2: '+o.length+' chiusure sui nuovi benchmark dal 30/10, '+intervals+
       '/5 intervalli minimi; ultima '+o.at(-1).date+' (2Y '+o.at(-1)['2Y'].toFixed(2)+
       '%, 10Y '+o.at(-1)['10Y'].toFixed(2)+'%). '+(shortfall?
       (shortfall===1?'Manca 1 intervallo e serve la riconciliazione XLSX.':'Mancano '+shortfall+' intervalli e serve la riconciliazione XLSX.'):
       'Copertura temporale sufficiente, ma riconciliazione XLSX ancora mancante.')+
       ' Nessun collegamento attraverso il cambio del titolo del 30/10.'});
    }
   }
  }
  return notes;
 }
 function commonObservations(rateData,prices,pair,modelDate,now){
  if(!/^[A-Z]{6}$/.test(pair||'')||!isDay(modelDate)||modelDate>now||
   !Array.isArray(prices?.rows))return [];
  const base=pair.slice(0,3),quote=pair.slice(3),a=rateData?.[base],b=rateData?.[quote];
  if(!a||!b||!isDay(a.date)||!isDay(b.date)||
    !isGovSource(a)||!isGovSource(b))return [];
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
 function snapshot(rateData,prices,pair,modelDate,now,audHistory,chfHistory,nzdPostroll){
  const eff=String(pair||'').includes('AUD')?researchRates(rateData,audHistory,modelDate,now):rateData;
  const base=String(pair||'').slice(0,3),quote=String(pair||'').slice(3,6);
  const a=eff?.[base],b=eff?.[quote],rows=commonObservations(eff,prices,pair,modelDate,now),latest=rows.at(-1);
  const lag=latest?days(latest.date,modelDate):null,age=latest?days(latest.date,now):null;
  const sourceOK=Boolean(isGovSource(a)&&isGovSource(b));
  const ready=Boolean(latest&&sourceOK&&lag!==null&&lag>=0&&lag<=3&&age!==null&&age>=0&&age<=5);
  const short=ready?metrics(rows,5,12):null;
  const medium=ready?metrics(rows,20,45):null;
  const reason=!sourceOK?'Mancano due rendimenti governativi 2Y ufficiali confrontabili come serie di origine.'
    :!latest?'Non esistono abbastanza fixing BCE e rendimenti 2Y sulle stesse date.'
    :!ready?'Ultima osservazione FX/2Y comune troppo vecchia per confrontare i movimenti recenti.'
    :!short?'Storico troppo discontinuo: 5 intervalli fra date comuni coprono più di 12 giorni o sono insufficienti.'
    :'';
  const context=researchedSources(rateData,pair,modelDate,now,chfHistory,nzdPostroll);
  return {pair,base,quote,rows,latest,age,lag,ready:ready&&Boolean(short),researchOnly:!!(a?.researchOnly||b?.researchOnly),context,
   short,medium,reason,
   firstSource:a?.source||'',secondSource:b?.source||'',
   // This series is a relative sovereign yield difference; never an OIS spread.
   kind:(a?.researchOnly||b?.researchOnly)?'2Y GOV · RBA F2 RICERCA (NON CORE / NON OIS)':'2Y GOV · DIFFERENZIALE INDICATIVO (NON OIS)'};
 }
 // A short, source-dated research observation, never a trade decision.
 function brief(r){
  if(!r?.ready||!r.short||!r.latest?.date)return {
   ready:false,asof:null,tone:'unavailable',label:'2Y governativi non verificabili'+(r?.context?.length?' · '+r.context.map(x=>x.currency==='NZD'?'NZD '+x.intervals+'/5 post-roll':'CHF SNB '+x.lastDate).join(' / '):''),
   explanation:r?.reason||'Dati tassi/FX non disponibili su date comuni.',
   context:r?.context||[]
  };
  const sign=m=>m?.direction==='STESSO SEGNO'?'concordi':
    m?.direction==='SEGNO OPPOSTO'?'discordi':'non conclusivi';
  const short=sign(r.short),long=r.medium?sign(r.medium):'non verificabili';
  const tone=r.medium&&r.short.direction!==r.medium.direction?'mixed':
    r.short.direction==='SEGNO OPPOSTO'?'divergent':
    r.short.direction==='STESSO SEGNO'?'aligned':'uncertain';
  const label='5 intervalli '+short+' · 20 '+long+(r.researchOnly?' · RBA F2 ricerca':'');
  return {ready:true,asof:r.latest.date,tone,label,
   researchOnly:!!r.researchOnly,
   explanation:'Confronto di segno su fixing BCE e governativi 2Y con le stesse date; non OIS, non causalità né segnale.'+(r.researchOnly?' RBA F2 AUD è ricerca, non Core né backtest.':'')};
 }
 function build(api){
  const {get,state,plot,fmt,sign,date,esc,dayNow}=api;
  const pair=state.pair||'EURUSD',doc=get('pairs');
  const r=snapshot(get('rates'),get('currencyPrices'),pair,doc?.price_asof,dayNow(),get('audDailyResearch'),get('chfResearch'),get('nzdPostroll'));
  function read(x){
   if(!x)return 'Non verificabile con la copertura attuale.';
   const direction=x.direction==='STESSO SEGNO'?'si sono mossi nello stesso verso'
    :x.direction==='SEGNO OPPOSTO'?'si sono mossi in versi opposti'
    :'non danno un confronto direzionale conclusivo';
   return 'Tra '+date(x.start)+' e '+date(x.end)+' ('+x.n+' intervalli fra '+(x.n+1)+' date comuni, '+x.days+' giorni) prezzo FX e differenziale 2Y '+direction+'.';
  }
  function render(){
   if(!r.ready)return '<section class="decision-rates-bridge" aria-label="Conferma tassi e prezzo"><div class="decision-rates-heading"><span>PREZZO FX / TASSI 2Y</span><h2>La verifica sui tassi non è disponibile.</h2></div><p class="decision-rate-unavailable">'+esc(r.reason)+'</p>'+(r.context.length?'<div class="decision-source-evidence"><span>FONTI DI RICERCA OSSERVATE · NON IDONEE AL VERDETTO 5/20</span>'+r.context.map(x=>'<p data-source-context="'+x.currency+'">'+esc(x.text)+'</p>').join('')+'</div>':'')+'<small>Per evitare una falsa divergenza non confrontiamo serie di date diverse o osservazioni troppo distanti. Le curve OIS storiche non sono disponibili qui.</small></section>';
   const sel=[20,60,120].includes(Number(state.pairPriceWindow))?Number(state.pairPriceWindow):60;
   const line=r.rows.slice(-sel).map(x=>({label:x.date,value:x.spread}));
   const figure=plot({lines:[{name:r.base+' 2Y − '+r.quote+' 2Y',color:'#e2b985',values:line}],precision:1,unit:' bp',label:'Differenziale rendimenti governativi 2 anni '+r.base+' meno '+r.quote});
   const pill=x=>x?'<div class="decision-rate-horizon" data-horizon="'+x.n+'"><span>'+x.n+' INTERVALLI · '+(x.n+1)+' DATE COMUNI · '+x.days+' GIORNI</span><strong>'+sign(x.fxPct,2,'%')+' FX <b>vs</b> '+sign(x.spreadBp,1,' bp')+' 2Y</strong><small>'+esc(x.direction)+' · '+date(x.start)+' → '+date(x.end)+'</small></div>':'';
   const short=r.short;
   const shortText=short.direction==='STESSO SEGNO'?'Nei 5 intervalli tra le ultime 6 date comuni il prezzo FX e lo spread 2Y si sono mossi nello stesso verso.'
    :short.direction==='SEGNO OPPOSTO'?'Nei 5 intervalli tra le ultime 6 date comuni il prezzo FX e lo spread 2Y hanno segni opposti.'
    :'I 5 intervalli tra le ultime 6 date comuni non mostrano un verso congiunto definito.';
   const mediumText=r.medium
     ?r.medium.direction===short.direction?' Anche sui 20 intervalli tra 21 date comuni il confronto è '+(r.medium.direction==='STESSO SEGNO'?'concorde nel segno.':r.medium.direction==='SEGNO OPPOSTO'?'discordante nel segno.':'non conclusivo.')
       :' Sui 20 intervalli tra 21 date comuni il risultato cambia: '+(r.medium.direction==='STESSO SEGNO'?'si muovono nello stesso verso.':r.medium.direction==='SEGNO OPPOSTO'?'si muovono in versi opposti.':'non emerge un verso conclusivo.')
     :' Il confronto su 20 intervalli tra 21 date comuni non è sufficientemente continuo per una conclusione.';
   const verdict=shortText+mediumText+' Non dimostra causalità, rendimento atteso o una relazione quantitativa validata.';
   const recentDifferent=r.lag>0?' Attenzione: il grafico si ferma al '+date(r.latest.date)+', mentre lo snapshot FX arriva al '+date(doc?.price_asof)+'. Il fixing più recente NON è stato abbinato a un tasso di un altro giorno.':'';
   return '<section class="decision-rates-bridge" aria-label="Prezzo e repricing 2Y" data-rate-asof="'+esc(r.latest.date)+'" data-aud-research="'+String(r.researchOnly)+'">'
    +'<div class="decision-rates-heading"><div><span>PREZZO FX / PRICING RELATIVO</span><h2>'+esc(r.base+'/'+r.quote)+' · i tassi confermano il prezzo?</h2><p>Due evidenze sullo stesso calendario, senza mischiare scale: fixing BCE e differenziale governativo 2Y.</p></div><a href="#rates" class="decision-rates-link">Apri Tassi & OIS</a></div>'
    +'<div class="decision-rates-body"><div class="decision-rates-visual"><span>GRAFICO · '+esc(r.base)+' 2Y − '+esc(r.quote)+' 2Y</span>'+figure+'<small>Rendimenti governativi 2Y ufficiali. Spread espresso in punti base, non OIS né differenziale di carry. Visualizzazione sulle ultime '+line.length+' date comuni.'+(r.researchOnly?' AUD RBA F2: osservazioni giornaliere pubblicate settimanalmente; ricerca non canonica, non benchmark amministrato.':'')+'</small></div>'
    +'<div class="decision-rates-analysis"><span>COSA CONFERMANO I DATI?</span><h3>'+esc(r.medium&&r.medium.direction!==short.direction?'Segnali diversi tra breve e medio periodo.':short.direction==='STESSO SEGNO'?'Movimenti concordi, ma non prova causale.':short.direction==='SEGNO OPPOSTO'?'Prezzo e spread 2Y divergono.':'Confronto direzionale non conclusivo.')+'</h3>'
    +pill(short)
    +(r.medium?pill(r.medium):'<p class="decision-rate-data-gap">Orizzonte 20 intervalli (21 date comuni) non comparabile: osservazioni troppo rade o intervallo superiore a 45 giorni.</p>')
    +'<p class="decision-rates-verdict">'+esc(verdict+recentDifferent)+'</p></div></div>'
    +'<details class="decision-rates-method"><summary>Fonti, date e limiti del confronto</summary><p>'+esc(read(short))+' '+esc(read(r.medium))+'</p>'
    +'<p>'+esc(r.base)+': '+esc(r.firstSource)+'; '+esc(r.quote)+': '+esc(r.secondSource)+'. I benchmark governativi e le metodologie possono differire (par, spot, zero-coupon): lo spread è indicativo. '+(r.researchOnly?'RBA F2: pubblicazione settimanale di osservazioni giornaliere, valutazioni di ricerca non benchmark amministrati; nessuna idoneità point-in-time per backtest. ':'')+'Non stiamo confrontando curve OIS e non inferiamo che i tassi causino il movimento FX.</p></details></section>';
  }
  return {data:r,render};
 }
 if(typeof window!=='undefined')window.FXQuantRatesBridge={snapshot,commonObservations,metrics,brief,build,researchRates,researchedSources};
 if(typeof module!=='undefined'&&module.exports)module.exports={snapshot,commonObservations,metrics,brief,build,researchRates,researchedSources};
})();