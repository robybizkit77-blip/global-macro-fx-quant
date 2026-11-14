'use strict';
/* FX Quant NEXT / Home: source-first monetary change vs same-date FX movement.
 * Two READ-ONLY cross checks, USD and non-USD, selected by provenance/date.
 * Not a trade ranking or a new pricing forecast.
 */
(function(root){
 const currencies=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const goodDate=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&
   !Number.isNaN(Date.parse(s+'T12:00:00Z'))&&
   new Date(Date.parse(s+'T12:00:00Z')).toISOString().slice(0,10)===s;
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
 const fmt=(v,n=2)=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(n).replace('.',',');
 const date=s=>goodDate(s)?s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4):'n.d.';
 const kind=k=>k==='OIS'?'OIS ufficiale':k==='FUTURES'?'futures ufficiali':
   k==='FUTURES SECONDARI'?'futures secondari':k==='PROXY FUTURES'?'proxy bank-bill':
   'fonte monetaria';
 const pairText=p=>p.slice(0,3)+'/'+p.slice(3);
 const strongDate=s=>Date.parse(s+'T12:00:00Z');
 function priceAt(row,ccy){
  if(ccy==='EUR')return 1;
  const r=row?.[ccy];return finite(r)&&r>0?r:null;
 }
 function pairReturn(prices,pair,from,to,today){
  if(!pair||!goodDate(from)||!goodDate(to)||!goodDate(today)||
   from>=to||to>today||
   prices?.schema!=='GMFQ_ECB_G8_PRICE_HISTORY_V1'||
   prices?.status!=='CURRENT_OFFICIAL_HISTORY'||
   prices?.base!=='EUR'||
   prices?.source_url!=='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'||
   !Array.isArray(prices.rows)||
   !goodDate(prices.last_as_of)||prices.last_as_of<to)return null;
  const lookup=new Map(prices.rows.filter(x=>goodDate(x?.Date)&&x.Date<=today)
   .map(x=>[x.Date,x]));
  const begin=lookup.get(from),end=lookup.get(to);
  if(!begin||!end)return null;
  const a=pair.slice(0,3),b=pair.slice(3);
  const af=priceAt(begin,a),bf=priceAt(begin,b),at=priceAt(end,a),bt=priceAt(end,b);
  if(!af||!bf||!at||!bt)return null;
  const start=bf/af,finish=bt/at,percent=100*(finish/start-1);
  if(!finite(percent))return null;
  return {pair,from,to,percent:Math.round(percent*10000)/10000,
   start,end:finish,source:'BCE · fixing bilaterale ricavato da due fixing EUR',
   quoteConvention:'B per 1 A'};
 }
 function inspectPair(pair,{prices,pairs,history,today}={}){
  if(typeof pair!=='string'||!/^[A-Z]{6}$/.test(pair)||
   !currencies.includes(pair.slice(0,3))||
   !currencies.includes(pair.slice(3))||
   pair.slice(0,3)===pair.slice(3)||!pairs?.pairs?.[pair]||!goodDate(today))return null;
  const api=root.FXQuantPairMonetary;
  if(!api?.historicalWindow)return null;
  const base=pair.slice(0,3),quote=pair.slice(3);
  // Require TWO published dates per leg, with no listed-futures rollover.
  // Historic common-date intervals are never represented as today's pricing.
  const observed=api.historicalWindow(history,base,quote,today,'1d');
  if(!observed||!goodDate(observed.from)||!goodDate(observed.to)||
   !finite(observed.relativeBp)||observed.from>=observed.to||
   !['HISTORICAL_COMMON','HISTORICAL_PROXY_REFERENCE'].includes(observed.grade))
   return null;
  const fx=pairReturn(prices,pair,observed.from,observed.to,today);
  if(!fx)return null;
  const a=history?.currencies?.[base],b=history?.currencies?.[quote];
  if(!a?.kind||!b?.kind)return null;
  const money=observed.relativeBp,epsBp=.05,epsPrice=.005;
  const signed= Math.abs(money)<epsBp||Math.abs(fx.percent)<epsPrice?
    'MOVIMENTO_CONTENUTO':
    Math.sign(money)===Math.sign(fx.percent)?'SEGNI_COHERENTI':'SEGNI_DIVERGENTI';
  const observedAsOf=observed.to,staleness=Math.floor((strongDate(today)-strongDate(observedAsOf))/86400000);
  return {pair,base,quote,from:observed.from,to:observed.to,
   monetaryBp:money,fxPct:fx.percent,comparison:signed,
   pricingType:observed.grade,proxy:observed.reconstructed===true,
   kinds:{base:kind(a.kind),quote:kind(b.kind)},
   sources:{money:'./rates-pricing-history-v1.json',
    spot:'../../../live_data/sections/ECB_G8_PRICE_HISTORY.json'},
   sourceDates:{money:observed.to,spot:fx.to},staleness,
   absoluteMonetary:Math.abs(money)};
 }
 function choose({prices,pairs,history,today}={}){
  if(!prices||!pairs||!history||!goodDate(today))return [];
  const examples=Object.keys(pairs.pairs||{}).filter(x=>/^[A-Z]{6}$/.test(x))
   .map(pair=>inspectPair(pair,{prices,pairs,history,today})).filter(Boolean);
  const ranks=items=>items.sort((a,b)=>b.to.localeCompare(a.to)||
   // Only recency determines eligibility. The next criterion is source quality,
   // never magnitude or predicted FX opportunity.
   Number(a.proxy)-Number(b.proxy)||
   (a.pair==='EURUSD'?-1:b.pair==='EURUSD'?1:0)||
   a.pair.localeCompare(b.pair));
  const usd=ranks(examples.filter(x=>x.base==='USD'||x.quote==='USD'))[0];
  const other=ranks(examples.filter(x=>x.base!=='USD'&&x.quote!=='USD'))[0];
  return [usd,other].filter(Boolean);
 }
 function render(args={}){
  const picks=choose(args);
  if(!picks.length)return '';
  const asof=args.history?.as_of;
  const row=x=>{
   const sign=x.comparison==='SEGNI_COHERENTI'?'Stesso segno, non causalità':
    x.comparison==='SEGNI_DIVERGENTI'?'I segnali divergono':
    'Movimenti contenuti';
   const headline=x.comparison==='SEGNI_COHERENTI'?
    'Le variazioni monetarie e il cambio hanno lo stesso segno.':
    x.comparison==='SEGNI_DIVERGENTI'?
    'Tassi relativi e prezzo non si muovono nella stessa direzione.':
    'Il confronto non mostra una direzione netta e condivisa.';
   const labels=x.proxy?'Proxy ricostruito, non osservazione indipendente':
    'Intervallo osservato in archivio, non intraday';
   return '<article class="home-pricing-proof-card" data-home-pricing-pair="'+esc(x.pair)+
    '" data-home-pricing-status="'+esc(x.comparison)+'" data-home-pricing-to="'+esc(x.to)+'">'+
    '<header><span>CONFRONTO '+esc(pairText(x.pair))+' · '+esc(date(x.from))+
    ' → '+esc(date(x.to))+'</span><strong>'+esc(sign)+'</strong></header>'+
    '<div class="home-pricing-proof-numbers">'+
    '<div><small>Δ RELATIVO 6M · '+esc(x.base)+' − '+esc(x.quote)+'</small>'+
    '<strong class="'+(x.monetaryBp>0?'up':x.monetaryBp<0?'down':'')+'">'+
    esc(fmt(x.monetaryBp))+' pb</strong></div>'+
    '<div><small>CAMBIO '+esc(pairText(x.pair))+' · BCE</small>'+
    '<strong class="'+(x.fxPct>0?'up':x.fxPct<0?'down':'')+'">'+
    esc(fmt(x.fxPct))+'%</strong></div></div>'+
    '<p>'+esc(headline)+' È un confronto storico sulle stesse date, non la prova che i tassi abbiano causato il movimento Forex.</p>'+
    '<footer><span>'+esc(x.kinds.base)+' / '+esc(x.kinds.quote)+' · '+esc(labels)+'</span>'+
    '<button type="button" data-command="pair:'+esc(x.pair)+'" aria-label="Apri il dossier '+esc(pairText(x.pair))+'">Apri dossier FX ↗</button></footer></article>';
  };
  return '<section class="home-pricing-proof" id="home-pricing-proof" '+
    'data-home-pricing-asof="'+esc(asof||'')+
    '" aria-label="Verifica documentata tra repricing monetario e Forex">'+
    '<div class="home-pricing-proof-heading"><div>'+
    '<span class="morning-section-label">DALLE ASPETTATIVE AI CAMBI · DATI CONSULTABILI</span>'+
    '<h2>Il Forex sta seguendo il repricing dei tassi?</h2>'+
    '<p>Due confronti documentati, uno con USD e uno fra altre valute. '+
    'Sono scelti per recenza delle osservazioni confrontabili, <strong>non per attrattività di trading</strong>.</p></div>'+
    '<a href="#rates">Apri le curve OIS/futures ↗</a></div>'+
    '<div class="home-pricing-proof-grid">'+picks.map(row).join('')+'</div>'+
    '<details class="home-pricing-proof-sources"><summary>Verifica i dati e il metodo</summary>'+
    '<p>Per ogni coppia si confrontano <strong>due variazioni 6M</strong> di strumenti distinti e la variazione del fixing BCE sulla stessa data iniziale e finale. Contratti secondari senza continuità di codice sono esclusi. OIS, futures e proxy non sono equivalenti.</p>'+
    '<p>Gli esempi sono retrospettivi, non una graduatoria di opportunità o uno studio causale. '+
    'I livelli disponibili sono archiviati; questa analisi non è un backtest point-in-time. '+
    'Stesso segno non equivale a conferma della tesi macro o a timing di ingresso.</p>'+
    '<nav><a href="./rates-pricing-history-v1.json" target="_blank" rel="noopener noreferrer">Storico monetario G8 · JSON ↗</a>'+
    '<a href="../../../live_data/sections/ECB_G8_PRICE_HISTORY.json" target="_blank" rel="noopener noreferrer">Fixing BCE G8 · JSON ↗</a>'+
    '<a href="../ois-same-contract-repricing-research.json" target="_blank" rel="noopener noreferrer">Identità futures · JSON ↗</a></nav>'+
    '</details></section>';
 }
 const api={inspectPair,choose,pairReturn,render};
 root.FXQuantHomePricingProof=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
