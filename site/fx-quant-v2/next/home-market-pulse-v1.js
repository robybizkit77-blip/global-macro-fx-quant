'use strict';
/* A purely visual, source-dated, read-only market ribbon for FX Quant Next.
 * Uses the existing published market research, not new API calls.
 * Never labels historical closes as live quotes or market positioning.
 */
(function(root){
 const day=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s);
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const link=s=>typeof s==='string'&&/^https:\/\/[^/\s@]+\.[^/\s@]+/.test(s);
 const age=(a,b)=>(Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/86400000;
 const fmt=(x,d=2)=>Math.abs(x).toLocaleString('it-IT',{minimumFractionDigits:d,maximumFractionDigits:d});
 const signed=(x,d=2,u='')=>(x>0?'+':x<0?'−':'')+fmt(x,d)+u;
 function render({feed,risk,currencyPrices,esc,date,dayNow}={}){
  if(!feed||!risk||typeof esc!=='function'||typeof dayNow!=='function'||typeof date!=='function')return '';
  const today=dayNow(),safe=x=>esc(String(x??'')),items=[];
  const recent=x=>day(x)&&x<=today&&age(x,today)>=0&&age(x,today)<=7;
  const isSourced=x=>x&&x.quality==='PUBLISHED_SOURCE_RESEARCH_ONLY'&&
   x.not_intraday===true&&recent(x.date)&&link(x.source_url)&&num(x.value)&&num(x.previous);
  const chart=x=>{
   const pts=(Array.isArray(x.history)?x.history:[]).filter(a=>Array.isArray(a)&&
    day(a[0])&&a[0]<=x.date&&num(a[1])).slice(-12);
   if(pts.length<3)return '';
   const ys=pts.map(a=>a[1]),lo=Math.min(...ys),spread=Math.max(Math.max(...ys)-lo,.000001);
   const points=ys.map((v,i)=>(4+i*100/(ys.length-1)).toFixed(1)+','+
    (36-(v-lo)/spread*28).toFixed(1)).join(' ');
   return '<svg class="hourly-pulse-spark" viewBox="0 0 108 44" aria-hidden="true" focusable="false">'+
    '<polyline points="'+points+'" fill="none" stroke="currentColor" stroke-width="2.6"'+
    ' stroke-linejoin="round" stroke-linecap="round"/></svg>';
  };
  const add=(route,area,label,value,delta,asof,state='neutral',spark='',note='')=>{
   if(!recent(asof))return;
   items.push('<a class="hourly-pulse-tile hourly-pulse-'+state+'" href="#'+route+'"'+
    ' aria-label="'+safe(label+': '+value+'; '+delta+'; rilevazione '+date(asof))+'">'+
    '<div class="hourly-pulse-tile-top"><span>'+safe(area)+'</span><time>'+safe(date(asof))+'</time></div>'+
    '<div class="hourly-pulse-tile-middle"><strong>'+safe(value)+'</strong>'+spark+'</div>'+
    '<div class="hourly-pulse-tile-bottom"><span>'+safe(label)+'</span><b>'+safe(delta)+'</b></div>'+
    (note?'<small>'+safe(note)+'</small>':'')+'</a>');
  };
  // One-fixing ECB G8 comparison: the USD arrow is determined by TWO numeric
  // cross-rate changes, never by a headline or a narrative phrase.
  // ECB quotes units of foreign currency per 1 EUR.
  const official=currencyPrices?.schema==='GMFQ_ECB_G8_PRICE_HISTORY_V1'&&
   currencyPrices.status==='CURRENT_OFFICIAL_HISTORY'&&
   currencyPrices.base==='EUR'&&
   currencyPrices.source_url==='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml';
  const rows=Array.isArray(currencyPrices?.rows)?currencyPrices.rows:[];
  const prev=rows.at(-2),last=rows.at(-1);
  const validFixing=r=>r&&day(r.Date)&&num(r.USD)&&r.USD>0&&num(r.JPY)&&r.JPY>0;
  if(official&&validFixing(prev)&&validFixing(last)&&prev.Date<last.Date&&
     currencyPrices.last_as_of===last.Date&&recent(last.Date)&&
     prev.Date<=today){
   // USD/EUR strength is reciprocal to EUR/USD. USD/JPY is derived from two
   // EUR-based ECB fixes on exactly the same dates (JPY per USD).
   const eur=(prev.USD/last.USD-1)*100;
   const jpy=((last.JPY/last.USD)/(prev.JPY/prev.USD)-1)*100;
   const eps=.005; // Below half the 0.01% display precision: no directional claim.
   const bothUp=eur>eps&&jpy>eps,bothDown=eur < -eps&&jpy < -eps;
   const flat=Math.abs(eur)<=eps&&Math.abs(jpy)<=eps;
   const value=bothUp?'USD ↑':bothDown?'USD ↓':flat?'USD stabile':'USD misto';
   const tone=bothUp?'fx':bothDown?'adverse':'neutral';
   add('currencies','FORZA FX RELATIVA','USD vs EUR / JPY',value,
    'EUR '+signed(eur,2,'%')+' · JPY '+signed(jpy,2,'%'),
    last.Date,tone,'','BCE · 2 confronti, non indice USD');
  }
  const s=risk.streams||{},sp=s.SP500,vix=s.VIX,hy=s.HY_OAS;
  if(isSourced(sp)&&sp.previous!==0){
   const n=(sp.value-sp.previous)/Math.abs(sp.previous)*100;
   add('risk','AZIONARIO','S&P 500',signed(n,2,'%'),'Ultima chiusura',sp.date,
    n>0?'constructive':n<0?'adverse':'neutral',chart(sp),'Dato pubblicato');
  }
  if(isSourced(vix)){
   const n=vix.value-vix.previous;
   add('risk','VOLATILITÀ','Indice VIX',fmt(vix.value),signed(n,2,' pt'),vix.date,
    n>0?'caution':n<0?'constructive':'neutral',chart(vix),'Chiusura Cboe');
  }
  if(isSourced(hy)){
   const bp=(hy.value-hy.previous)*100;
   add('risk','CREDITO','Spread HY',fmt(hy.value)+'%',signed(bp,0,' pb'),hy.date,
    bp>0?'caution':bp<0?'constructive':'neutral',chart(hy),'OAS: spread, non rendimento');
  }
  // Omit commodities until matched, source-dated numerical gold and WTI
  // observations are present. Narrative headlines alone cannot prove direction.
  if(items.length<2)return '';
  return '<section class="hourly-market-pulse" aria-label="Osservazioni di mercato pubblicate, non dati in tempo reale">'+
   '<div class="hourly-market-pulse-head"><div><span class="morning-section-label">IL MERCATO IN UN COLPO D’OCCHIO</span>'+
   '<h2>Ultime osservazioni</h2></div><p>Fonti datate · Confronti non intraday</p></div>'+
   '<div class="hourly-pulse-track">'+items.join('')+'</div></section>';
 }
 root.FXQuantHomePulse={render};
})(typeof window!=='undefined'?window:globalThis);
