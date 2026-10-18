/* Global Macro FX Quant · Control Room v10
   Additive UX correction: invisible-native card navigation, in-app ECB DXY synthetic,
   eight-country rates with flagged model estimates, eight-country pricing context.
   This module never changes canonical datasets, scoring, risk, signals or templates. */
(() => {
'use strict';
const frame=document.getElementById('gmfq-page');
if(!frame)return;
const ROOT='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const FLAG={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',AUD:'🇦🇺',CAD:'🇨🇦',NZD:'🇳🇿',CHF:'🇨🇭'};
const BANK={USD:'Fed',EUR:'ECB',GBP:'BoE',JPY:'BoJ',AUD:'RBA',CAD:'BoC',NZD:'RBNZ',CHF:'SNB'};
const COLOR={USD:'#e2e9f3',EUR:'#448df8',GBP:'#f15f7a',JPY:'#eec866',AUD:'#49d7a3',CAD:'#76bbff',NZD:'#bfa3ff',CHF:'#e4a1dc'};
const destinations=[
 ['.gridtop > .panel:nth-child(2)','#/tassi?focus=ois','Tassi e curve OIS'],
 ['.gridtop > .panel:nth-child(3)','#/tassi?focus=curve','Curve dei rendimenti'],
 ['.mid > .panel:nth-child(1)','#/valute','Forza relativa valutaria'],
 ['.mid > .panel:nth-child(2)','#/tassi?focus=2y','Rendimenti a 2 anni'],
 ['.mid > .panel:nth-child(3)','#/tassi?focus=spread','Spread governativi 2Y'],
 ['.bottom > .panel:nth-child(1)','#/screener','Screener delle 28 coppie'],
 ['.bottom > .panel:nth-child(2)','#/macro','Analisi dei messaggi Macro']
];
let dxyFeed=null;
function route(){return (location.hash||'#/home').replace(/^#\/?/,'').split('?')[0]}
function home(){return ['home','index.html'].includes(route())}
function num(v){return typeof v==='number'&&Number.isFinite(v)?v:null}
function fmt(v,d=2){return num(v)===null?'—':v.toFixed(d)}
function fresh(date,max=4){if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))return false;const today=new Date();const days=(Date.UTC(today.getUTCFullYear(),today.getUTCMonth(),today.getUTCDate())-Date.parse(date+'T00:00:00Z'))/86400000;return days>=0&&days<=max}
function htmlEscape(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function go(url){if(url&&url.startsWith('#/')&&location.hash!==url)location.hash=url}
async function feed(file){const c=new AbortController(),t=setTimeout(()=>c.abort(),12000);try{const r=await fetch(ROOT+file,{cache:'no-store',signal:c.signal});if(!r.ok)throw Error('HTTP '+r.status);return await r.json()}finally{clearTimeout(t)}}
function navigation(doc){
  for(const [selector,link,title] of destinations){
    const e=doc.querySelector(selector);if(!e)continue;
    e.dataset.gmfqDestination=link;e.setAttribute('role','link');e.tabIndex=0;e.setAttribute('aria-label','Apri '+title);
  }
  doc.body.addEventListener('click',e=>{
    if(e.defaultPrevented||e.target.closest('a,button,input,select,textarea'))return;
    const tile=e.target.closest('#valute .cc');
    if(tile){
      const ccy=tile.dataset.filter;
      if(ccy==='DXY'){openDxy(doc);return}
      if(FX.includes(ccy)){go('#/valute?ccy='+ccy);return}
    }
    const pricing=e.target.closest('#ois .oisrow');
    if(pricing){const ccy=pricing.dataset.ccy;if(FX.includes(ccy)){go('#/banche?ccy='+ccy);return}}
    const pair=e.target.closest('#pairs tr[data-filter]');
    if(pair){const p=(pair.dataset.filter||'').replace(/[^A-Z]/g,'');if(/^[A-Z]{6}$/.test(p)){go('#/screener?pair='+p);return}}
    const panel=e.target.closest('[data-gmfq-destination]');
    if(panel)go(panel.dataset.gmfqDestination);
  });
  doc.body.addEventListener('keydown',e=>{
    if(!['Enter',' '].includes(e.key)||e.target.closest('a,button,input,select,textarea'))return;
    const tile=e.target.closest('#valute .cc');
    if(tile&&e.target===tile){e.preventDefault();const k=tile.dataset.filter;k==='DXY'?openDxy(doc):FX.includes(k)&&go('#/valute?ccy='+k);return}
    const pricing=e.target.closest('#ois .oisrow');
    if(pricing&&e.target===pricing){e.preventDefault();go('#/banche?ccy='+pricing.dataset.ccy);return}
    const pair=e.target.closest('#pairs tr[data-filter]');
    if(pair&&e.target===pair){e.preventDefault();go('#/screener?pair='+pair.dataset.filter);return}
    const panel=e.target.closest('[data-gmfq-destination]');
    if(panel&&panel===e.target){e.preventDefault();go(panel.dataset.gmfqDestination)}
  });
}
function style(doc){
 const s=doc.createElement('style');s.id='gmfq-desk-polish-v11';
 s.textContent=`
  .panel[data-gmfq-destination],#valute .cc,#ois .oisrow,#pairs tr[data-filter]{cursor:pointer}
  .panel[data-gmfq-destination]:hover .heading{color:#f0ddae}
  .panel[data-gmfq-destination]:focus-visible,#valute .cc:focus-visible,
  #ois .oisrow:focus-visible,#pairs tr[data-filter]:focus-visible {outline:2px solid #d6b873;outline-offset:-3px}
  .gmfq-quiet-meta{display:block;color:#9eb1c1;font:10px/1.4 Arial,sans-serif;margin-top:3px}
  .gmfq-est-flag{fill:#eec66e;font-size:10px}
  .gmfq-legend-row{display:flex;gap:6px 11px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
  .gmfq-legend-item{font:10px/1.3 Arial,sans-serif;white-space:nowrap;color:#c5d2df}
  .gmfq-legend-item i{display:inline-block;width:10px;height:2px;vertical-align:middle;margin-right:3px}
  .gmfq-legend-item.est{color:#e7c27a}
  .gmfq-chart-note{color:#93a7b8;font:10px/1.35 Arial,sans-serif;margin-top:5px}
  .gmfq-est-note{color:#e0bb6c}
  .gmfq-dxy-dialog{border:1px solid #29465b;border-radius:10px;color:#e4edf5;background:#071827;
    max-width:min(590px,94vw);width:94vw;padding:22px 23px;box-shadow:0 24px 65px #000a}
  .gmfq-dxy-dialog::backdrop{background:#020a14be}
  .gmfq-dxy-dialog h2{font:600 20px/1.2 Arial,sans-serif;color:#f2f7fb;margin:0 0 10px}
  .gmfq-dxy-dialog p{font:13px/1.5 Arial,sans-serif;color:#b0c3d2;margin:7px 0}
  .gmfq-dxy-dialog .gmfq-dxy-val{font:600 36px/1.1 Arial,sans-serif;color:#f0f6fe;font-variant-numeric:tabular-nums}
  .gmfq-dxy-dialog button{border:1px solid #435f73;border-radius:6px;color:#dce9f3;background:#12283b;padding:8px 14px;cursor:pointer}
  .gmfq-dxy-dialog .gmfq-source{color:#e6c778;font-size:12px}
  .gmfq-dxy-dialog a{color:#e6c778;text-decoration:underline}
  .gmfq-dxy-dialog svg{width:100%;height:145px}
  .gmfq-dxy-dialog .gmfq-close{float:right}
  /* Eight pricing lanes must fit the original 260px panel without clipping. */
  .gridtop #ois {padding:1px 7px 0}
  .gridtop #ois .oisrow{grid-template-columns:62px minmax(0,1fr) 47px;gap:5px;
    margin:2px 0;min-height:18px;font-size:11px}
  .gridtop #ois .oisrow:first-child{margin-top:3px}
  .gridtop #ois .oisrow .track{height:14px}
  .gridtop #ois .oisrow strong{font-size:11px}
  .gridtop #ois .oisrow .miniquality{font-size:9px;line-height:1.1}
  .gridtop #ois .oisnote{font-size:9px;line-height:1.2;margin-top:3px}
  .gridtop #ois .gmfq-nzd-proxy{border-top:1px solid #263b49;padding-top:2px}
  .gridtop #ois .gmfq-nzd-proxy .fill{background:linear-gradient(90deg,#6c5b36,#dabb6c)}
  .gridtop .yieldpanel .legend-y{margin:0 3px}
  .gridtop .yieldpanel .gmfq-legend-row{gap:2px 6px;justify-content:center}
  .gridtop .yieldpanel .gmfq-legend-row .gmfq-legend-item{font-size:9px}
  .gridtop .yieldpanel .gmfq-legend-row span:before{display:none}
  .gridtop .yieldpanel .yieldplot{height:166px}
  .gridtop .yieldpanel .gmfq-chart-note{margin:1px 10px;font-size:9px;line-height:1.1}
 `;
 doc.head.appendChild(s);
}
function dateHistory(x,which){
 const h=x?.[which];if(!h)return[];
 const arr=Array.isArray(h)?h.map(p=>({date:p.date,v:num(p.value)})):Array.isArray(h.dates)?h.dates.map((date,i)=>({date,v:num(h.values?.[i])})):[];
 return arr.filter(p=>/^\d{4}-\d{2}-\d{2}$/.test(p.date||'')&&p.v!==null&&(!x?.date||p.date<=x.date)).sort((a,b)=>a.date.localeCompare(b.date))
}
function estimate(target,ref,which){
 const original=target?.[which==='history2'?'2Y':'10Y'];const base=ref?.[which==='history2'?'2Y':'10Y'];
 if(num(original)===null||num(base)===null||!target.date||!fresh(ref.date,5))return null;
 const a=dateHistory(target,which),b=dateHistory(ref,which);const refMap=new Map(b.map(x=>[x.date,x.v]));
 const common=a.filter(x=>refMap.has(x.date)&&x.date<=target.date).slice(-125);
 if(common.length<45)return null;
 const diffs=[];
 for(let i=1;i<common.length;i++){
   const y=common[i].v-common[i-1].v,dx=refMap.get(common[i].date)-refMap.get(common[i-1].date);
   if(Math.abs(dx)<1&&Math.abs(y)<1)diffs.push([dx,y]);
 }
 if(diffs.length<40)return null;
 const xm=diffs.reduce((s,x)=>s+x[0],0)/diffs.length,ym=diffs.reduce((s,x)=>s+x[1],0)/diffs.length;
 const cov=diffs.reduce((s,x)=>s+(x[0]-xm)*(x[1]-ym),0),variance=diffs.reduce((s,x)=>s+(x[0]-xm)**2,0);
 if(variance<.001)return null;
 const beta=Math.max(-.5,Math.min(2.5,cov/variance));
 const anchor=common.at(-1),rateThen=refMap.get(anchor.date),gap=(Date.parse(ref.date)-Date.parse(target.date))/86400000;
 if(gap<=0||gap>35)return null;
 const value=original+beta*(base-rateThen);
 if(!Number.isFinite(value)||Math.abs(value-original)>1.5||value< -3||value>18)return null;
 return {v:value,asof:ref.date,model:'stima β '+(ref===undefined?'':(target===null?'':'fattoriale')),beta:beta,origin:target.date,refDate:anchor.date};
}
function ratesAll(raw){
 const cur={};
 for(const c of FX){
   const x=raw?.[c],recent=x&&fresh(x.date,4)&&String(x.quality||'').includes('OFFICIAL');
   cur[c]={src:x,date:x?.date||null,v2:recent?num(x['2Y']):null,v10:recent?num(x['10Y']):null,
     h2:dateHistory(x,'history2'),h10:dateHistory(x,'history10'),estimate2:false,estimate10:false};
 }
 for(const [k,proxy] of [['CHF','EUR'],['NZD','AUD']]){
   const a=cur[k],ref=raw?.[proxy];
   if(a.v2===null){const m=estimate(raw?.[k],ref,'history2');if(m){a.v2=m.v2??m.v;a.estimate2=true;a.estimatedAsOf2=m.asof;a.proxy=proxy;a.beta2=m.beta;}}
   if(a.v10===null){const m=estimate(raw?.[k],ref,'history10');if(m){a.v10=m.v;a.estimate10=true;a.estimatedAsOf10=m.asof;a.proxy=proxy;a.beta10=m.beta;}}
 }
 return cur;
}
function yieldChart(doc,all,which='2Y'){
 const key=which==='2Y'?'h2':'h10',currentKey=which==='2Y'?'v2':'v10';
 const data=FX.map(c=>({c,series:all[c][key].slice(-90),now:all[c][currentKey],est:which==='2Y'?all[c].estimate2:all[c].estimate10,latest:which==='2Y'?(all[c].estimatedAsOf2||all[c].date):(all[c].estimatedAsOf10||all[c].date)})).filter(x=>x.series.length>4);
 if(!data.length)return;
 const allDays=data.flatMap(x=>x.series.map(p=>p.date));
 const min=allDays.sort()[0],max=[...allDays,...data.map(x=>x.latest).filter(Boolean)].sort().at(-1);
 let vals=data.flatMap(x=>x.series.map(p=>p.v));vals.push(...data.map(x=>x.now).filter(x=>x!==null));
 const bottom=Math.min(...vals)-.18,top=Math.max(...vals)+.18,W=320,H=176,L=28,R=8,T=12,B=12;
 const td=Date.parse(max)-Date.parse(min)||1,span=top-bottom||1;
 const xx=d=>L+(W-L-R)*(Date.parse(d)-Date.parse(min))/td,yy=v=>T+(H-T-B)*(top-v)/span;
 let svg='';
 for(let i=0;i<=3;i++){const y=T+i*(H-T-B)/3;svg+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke="#243c4c" stroke-width=".8"/><text x="${L-4}" y="${y+3}" text-anchor="end" fill="#8fa8bb" font-size="9">${(top-i*span/3).toFixed(1)}</text>`;}
 for(const x of data){
   const pts=x.series.map(p=>`${xx(p.date).toFixed(1)},${yy(p.v).toFixed(1)}`).join(' ');
   svg+=`<polyline points="${pts}" fill="none" stroke="${COLOR[x.c]}" stroke-width="1.4"/>`;
   if(x.now!==null && x.latest && x.latest>x.series.at(-1).date && !x.est){const last=x.series.at(-1);svg+=`<line x1="${xx(last.date)}" y1="${yy(last.v)}" x2="${xx(x.latest)}" y2="${yy(x.now)}" stroke="${COLOR[x.c]}" stroke-width="1.2" stroke-dasharray="2 3"/><circle cx="${xx(x.latest)}" cy="${yy(x.now)}" r="2.2" fill="${COLOR[x.c]}"/>`;}
   if(x.est&&x.now!==null){const last=x.series.at(-1);svg+=`<line x1="${xx(last.date)}" y1="${yy(last.v)}" x2="${xx(x.latest)}" y2="${yy(x.now)}" stroke="#e8c46d" stroke-width="1.8" stroke-dasharray="3 3"/><circle cx="${xx(x.latest)}" cy="${yy(x.now)}" r="2.6" fill="#e8c46d"/>`}
 }
 svg+=`<text x="${L}" y="${H-2}" fill="#819bad" font-size="9">${min.slice(5)}</text><text x="${W-R}" y="${H-2}" text-anchor="end" fill="#819bad" font-size="9">${max.slice(5)}</text>`;
 const curve=doc.getElementById('curves'),legend=doc.getElementById('ylegend');
 if(!curve||!legend)return;
 curve.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Serie ${which} di tutte le otto valute G8; eventuali tratti stimati tratteggiati">${svg}</svg>`;
 const chosen=legend.dataset.gmfqYieldMode||'2Y';
 legend.innerHTML=`<div class="gmfq-legend-row">${data.map(x=>`<span class="gmfq-legend-item ${x.est?'est':''}" title="${x.est?'Tratto terminale stimato':''}"><i style="background:${COLOR[x.c]}"></i>${x.c}${x.est?'*':''}</span>`).join('')}
 <button type="button" data-gmfq-tenor="2Y" aria-pressed="${chosen==='2Y'}" style="background:transparent;border:0;color:${chosen==='2Y'?'#f1ca6d':'#93b1c3'};cursor:pointer;padding:0 3px">2Y</button>
 <button type="button" data-gmfq-tenor="10Y" aria-pressed="${chosen==='10Y'}" style="background:transparent;border:0;color:${chosen==='10Y'?'#f1ca6d':'#93b1c3'};cursor:pointer;padding:0 3px">10Y</button></div>`;
 const note=curve.parentElement?.querySelector('.gmfq-chart-note')||doc.createElement('div');
 note.className='gmfq-chart-note';note.textContent='Serie storiche tutte G8. Linee puntinate: intervallo storico→snapshot ufficiale; oro tratteggiato (*) = stima beta EUR/AUD, solo informativa, mai nel motore.';
 if(!note.isConnected)curve.insertAdjacentElement('afterend',note);
}
function rateBar(doc,all,id,spread=false){
 const host=doc.getElementById(id);if(!host)return;
 const items=(spread?FX.filter(x=>x!=='USD'):FX).map(c=>{
 const row=all[c],us=all.USD,est=row.estimate2||(!row.v2&&false);
 const value=spread?(num(row.v2)!==null&&num(us.v2)!==null?100*(row.v2-us.v2):null):row.v2;
 return {ccy:c,v:value,estimate:est,asof:row.estimatedAsOf2||row.date};
 });
 const W=445,H=165,L=36,R=12,T=10,B=22,barW=24,dx=(W-L-R)/items.length;
 const numbers=items.map(x=>x.v).filter(x=>x!==null);if(!numbers.length)return;
 const hi=Math.max(spread?50:0,...numbers)+(.1*(Math.max(...numbers)-Math.min(...numbers))||.5),
 lo=Math.min(0,...numbers)-(.1*(Math.max(...numbers)-Math.min(...numbers))||.5),
 yy=v=>T+(H-T-B)*(hi-v)/(hi-lo||1),zero=yy(0);
 let svg=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" stroke="#35536a" stroke-width="1"/>`;
 items.forEach((x,i)=>{
   const cx=L+dx*(i+.5),X=cx-barW/2,v=x.v;
   if(v!==null){const y=yy(v),h=Math.max(1,Math.abs(y-zero));svg+=`<rect x="${X}" y="${Math.min(y,zero)}" width="${barW}" height="${h}" rx="1" fill="${x.estimate?'#debd6d':COLOR[x.ccy]}" ${x.estimate?'opacity=".9"':''}/>`;}
   const ytext=v!==null&&v>=0?yy(v)-5:Math.min(H-B-7,zero+(v!==null?Math.abs(yy(v)-zero):0)+11);
   svg+=`<text x="${cx}" y="${ytext}" text-anchor="middle" fill="${x.estimate?'#e7c775':'#dae6f0'}" font-size="10">${v===null?'—':spread?Math.round(v):fmt(v,2)}${x.estimate?'*':''}</text><text x="${cx}" y="${H-3}" text-anchor="middle" fill="#acc3d4" font-size="11">${x.ccy}</text>`;
 });
 host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Copertura G8 completa; asterisco indica stima modellistica">${svg}</svg>`;
 const note=host.parentElement?.querySelector('.gmfq-chart-note')||doc.createElement('div');
 note.className='gmfq-chart-note';note.textContent=items.some(x=>x.estimate)?'* STIMA 2Y fattoriale: CHF da EUR, NZD da AUD. Il dato stimato non alimenta il motore.':'Rendimenti governativi verificati.';
 if(!note.isConnected)host.insertAdjacentElement('afterend',note);
}
function oisAll(doc,ois,proxy){
 const host=doc.getElementById('ois');if(!host||!ois?.currencies)return;
 const names=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'],rows=names.map(k=>{
 const x=ois.currencies[k],d=num(x?.horizons?.['6m']?.policy_delta_bp);
 const valid=x&&fresh(x.as_of,4)&&x.operational_status!=='WITHHELD'&&d!==null;
 return {k,d:valid?d:null,asof:x?.as_of,quality:x?.quality==='OFFICIAL_CERTIFIED'?'UFFICIALE':'STIMA'};
 });
 const maximum=Math.max(65,...rows.map(x=>Math.abs(x.d||0)));
 let html=rows.map(x=>{
  if(x.k==='NZD'){
    const ready=proxy?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&proxy.status==='LIVE_DIRECTIONAL_PROXY_READY'&&fresh(proxy.as_of,4);
    const v=ready?num(proxy.horizons?.['6m']?.implied_bank_bill_rate):null;
    const change=ready?num(proxy.horizons?.['6m']?.change_1d_bp):null;
    const msg=v===null?'NESSUN PROXY CORRENTE':`PROXY BB 6M · ${fmt(v,2)}% · Δ1D ${change===null?'—':(change>=0?'+':'')+change} bp`;
    return `<div class="oisrow gmfq-nzd-proxy" data-ccy="NZD" tabindex="0" role="link" aria-label="Apri RBNZ e proxy futures NZD" title="${htmlEscape(msg)} · ASX ${htmlEscape(proxy?.as_of||'n.d.')}"><span>RBNZ<small class="miniquality">PROXY BB ≠ OIS</small></span><div class="track"><div class="fill" style="width:${change===null?0:Math.min(95,Math.abs(change)*4)}%"></div></div><strong>${v===null?'—':fmt(v,2)+'%'}</strong></div>`;
  }
  const w=x.d===null?0:Math.max(2,Math.abs(x.d)/maximum*100);
  return `<div class="oisrow" data-ccy="${x.k}" tabindex="0" role="link" aria-label="Apri OIS ${x.k}" title="${x.k} · ${x.quality} · ${x.asof||'n.d.'}">
  <span>${BANK[x.k]}<small class="miniquality">${x.d===null?'WITHHELD':x.quality}</small></span>
  <div class="track"><div class="fill ${x.d!==null&&x.d<0?'alt':''}" style="width:${w}%"></div></div>
  <strong>${x.d===null?'—':(x.d>=0?'+':'')+fmt(x.d,0)+' bp'}</strong></div>`;
 }).join('');
 html+='<div class="oisnote">7 dati Δ policy a 6 mesi, distinti per qualità. NZD: futures bancari ASX, proxy direzionale non confrontabile con l\'OIS.</div>';
 host.innerHTML=html;
}
function dxyLine(data){
 if(!Array.isArray(data?.history)||data.history.length<3)return'<div class="gmfq-chart-note">Storico in fase di costruzione dal fixing ECB.</div>';
 const arr=data.history.slice(-90).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.date)&&num(x.value)!==null);
 if(arr.length<3)return'';
 const W=540,H=145,lo=Math.min(...arr.map(x=>x.value))-.15,hi=Math.max(...arr.map(x=>x.value))+.15,span=hi-lo||1;
 const points=arr.map((x,i)=>`${(i/(arr.length-1)*(W-25)+10).toFixed(1)},${(10+(H-25)*(hi-x.value)/span).toFixed(1)}`).join(' ');
 return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Storico del DXY sintetico da cambi giornalieri ECB"><polyline points="${points}" fill="none" stroke="#e6c675" stroke-width="2"/><line x1="10" x2="${W-15}" y1="${H-12}" y2="${H-12}" stroke="#31485b"/><text x="10" y="${H-1}" fill="#98b0c3" font-size="10">${arr[0].date}</text><text x="${W-15}" y="${H-1}" text-anchor="end" fill="#98b0c3" font-size="10">${arr.at(-1).date}</text></svg>`;
}
function validDxy(x){return x?.schema==='GMFQ_DXY_SYNTHETIC_ECB_V1'&&x.status==='ESTIMATED_INFORMATIONAL'&&x.not_official_ice===true&&x.usable_as_official_ice_or_trade_signal===false&&fresh(x.as_of,4)&&num(x.value)!==null&&Array.isArray(x.history)&&x.history.at(-1)?.date===x.as_of}
function renderDxy(doc){
 const tile=doc.querySelector('#valute .cc[data-filter="DXY"]');
 if(!tile)return;
 tile.tabIndex=0;tile.setAttribute('role','button');tile.setAttribute('aria-label','Apri analisi DXY sintetico, non ICE');
 const value=tile.querySelector('.value'),move=tile.querySelector('.move');
 if(!value||!move)return;
 if(validDxy(dxyFeed)){
   value.textContent=fmt(dxyFeed.value,2);
   const pct=num(dxyFeed.previous_value)&&num(dxyFeed.previous_value)>0?100*(dxyFeed.value/dxyFeed.previous_value-1):null;
   move.className='move '+(pct===null?'neutral':pct>=0?'up':'down');
   move.textContent=pct===null?'STIMA ECB':(pct>=0?'+':'')+fmt(pct,2)+'% · STIMA';
 }else{
   value.textContent='—';move.className='move neutral';move.textContent='STIMA NON DISPONIBILE';
 }
 tile.title='DXY sintetico da fixing ECB (inclusa SEK); non è il valore ICE ufficiale né un prezzo intraday';
}
function openDxy(doc){
 let dialog=doc.getElementById('gmfq-dxy-dialog');
 if(!dialog){
   dialog=doc.createElement('dialog');dialog.id='gmfq-dxy-dialog';dialog.className='gmfq-dxy-dialog';
   doc.body.appendChild(dialog);
 }
 const ok=validDxy(dxyFeed);
 dialog.innerHTML=`<button type="button" class="gmfq-close">Chiudi ×</button><h2>DXY · Dollar Index</h2>
 <div class="gmfq-dxy-val">${ok?fmt(dxyFeed.value,2):'—'}</div>
 <p class="gmfq-source">SINTETICO ECB · ${ok?htmlEscape(dxyFeed.as_of):'NON DISPONIBILE'} · non ICE ufficiale</p>
 ${ok?dxyLine(dxyFeed):'<p>Fonte non sufficientemente aggiornata: valore non pubblicato.</p>'}
 <p>Ricostruito dai fixing giornalieri BCE di EUR, JPY, GBP, CAD, SEK e CHF con pesi e costante del paniere ICE. Non è una quotazione intraday né un dato utilizzato dai motori operativi.</p>
 <p><a href="https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.eu.html" target="_blank" rel="noopener noreferrer">Fonte ECB ↗</a></p>`;
 dialog.querySelector('button').onclick=()=>dialog.close();
 dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
 if(typeof dialog.showModal==='function')dialog.showModal();
}
async function applyHome(doc){
 const [rr,oo,pp,dd]=await Promise.allSettled([
  feed('NATIVE_RATES_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json'),
  feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),feed('DXY_SYNTHETIC_ECB.json')]);
 const d=dd.status==='fulfilled'?dd.value:null;
 dxyFeed=d;
 const rates=rr.status==='fulfilled'?rr.value:null;
 const ois=oo.status==='fulfilled'?oo.value:null;
 const proxy=pp.status==='fulfilled'?pp.value:null;
 const display=()=>{
   if(!frame.isConnected||frame.contentDocument!==doc)return;
   if(doc.documentElement.dataset.marketMode!=='live')return;
   if(rates){
     const all=ratesAll(rates);
     yieldChart(doc,all,'2Y');
     const legend=doc.getElementById('ylegend');
     if(legend){
       legend.addEventListener('click',ev=>{
         const b=ev.target.closest('button[data-gmfq-tenor]');
         if(!b)return;
         legend.dataset.gmfqYieldMode=b.dataset.gmfqTenor;
         yieldChart(doc,all,b.dataset.gmfqTenor);
       });
     }
     rateBar(doc,all,'ratesbars');rateBar(doc,all,'spreads',true);
   }
   if(ois)oisAll(doc,ois,proxy);
   renderDxy(doc);
   doc.querySelectorAll('#valute .cc').forEach(el=>{
     el.tabIndex=0;el.setAttribute('role','button');
     if(el.dataset.filter!=='DXY')el.setAttribute('aria-label','Apri Valute '+(el.dataset.filter||''));
   });
   doc.querySelectorAll('#pairs tr[data-filter]').forEach(el=>{el.tabIndex=0;el.setAttribute('role','link')});
 };
 if(doc.documentElement.hasAttribute('data-live-state')){display();return}
 const observer=new MutationObserver(()=>{
   if(doc.documentElement.hasAttribute('data-live-state')){observer.disconnect();display()}
 });
 observer.observe(doc.documentElement,{attributes:true,attributeFilter:['data-live-state']});
}
function focusCurrency(doc){
 const params=new URLSearchParams(location.hash.split('?')[1]||'');
 const code=params.get('ccy');
 if(!FX.includes(code))return;
 let done=false;
 function tryFocus(){if(done)return true;const b=doc.querySelector('button[data-ccy="'+code+'"]');if(!b)return false;done=true;b.click();return true}
 if(tryFocus())return;
 const ob=new MutationObserver(()=>{if(tryFocus())ob.disconnect()});
 ob.observe(doc.body,{subtree:true,childList:true});
 frame.addEventListener('load',()=>ob.disconnect(),{once:true});
}
function onFrameLoad(){
 let doc;try{doc=frame.contentDocument}catch(_){return}
 if(!doc?.body)return;
 if(!home()){focusCurrency(doc);return}
 style(doc);navigation(doc);applyHome(doc).catch(e=>console.warn('[GMFQ home extension WITHHELD]',e));
}
frame.addEventListener('load',onFrameLoad);
})();
