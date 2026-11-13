'use strict';
/* Read-only 8 currency time-series visualizer of pricing tenor histories.
 * No interpolation: gaps and changed listed futures contracts break lines.
 * No backtests/policy signal; NZD references reconstructed and identified.
 */
(function(root){
 const G8=['USD','EUR','GBP','JPY','CHF','AUD','NZD','CAD'];
 const TENORS=['3m','6m','12m'];
 const COLORS={'3m':'#94cfee','6m':'#88e3be','12m':'#efc58a','relative':'#8fded3'};
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const dateOK=x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x)&&!Number.isNaN(Date.parse(x+'T12:00:00Z'));
 const clean=x=>String(x??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[ch]));
 const fmt=(n,d=2)=>num(n)?n.toFixed(d).replace('.',','):'—';
 const dmy=s=>dateOK(s)?s.slice(8,10)+'/'+s.slice(5,7):'—';
 const span=(a,b)=>Math.round((Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/864e5);
 const labelKind=k=>k==='OIS'?'OIS BoE':k==='FUTURES'?'Futures ufficiali':
  k==='FUTURES SECONDARI'?'Futures secondari':k==='PROXY FUTURES'?'Proxy bank-bill':'Fonte da verificare';
 const validRoot=h=>h?.schema==='GMFQ_NEXT_G8_PRICING_HISTORY_V1'&&
  h.eligible_for_fx_engine===false&&h.eligible_for_backtests_as_official_ois===false&&
  h.official_ois_created===false&&h.date_gaps_interpolated===false;
 function country(h,c,days){
  if(!validRoot(h)||!G8.includes(c))return null;
  const r=h.currencies?.[c];
  if(!r||!['OIS','FUTURES','FUTURES SECONDARI','PROXY FUTURES'].includes(r.kind))return null;
  const cutoff=h.as_of,limit=days===0?'0000-01-01':
   new Date(Date.parse(cutoff+'T12:00:00Z')-Number(days)*864e5).toISOString().slice(0,10);
  const ts={};
  for(const t of TENORS){
   const points=Array.isArray(r.tenors?.[t])?r.tenors[t]:[];
   const seen=new Set();
   ts[t]=points.filter(p=>{
    if(!p||!dateOK(p.date)||p.date>cutoff||p.date<limit||!num(p.rate)||
     !['OFFICIAL_TENOR','SECONDARY_SAME_CONTRACT','BANK_BILL_PROXY',
       'BANK_BILL_PROXY_DELTA_REFERENCE'].includes(p.source_class)||typeof p.derived!=='boolean')
     return false;
    if(r.kind==='FUTURES SECONDARI'&&(p.source_class!=='SECONDARY_SAME_CONTRACT'||!p.contract))
     return false;
    if(p.derived&&p.source_class!=='BANK_BILL_PROXY_DELTA_REFERENCE')return false;
    if(seen.has(p.date))return false;
    seen.add(p.date);return true;
   }).sort((a,b)=>a.date.localeCompare(b.date));
  }
  return {ccy:c,kind:r.kind,quality:r.quality,source:r.source,tenors:ts,
   observedDates:new Set(TENORS.flatMap(t=>ts[t].filter(p=>!p.derived).map(p=>p.date))).size,
   derivedReferences:TENORS.flatMap(t=>ts[t].filter(p=>p.derived)).length};
 }
 function connect(a,b){
  if(!a||!b||span(a.date,b.date)<1||span(a.date,b.date)>4)return false;
  if(a.source_class!==b.source_class)return false;
  if(a.source_class==='SECONDARY_SAME_CONTRACT'||a.source_class==='RELATIVE_SAME_DATE')
   return a.contract===b.contract;
  if(a.source_class==='BANK_BILL_PROXY_DELTA_REFERENCE'&&b.source_class==='BANK_BILL_PROXY')
   return true; // One ASX delta-implied, explicitly labeled dotted segment
  if(a.derived||b.derived)return false;
  return true;
 }
 function visualSeries(source,opts={}){
  const all=source.filter(s=>Array.isArray(s.points)&&s.points.length);
  if(!all.length)return '<div class="ois-history-empty">Serie storica non disponibile per le fonti selezionate.</div>';
  const pts=all.flatMap(s=>s.points);
  if(!pts.length)return '<div class="ois-history-empty">Nessuna osservazione con data certificata.</div>';
  const dates=pts.map(p=>p.date).sort(),left=dates[0],right=dates.at(-1);
  const values=pts.map(p=>p.rate),lo=Math.min(...values),hi=Math.max(...values);
  let pad=(hi-lo)*.16;if(pad===0)pad=Math.max(Math.abs(lo)*.009,.02);
  const Y0=hi+pad,Y1=lo-pad;
  const W=720,H=263,L=54,R=18,T=22,B=35;
  const leftMs=Date.parse(left+'T12:00:00Z'),rightMs=Date.parse(right+'T12:00:00Z');
  const DX=Math.max(1,rightMs-leftMs);
  const X=d=>L+(Date.parse(d+'T12:00:00Z')-leftMs)/DX*(W-L-R);
  const Y=v=>T+(Y0-v)/(Y0-Y1)*(H-T-B);
  let body='';
  for(let k=0;k<5;k++){
   const y=T+(H-T-B)*k/4,v=Y0-(Y0-Y1)*k/4;
   body+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y.toFixed(2)+'" y2="'+y.toFixed(2)+
    '" stroke="#385668" stroke-dasharray="3 6"/>'+
    '<text x="'+(L-9)+'" y="'+(y+4)+'" fill="#8eafbd" text-anchor="end" font-size="10">'+
     fmt(v,opts.unit==='pb'?1:2)+'</text>';
  }
  for(const row of all){
   const color=row.color||'#98bed6',points=row.points;
   let segments=[],segment=[];
   const flush=()=>{if(segment.length>1)segments.push([...segment]);segment=[]};
   for(let j=0;j<points.length;j++){
    const p=points[j],prior=points[j-1];
    if(j&&(!connect(prior,p)||row.allowJumps===false&&prior.contract!==p.contract)){
     flush();
    }
    segment.push(p);
   }
   flush();
   for(const seg of segments)body+='<polyline fill="none" stroke="'+color+
    '" stroke-width="2.5"'+(seg.some(p=>p.derived)?' stroke-dasharray="5 5"':'')+
    ' stroke-linejoin="round" stroke-linecap="round" points="'+
    seg.map(p=>X(p.date).toFixed(2)+','+Y(p.rate).toFixed(2)).join(' ')+'"/>';
   for(const p of points){
    const xx=X(p.date),yy=Y(p.rate);
    body+='<circle cx="'+xx.toFixed(2)+'" cy="'+yy.toFixed(2)+
     '" r="'+(p.derived?'3.5':'3')+'" fill="'+(p.derived?'#142c3b':color)+
     '" stroke="'+color+'" stroke-width="'+(p.derived?'2.4':'1')+'"><title>'+
     clean(row.name)+' · '+clean(p.date)+' · '+fmt(p.rate,opts.unit==='pb'?1:3)+
     (opts.unit==='pb'?' pb':'%')+
     (p.contract?' · '+clean(p.contract):'')+
     (p.derived?' · LIVELLO RICOSTRUITO (NON OSSERVATO)':'')+'</title></circle>';
   }
  }
  body+='<text x="'+L+'" y="'+(H-10)+'" fill="#9db8c7" font-size="10">'+dmy(left)+
   '</text><text x="'+(W-R)+'" y="'+(H-10)+'" text-anchor="end" fill="#9db8c7" font-size="10">'+dmy(right)+'</text>';
  return '<div class="ois-history-chart"><svg viewBox="0 0 720 263" role="img" aria-label="'+
   clean(opts.name||'Storico delle quotazioni osservate dei tenori')+'">'+body+'</svg></div>'+
   '<div class="ois-history-legend">'+all.map(s=>'<span><i style="background:'+s.color+
    '"></i>'+clean(s.name)+'</span>').join('')+'</div>';
 }
 function relative(a,b){
  const m=new Map((b?.tenors?.['6m']||[]).map(p=>[p.date,p]));
  return (a?.tenors?.['6m']||[]).flatMap(p=>{
   const q=m.get(p.date);
   if(!q||p.derived||q.derived)return [];
   return [{date:p.date,rate:Math.round((p.rate-q.rate)*1e4)/100,
    contract:String(p.contract||'')+' vs '+String(q.contract||''),
    derived:false,source_class:'RELATIVE_SAME_DATE'}];
  });
 }
 function spreadLine(points){ return points; } // Keep both contract IDs; lines break on rollover.
 function historicalMoves(r){
  const arr=r.tenors['6m'],out=[];
  for(let i=1;i<arr.length;i++){
   const a=arr[i-1],b=arr[i];
   if(!connect(a,b))continue;
   out.push({date:b.date,bp:Math.round((b.rate-a.rate)*10000)/100,
    source_class:b.source_class,contract:b.contract});
  }
  return out.slice(-7);
 }
 function sparkline(row){
  const pts=row?.tenors?.['6m']||[];
  if(!pts.length)return '<span class="ois-mini-empty">n.d.</span>';
  const w=132,h=35,L=3,R=2,T=3,B=3,lo=Math.min(...pts.map(p=>p.rate)),hi=Math.max(...pts.map(p=>p.rate));
  const spanY=Math.max(.02,hi-lo),minX=Date.parse(pts[0].date+'T12:00:00Z');
  const spanX=Math.max(1,Date.parse(pts.at(-1).date+'T12:00:00Z')-minX);
  const x=p=>L+(Date.parse(p.date+'T12:00:00Z')-minX)/spanX*(w-L-R);
  const y=p=>T+(hi-p.rate)/spanY*(h-T-B);
  let body='';
  for(let i=1;i<pts.length;i++){
   if(!connect(pts[i-1],pts[i]))continue;
   body+='<line x1="'+x(pts[i-1]).toFixed(1)+'" y1="'+y(pts[i-1]).toFixed(1)+
    '" x2="'+x(pts[i]).toFixed(1)+'" y2="'+y(pts[i]).toFixed(1)+
    '" stroke="#87dcbf" stroke-width="2.1"/>';
  }
  for(const p of pts)body+='<circle cx="'+x(p).toFixed(1)+'" cy="'+y(p).toFixed(1)+
   '" r="'+(p.derived?'2.4':'1.8')+'" fill="'+(p.derived?'#1b3a4b':'#87dcbf')+
   '" stroke="#87dcbf" stroke-width="1"><title>'+clean(p.date)+' · '+fmt(p.rate,3)+'%</title></circle>';
  return '<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" role="img" aria-label="Storico 6M">'+body+'</svg>';
 }
 function render({history,ccy='USD',other='EUR',window=40}){
  if(!validRoot(history))return '<section class="rates-pricing-history" id="rates-pricing-history"><div class="ois-history-empty">Lo storico G8 non è stato verificato: nessun grafico generato.</div></section>';
  const days=[14,30,60].includes(+window)?+window:40;
  const c=country(history,ccy,days),peer=country(history,other,days);
  if(!c)return '<section class="rates-pricing-history"><div class="ois-history-empty">Nessuna serie disponibile.</div></section>';
  const arr=TENORS.map(t=>({name:t.toUpperCase(),color:COLORS[t],points:c.tenors[t]}));
  const dates=new Set(TENORS.flatMap(t=>c.tenors[t].map(p=>p.date))).size;
  const last=TENORS.flatMap(t=>c.tenors[t]).map(p=>p.date).sort().at(-1);
  const spread=other!==ccy?relative(c,peer):[];
  const moves=historicalMoves(c);
  const g8=G8.map(k=>{
   const g=country(history,k,days);
   return '<button type="button" data-rate-ccy="'+k+'" class="ois-history-currency '+(k===ccy?'active':'')+
    '" aria-pressed="'+String(k===ccy)+'" aria-label="Visualizza storico monetario '+k+'">'+
    '<span class="ois-history-currency-label"><b>'+k+'</b><small>'+clean(labelKind(g?.kind))+'</small></span>'+
    '<span class="ois-history-currency-plot">'+sparkline(g)+'</span>'+
    '<span class="ois-history-currency-metric"><strong>'+fmt(g?.tenors?.['6m']?.at(-1)?.rate,3)+'%</strong>'+
    '<small>'+String(g?.observedDates||0)+' date</small></span></button>';
  }).join('');
  return '<section class="rates-pricing-history" id="rates-pricing-history" data-history-currency="'+ccy+
   '" data-history-asof="'+clean(history.as_of)+'">'+
   '<div class="rates-section-head"><div><span class="chapter-kicker">STORICO PRICING · G8 · 3M/6M/12M</span>'+
   '<h2>Non solo il livello. <em>Come si è evoluta la curva?</em></h2></div>'+
   '<p>Serie storiche archiviate, con i giorni mancanti lasciati vuoti. Contratti futures diversi non vengono uniti artificialmente.</p></div>'+
   '<div class="ois-history-top"><div><b>'+ccy+' · '+clean(labelKind(c.kind))+
   '</b><small>'+clean(c.quality)+' · Ultimo dato '+dmy(last)+
   ' · '+dates+' date in finestra</small></div>'+
   '<div class="pill-controls">'+[[14,'14 giorni'],[30,'30 giorni'],[60,'60 giorni']].map(([d,l])=>
    '<button type="button" data-rs-history-window="'+d+'" class="pill '+(days===d?'active':'')+
    '" aria-pressed="'+String(days===d)+'">'+l+'</button>').join('')+'</div></div>'+
   '<div class="ois-history-chartgrid"><article class="ois-history-primary"><span class="micro-over">EVOLUZIONE DEI LIVELLI · '+ccy+'</span>'+
   '<h3>Tre tenori nella stessa finestra temporale</h3>'+
   visualSeries(arr,{name:'Storico per scadenza '+ccy,unit:'%'})+
   '<p class="rates-plot-note">'+(c.kind==='OIS'?
    'Curve OIS BoE: punti a termine 3M, 6M, 12M provenienti dallo storico ufficiale.':
    c.kind==='FUTURES SECONDARI'?
    'Quotazioni futures secondarie: linee interrotte a ogni cambio di contratto o giorno non osservato. Non sono OIS.':
    c.kind==='PROXY FUTURES'?
    'Proxy NZD: un solo livello indipendente e riferimenti 1D/1W ricostruiti dai delta ASX, non nuove osservazioni.':
    'Futures ufficiali: andamento dei tenori rappresentativi; senza identità contrattuale storica non equivale alla performance dello stesso contratto.')+
   '</p></article>'+
   '<article class="ois-history-secondary"><span class="micro-over">SPREAD 6M · '+ccy+' − '+other+'</span>'+
   '<h3>Come cambia il vantaggio relativo?</h3>'+
   (spread.length>=2?visualSeries([{name:ccy+' − '+other+' · 6M',color:COLORS.relative,
     points:spreadLine(spread)}],{name:'Differenziale indicativo 6M sulle date comuni',unit:'pb'}):
    '<div class="ois-history-empty">Solo '+spread.length+' data comune disponibile: grafico non interpretabile.</div>')+
   '<p class="rates-plot-note">Differenza tra i livelli 6M degli strumenti disponibili, <strong>solo sulle date comuni</strong>. OIS, futures e proxy hanno basi diverse: è una misura indicativa, non uno spread OIS negoziabile né un segnale FX.</p>'+
   '<details class="ois-history-evidence"><summary>Fonte, ampiezza e criteri dello storico</summary><div><p>'+
    clean(c.source)+' · '+clean(c.quality)+'</p><p>'+
    c.observedDates+' date osservate in finestra · '+c.derivedReferences+
    ' riferimenti ricostruiti · '+spread.length+' date comuni del differenziale.</p>'+
    '<p>Archivio retrospettivo: data della quotazione e data in cui è stata acquisita non coincidono sempre. Sono esclusi conflitti su contratti futures; lo storico non è un backtest point-in-time.</p></div></details>'+
   '</article></div>'+
   '<div class="ois-history-lower"><div><span class="micro-over">6M · CAMBIAMENTI OSSERVATI NELLO STORICO</span>'+
   '<h3>Variazioni fra due rilevazioni confrontabili</h3>'+
   (moves.length?'<div class="ois-history-moves">'+moves.map(m=>{
    const up=m.bp>0,down=m.bp<0,size=Math.min(100,Math.abs(m.bp)/20*100);
    return '<div class="ois-history-move"><time>'+dmy(m.date)+'</time><span class="ois-history-delta-bar"><i style="width:'+size.toFixed(1)+'%;background:'+(up?'#7ed7b5':down?'#df909b':'#87abc5')+'"></i></span>'+
     '<strong class="'+(up?'up':down?'down':'')+'">'+(up?'+':'')+fmt(m.bp,1)+' pb</strong></div>';
   }).join('')+'</div>':
   '<p class="ois-history-no-moves">Lo storico disponibile non contiene intervalli omogenei sufficienti per questo grafico delle variazioni 6M.</p>')+
   '<small>Le barre sono descrittive; per futures senza codice di contratto nello storico, non equivalgono a un repricing certificato del medesimo contratto.</small></div></div>'+
   '<div class="ois-history-g8"><div class="rates-section-head"><div><span class="chapter-kicker">TUTTE LE VALUTE · COPERTURA GRAFICA</span>'+
   '<h3>Panoramica G8: seleziona la valuta da approfondire</h3></div><p>Sparklines dei 6M. «Date» indica le osservazioni archiviate, non la profondità di una curva OIS ufficiale.</p></div>'+
   '<div class="ois-history-currency-grid">'+g8+'</div></div>'+
   '<p class="ois-history-footer">Fonte: archivio append-only del desk · conflitti quotazioni secondarie esclusi ('+
   Number(history.excluded_conflicted_contract_days||0)+
   ' identità contratto/data). I punti NZD ricostruiti sono marcati come tali. Dati raccolti retrospettivamente: nessuna interpolazione né attribuzione automatica di policy surprises o segnali FX.</p></section>';
 }
 const api={country,connect,relative,render,historicalMoves,visualSeries};
 root.FXQuantPricingHistory=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
