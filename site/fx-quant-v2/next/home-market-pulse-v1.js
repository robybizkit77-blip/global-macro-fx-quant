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
 function render({feed,risk,esc,date,dayNow}={}){
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
  const evidence=Array.isArray(feed.news)?feed.news:[];
  const sourced=n=>Array.isArray(n?.sources)&&n.sources.some(u=>link(u)&&
   feed.provenance?.web_source_urls?.includes(u));
  const fx=evidence.find(n=>n?.market_area==='FOREX'&&recent(n.published_date)&&
   sourced(n)&&/Forza del dollaro sui cross EUR\/USD e USD\/JPY/i.test(n.headline));
  if(fx)add('currencies','FORZA FX RELATIVA','USD contro EUR e JPY','USD ↑',
   'Fixing BCE',fx.published_date,'fx','', 'Direzione osservata');
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
  const commod=evidence.find(n=>n?.market_area==='COMMODITIES'&&recent(n.published_date)&&
   sourced(n)&&/Oro e petrolio/i.test(n.headline));
  if(commod&&/Oro in rialzo e petrolio in calo/i.test(feed.desk_judgment||'')&&
    /oro e WTI/i.test(commod.analysis||'')){
   add('risk','MATERIE PRIME','Oro / WTI','Oro ↑ · WTI ↓','Futures, proxy',
    commod.published_date,'mixed','','Fonti secondarie');
  }
  if(items.length<2)return '';
  return '<section class="hourly-market-pulse" aria-label="Osservazioni di mercato pubblicate, non dati in tempo reale">'+
   '<div class="hourly-market-pulse-head"><div><span class="morning-section-label">IL MERCATO IN UN COLPO D’OCCHIO</span>'+
   '<h2>Ultime osservazioni</h2></div><p>Fonti datate · Confronti non intraday</p></div>'+
   '<div class="hourly-pulse-track">'+items.join('')+'</div></section>';
 }
 root.FXQuantHomePulse={render};
})(typeof window!=='undefined'?window:globalThis);
