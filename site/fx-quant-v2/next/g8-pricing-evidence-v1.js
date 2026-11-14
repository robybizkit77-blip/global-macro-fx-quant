'use strict';
/* Data-first G8 money-market evidence: dated 6M source variations or last
 * comparable archival interval. OIS, futures, and NZD bank-bill remain distinct.
 * Read-only: no G8/FX scoring, CB decision or backtest input.
 */
(function(root){
 const G8=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const goodDate=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&
  !Number.isNaN(Date.parse(x+'T12:00:00Z'));
 const number=x=>typeof x==='number'&&Number.isFinite(x);
 const fmt=(x,d=2)=>number(x)?(x>0?'+':x<0?'−':'')+Math.abs(x).toFixed(d).replace('.',','):'—';
 const pct=x=>number(x)?x.toFixed(3).replace('.',',')+'%':'n.d.';
 const date=x=>goodDate(x)?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'n.d.';
 const esc=x=>String(x??'').replace(/[&<>"']/g,t=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[t]));
 const deltaDays=(a,b)=>Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5);
 const kind=k=>k==='OIS'?'OIS ufficiali':k==='FUTURES'?'futures ufficiali':
  k==='FUTURES SECONDARI'?'futures secondari':k==='PROXY FUTURES'?'proxy bank-bill':'riferimento monetario';
 function eligible(a,b,ccy){
  if(!a||!b||!goodDate(a.date)||!goodDate(b.date)||a.date>=b.date||
   !number(a.rate)||!number(b.rate))return null;
  if(a.derived||b.derived){
   return ccy==='NZD'&&a.derived===true&&b.derived===false&&
    a.source_class==='BANK_BILL_PROXY_DELTA_REFERENCE'&&
    b.source_class==='BANK_BILL_PROXY'&&a.contract&&a.contract===b.contract?
    'PROXY_RICOSTRUITO':null;
  }
  if(a.source_class!==b.source_class)return null;
  if(a.source_class==='SECONDARY_SAME_CONTRACT')
   return a.contract&&b.contract===a.contract?'CONTRATTO_IDENTICO':null;
  return a.source_class==='OFFICIAL_TENOR'?'TENORE_UFFICIALE':null;
 }
 function latestHistorical(ccy,history,today,window){
  const api=root.FXQuantPricingHistory;
  const h=api?.country?.(history,ccy,60),p=h?.tenors?.['6m'];
  if(!Array.isArray(p)||!goodDate(today))return null;
  const results=[];
  for(let i=1;i<p.length;i++){
   const b=p[i];if(b.date>today)continue;
   for(let j=0;j<i;j++){
    const a=p[j],days=deltaDays(a.date,b.date);
    if(window==='1d'?days<1||days>4:days<5||days>9)continue;
    const method=eligible(a,b,ccy);
    if(!method)continue;
    const bp=Math.round((b.rate-a.rate)*10000)/100;
    results.push({bp,from:a.date,to:b.date,method,
     type:method==='PROXY_RICOSTRUITO'?'PROXY_DELTA_RICOSTRUITO':'STORICO_CONFRONTABILE',
     contract:b.contract||null,window});
   }
  }
  results.sort((a,b)=>b.to.localeCompare(a.to)||
   (window==='1w'?Math.abs(deltaDays(a.from,a.to)-7)-Math.abs(deltaDays(b.from,b.to)-7):
    deltaDays(a.from,a.to)-deltaDays(b.from,b.to)));
  return results[0]||null;
 }
 function read({ccy,today,snapshot,operational,research,nzd,history}){
  if(!G8.includes(ccy))return null;
  const api=root.FXQuantPricingMoves;
  if(!api?.readCurrency)return null;
  const m=api.readCurrency(ccy,snapshot,operational,research,nzd,today);
  const row=m.rows.find(x=>x.tenor==='6m');
  if(!row)return null;
  function movement(window){
   const q=row[window==='1w'?'week':'one'];
   if(q&&number(q.bp)&&goodDate(q.until))
    return {bp:q.bp,to:q.until,from:q.from||null,type:'ULTIMA_FONTE',
     window,method:q.method||'VARIAZIONE_DICHIARATA',contract:row.contract||null};
   return latestHistorical(ccy,history,today,window);
  }
  const one=movement('1d'),week=movement('1w');
  const highlighted=one||week||null;
  const quote=row.rate;
  const label=highlighted?
   '6M '+ccy+' · '+fmt(highlighted.bp,2)+' pb':
   number(quote)?'6M '+ccy+' · '+pct(quote):
   '6M '+ccy+' · archivio storico';
  const short=highlighted?
   (highlighted.type==='ULTIMA_FONTE'?'Δ '+highlighted.window.toUpperCase()+' · ':
    highlighted.type==='PROXY_DELTA_RICOSTRUITO'?'Proxy ricostruito · ':'Storico · ')+
   date(highlighted.from)+' → '+date(highlighted.to):
   'Livello '+date(row.asof)+' · '+kind(m.kind);
  const summary=highlighted?
   'Il riferimento 6M '+ccy+' ('+kind(m.kind)+') è variato di '+
   fmt(highlighted.bp,2)+' punti base nell’intervallo '+
   (highlighted.from?date(highlighted.from)+' → '+date(highlighted.to):
    'terminato il '+date(highlighted.to))+'. '+
   (highlighted.type==='ULTIMA_FONTE'?
    'Variazione della fonte, non una previsione di politica monetaria.':
    highlighted.type==='PROXY_DELTA_RICOSTRUITO'?
    'Riferimento ricostruito dai delta del proxy, non una seconda quotazione osservata.':
    'Ultimo confronto storico disponibile: non equivale a una variazione della seduta corrente.') :
   number(quote)?
    'Il riferimento 6M '+ccy+' ('+kind(m.kind)+') è '+pct(quote)+
    ' al '+date(row.asof)+'. È un livello datato, non una variazione implicita o una previsione dei tassi.':
    'Lo storico monetario è consultabile nella pagina Tassi & OIS, senza inventare variazioni.';
  return {ccy,kind:m.kind,quality:m.quality,source:m.source,rate:quote,asof:row.asof||null,
   one,week,highlighted,label,short,summary};
 }
 function render(x){
  if(!x)return '';
  const datum=(window,data)=>data?'<div class="g8-pricing-metric" data-g8-pricing-window="'+window+
    '" data-g8-pricing-evidence="'+esc(data.type)+'"><span>6M · '+window.toUpperCase()+'</span>'+
    '<strong class="'+(data.bp>0?'up':data.bp<0?'down':'')+'">'+esc(fmt(data.bp,2))+
    ' pb</strong><small>'+esc(data.type==='ULTIMA_FONTE'?'Fonte attuale':
     data.type==='PROXY_DELTA_RICOSTRUITO'?'Proxy ricostruito':'Storico')+
    ' · '+esc(date(data.from))+' → '+esc(date(data.to))+'</small></div>':
    '<div class="g8-pricing-metric" data-g8-pricing-window="'+window+
    '" data-g8-pricing-evidence="LEVEL_CONTEXT"><span>6M · '+window.toUpperCase()+
    ' · LIVELLO</span><strong>'+esc(pct(x.rate))+'</strong><small>'+
    esc(date(x.asof))+' · '+esc(kind(x.kind))+'</small></div>';
  return '<div class="g8-pricing-proof" id="g8-pricing-proof" data-g8-pricing-ccy="'+
   esc(x.ccy)+'"><div class="g8-pricing-proof-title"><span>'+
   'MOVIMENTO DEL 6M · '+esc(kind(x.kind))+'</span>'+
   '<a href="#rates">Approfondisci Tassi & OIS ↗</a></div>'+
   '<div class="g8-pricing-metrics">'+datum('1d',x.one)+datum('1w',x.week)+'</div>'+
   '<details class="g8-pricing-docs"><summary>Apri fonti, date e contratti</summary>'+
   '<p>Fonte: '+esc(x.source||'storico monetario G8')+' · '+esc(x.quality)+
   ' · riferimento '+esc(date(x.asof))+
   '. I contratti futures secondari sono confrontati solo se l’identità è invariata; futures e OIS non sono equivalenti.</p>'+
   '<nav><a href="./rates-pricing-history-v1.json" target="_blank" rel="noopener noreferrer">Storico G8 · JSON</a>'+
   '<a href="../ois-pricing-snapshot.json" target="_blank" rel="noopener noreferrer">Livelli monetari · JSON</a>'+
   '<a href="../ois-same-contract-repricing-research.json" target="_blank" rel="noopener noreferrer">Futures verificati · JSON</a></nav></details></div>';
 }
 const api={read,render,eligible,latestHistorical};
 root.FXQuantG8PricingEvidence=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
