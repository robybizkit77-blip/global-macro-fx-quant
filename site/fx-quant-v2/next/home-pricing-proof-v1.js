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

 // Longer horizons use exactly N BCE fixing sessions and the primary daily
 // comparison's end date. Never interpolate missing 6M or BCE observations.
 function inspectSessionWindow(pair,{prices,pairs,history,today}={},sessions,anchor){
  if(![5,20].includes(sessions)||typeof pair!=='string'||!/^[A-Z]{6}$/.test(pair)||
   !pairs?.pairs?.[pair]||!goodDate(anchor)||!goodDate(today)||anchor>today||
   !Array.isArray(prices?.rows))return null;
  const archive=root.FXQuantPricingHistory,bridge=root.FXQuantPairMonetary;
  if(!archive?.country||!bridge?.validLeg)return null;
  const dates=[...new Set(prices.rows.filter(x=>goodDate(x?.Date)&&x.Date<=today)
   .map(x=>x.Date))].sort();
  const idx=dates.indexOf(anchor);
  if(idx<sessions)return null;
  const from=dates[idx-sessions],to=anchor;
  const base=pair.slice(0,3),quote=pair.slice(3);
  if(!currencies.includes(base)||!currencies.includes(quote)||base===quote)return null;
  const A=archive.country(history,base,60)?.tenors?.['6m']||[];
  const B=archive.country(history,quote,60)?.tenors?.['6m']||[];
  const at=(s,day)=>s.find(x=>x.date===day);
  const a0=at(A,from),a1=at(A,to),b0=at(B,from),b1=at(B,to);
  const mA=bridge.validLeg(a0,a1,base),mB=bridge.validLeg(b0,b1,quote);
  if(!mA||!mB)return null;
  // Same-contract futures must not cross a known intervening rollover.
  const uninterrupted=(series,start,end,method)=>{
   if(method!=='SAME_LISTED_CONTRACT')return true;
   return series.filter(x=>x.date>=from&&x.date<=to).every(x=>
    x.source_class==='SECONDARY_SAME_CONTRACT'&&x.contract===start.contract&&
    x.contract===end.contract&&!x.derived);
  };
  if(!uninterrupted(A,a0,a1,mA)||!uninterrupted(B,b0,b1,mB))return null;
  const fx=pairReturn(prices,pair,from,to,today);
  if(!fx)return null;
  const aBp=Math.round((a1.rate-a0.rate)*10000)/100,
   bBp=Math.round((b1.rate-b0.rate)*10000)/100;
  const monetaryBp=Math.round((aBp-bBp)*100)/100;
  const comparison=Math.abs(monetaryBp)<.05||Math.abs(fx.percent)<.005?
   'MOVIMENTO_CONTENUTO':
   Math.sign(monetaryBp)===Math.sign(fx.percent)?'SEGNI_COHERENTI':'SEGNI_DIVERGENTI';
  return {pair,base,quote,sessions,from,to,monetaryBp,fxPct:fx.percent,
   comparison,proxy:mA==='PROXY_DELTA_RECONSTRUCTED'||mB==='PROXY_DELTA_RECONSTRUCTED',
   sourceDates:{money:to,spot:fx.to},aMethod:mA,bMethod:mB};
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

 // Editorial interpretation only: compares the direction of dated observations,
 // never infers causality or treats overlapping windows as independent tests.
 function horizonReading(x,windows){
  const [five,twenty]=windows;
  const short=x.comparison==='MOVIMENTO_CONTENUTO'?
   'Nel confronto breve almeno uno dei movimenti è contenuto: il segno non è indicativo.':
   'Nel confronto breve il 6M relativo si sposta verso '+(x.monetaryBp>0?x.base:x.quote)+
   ', mentre '+pairText(x.pair)+(x.fxPct>0?' sale.':' scende.');
  const signal=s=>s==='SEGNI_COHERENTI'?'tassi relativi e cambio hanno lo stesso segno':
   s==='SEGNI_DIVERGENTI'?'tassi relativi e cambio divergono':
   'almeno un movimento è contenuto';
  const condition=s=>s==='SEGNI_COHERENTI'?'coerenza di segno':
   s==='SEGNI_DIVERGENTI'?'divergenza di segno':'movimenti contenuti';
  let longer;
  if(five&&twenty){
   longer=five.comparison===twenty.comparison&&five.comparison===x.comparison?
    'La stessa '+condition(x.comparison)+' compare anche sulle finestre a 5 e 20 sedute.':
    'A 5 sedute '+signal(five.comparison)+'; a 20 sedute '+signal(twenty.comparison)+'.';
  }else if(five){
   longer=x.comparison===five.comparison?
    'La stessa '+condition(five.comparison)+' compare anche a 5 sedute; a 20 il dato non è verificabile.':
    'A 5 sedute '+signal(five.comparison)+'; a 20 il dato non è verificabile.';
  }else if(twenty){
   longer='A 5 sedute il dato non è verificabile; a 20 sedute '+signal(twenty.comparison)+'.';
  }else{
   longer='Non ci sono confronti verificabili a 5 o 20 sedute per questa coppia.';
  }
  return short+' '+longer;
 }


 // Weekday counts are an editorial freshness guard, not an exchange calendar.
 // A Friday observation remains recent over the weekend; bank holidays may
 // make the warning conservative, never create synthetic market sessions.
 function weekdayLag(from,to){
  if(!goodDate(from)||!goodDate(to)||from>to)return null;
  const n=Math.round((strongDate(to)-strongDate(from))/86400000);
  let count=Math.floor(n/7)*5;
  const start=new Date(strongDate(from)).getUTCDay();
  for(let i=1;i<=n%7;i++){const d=(start+i)%7;if(d!==0&&d!==6)count++;}
  return count;
 }
 function freshness({prices,history,today}={},picks=[]){
  if(!goodDate(today))return {stale:true,status:'DATE_NON_VERIFICABILI',priceAsOf:null,moneyAsOf:null};
  const raw=Array.isArray(prices?.rows)?prices.rows.map(r=>r?.Date).filter(d=>goodDate(d)&&d<=today).sort():[];
  const latestRow=raw.at(-1)||null;
  const reported=goodDate(prices?.last_as_of)&&prices.last_as_of<=today?prices.last_as_of:null;
  const priceAsOf=latestRow&&reported?(latestRow<reported?latestRow:reported):latestRow;
  const moneyAsOf=goodDate(history?.as_of)&&history.as_of<=today?history.as_of:null;
  const fxAge=weekdayLag(priceAsOf,today),moneyAge=weekdayLag(moneyAsOf,today);
  const evidenceStale=picks.some(p=>{const n=weekdayLag(p.to,today);return n===null||n>=3;});
  const stale=fxAge===null||moneyAge===null||fxAge>=3||moneyAge>=3||evidenceStale;
  return {stale,status:stale?'ARCHIVIO_NON_RECENTE':'CONFRONTO_STORICO_DATATO',
   priceAsOf,moneyAsOf,fxAge,moneyAge,evidenceStale};
 }

 function render(args={}){
  const picks=choose(args);
  if(!picks.length)return '';
  const asof=args.history?.as_of;
  const status=freshness(args,picks);
  const sourceLine='<div class="home-pricing-proof-date-context" data-home-pricing-freshness="'+status.status+'">'+
   '<strong>Ultima data disponibile per fonte</strong> · fixing BCE '+esc(date(status.priceAsOf))+
   ' · archivio 6M '+esc(date(status.moneyAsOf))+
   '. Ogni coppia riporta la data effettiva del confronto.'+
   (status.stale?' <strong>Attenzione: almeno una fonte o un confronto è fermo da 3 o più giorni feriali. Lettura soltanto storica.</strong>':'')+
   '</div>';
  const row=x=>{
   const sign=x.comparison==='SEGNI_COHERENTI'?'Stesso segno, non causalità':
    x.comparison==='SEGNI_DIVERGENTI'?'I segnali divergono':
    'Movimenti contenuti';
   const windows=[5,20].map(n=>inspectSessionWindow(x.pair,args,n,x.to));
   const oldObservation=weekdayLag(x.to,args.today)>=3;
   const headline=(oldObservation?'Questa verifica non è recente e non descrive la seduta attuale. ':'')+
    horizonReading(x,windows);
   const longRow=(w,n)=>'<div class="home-pricing-proof-multi-row" data-home-pricing-sessions="'+n+'"'+
    ' data-home-pricing-available="'+(w?'true':'false')+'">'+
    '<strong>'+n+' sedute BCE</strong>'+
    (w?'<span>'+esc(date(w.from))+' → '+esc(date(w.to))+'</span>'+
     '<span>Δ 6M '+esc(fmt(w.monetaryBp))+' pb · FX '+esc(fmt(w.fxPct))+'%</span>'+
     '<em>'+(w.comparison==='SEGNI_COHERENTI'?'Stesso segno':
      w.comparison==='SEGNI_DIVERGENTI'?'Segni divergenti':'Movimenti contenuti')+
     (w.proxy?' · proxy ricostruito':'')+'</em>':
     '<span>Non disponibile: manca il 6M confrontabile nelle due date BCE</span>')+
    '</div>';
   const longView='<details class="home-pricing-proof-multi">'+
    '<summary>Verifica anche 5 e 20 sedute</summary>'+
    '<div class="home-pricing-proof-multi-grid">'+windows.map((w,i)=>
     longRow(w,[5,20][i])).join('')+'</div>'+
    '</details>';
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
    longView+
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
    sourceLine+
    '<div class="home-pricing-proof-grid">'+picks.map(row).join('')+'</div>'+
    '<details class="home-pricing-proof-sources"><summary>Verifica i dati e il metodo</summary>'+
    '<p>Per ogni coppia si confrontano <strong>due variazioni 6M</strong> di strumenti distinti e la variazione del fixing BCE sulla stessa data iniziale e finale. Contratti secondari senza continuità di codice sono esclusi. OIS, futures e proxy non sono equivalenti.</p>'+
    '<p>La soglia di avviso sulla recenza usa 3 giorni feriali, non giorni di negoziazione certificati; non modifica né stima i dati. La data generale dell’archivio non implica che ogni valuta sia aggiornata fino a quel giorno.</p>'+ 
    '<p>Le finestre sono sovrapposte: un segno comune su 1, 5 e 20 sedute non rappresenta tre conferme indipendenti né dimostra un rapporto causale.</p>'+ 
    '<p>Le finestre a 5 e 20 sedute usano il calendario dei fixing BCE e terminano alla stessa data del confronto breve; richiedono due livelli 6M verificati per entrambe le valute senza cambio di contratto futures. Dove mancano i livelli, il risultato non è stimato.</p>'+ 
   '<p>Gli esempi sono retrospettivi, non una graduatoria di opportunità o uno studio causale. '+
    'I livelli disponibili sono archiviati; questa analisi non è un backtest point-in-time. '+
    'Stesso segno non equivale a conferma della tesi macro o a timing di ingresso.</p>'+
    '<nav><a href="./rates-pricing-history-v1.json" target="_blank" rel="noopener noreferrer">Storico monetario G8 · JSON ↗</a>'+
    '<a href="../../../live_data/sections/ECB_G8_PRICE_HISTORY.json" target="_blank" rel="noopener noreferrer">Fixing BCE G8 · JSON ↗</a>'+
    '<a href="../ois-same-contract-repricing-research.json" target="_blank" rel="noopener noreferrer">Identità futures · JSON ↗</a></nav>'+
    '</details></section>';
 }
 const api={inspectPair,inspectSessionWindow,horizonReading,weekdayLag,freshness,choose,pairReturn,render};
 root.FXQuantHomePricingProof=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
