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
    if(pair){const p=(pair.dataset.filter||'').replace(/[^A-Z]/g,'');if(/^[A-Z]{6}$/.test(p)){go('#/coppie?pair='+p);return}}
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
    if(pair&&e.target===pair){e.preventDefault();go('#/coppie?pair='+pair.dataset.filter);return}
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
  .gridtop #ois .oisrow{grid-template-columns:65px minmax(0,1fr) 49px;gap:4px;
    margin:0;min-height:18px;height:18px;font-size:11px}
  .gridtop #ois .oisrow:first-child{margin-top:0}
  .gridtop #ois .oisrow .track{height:12px}
  .gridtop #ois .oisrow strong{font-size:11px}
  .gridtop #ois .oisrow em{font:8px/1 Arial,sans-serif;color:#b1a17a;font-style:normal}
  .gridtop #ois .oisrow span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .gridtop #ois .oisnote{font-size:9px;line-height:1.1;margin-top:4px}
  .gridtop #ois .gmfq-nzd-proxy{border-top:1px solid #263b49;padding-top:0}
  .gridtop #ois .gmfq-nzd-proxy .fill{background:linear-gradient(90deg,#6c5b36,#dabb6c)}
  .gridtop .yieldpanel .legend-y{margin:0 3px}
  .gridtop .yieldpanel .gmfq-legend-row{gap:2px 6px;justify-content:center}
  .gridtop .yieldpanel .gmfq-legend-row .gmfq-legend-item{font-size:9px}
  .gridtop .yieldpanel .gmfq-legend-row span:before{display:none}
  .gridtop .yieldpanel .yieldplot{height:151px}
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
 // The target and its proxy must be anchored at the SAME observed date;
 // the last target official snapshot can be later than that common date.
 const value=anchor.v+beta*(base-rateThen);
 if(!Number.isFinite(value)||Math.abs(value-original)>1.5||value< -3||value>18)return null;
 const varianceTarget=diffs.reduce((s,x)=>s+(x[1]-ym)**2,0);
 const r2=varianceTarget>0?Math.min(1,Math.max(0,(cov*cov)/(variance*varianceTarget))):0;
 const confidence=r2>=.65?'ALTA':r2>=.30?'MEDIA':'BASSA';
 return {v:value,asof:ref.date,model:'stima β fattoriale',beta,origin:target.date,
   refDate:anchor.date,anchorValue:anchor.v,refAnchorRate:rateThen,r2,confidence};
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
   if(a.v2===null){const m=estimate(raw?.[k],ref,'history2');if(m){a.v2=m.v;a.estimate2=true;a.estimatedAsOf2=m.asof;a.proxy=proxy;a.beta2=m.beta;a.r2_2=m.r2;a.confidence2=m.confidence;a.anchor2=m.refDate;}}
   if(a.v10===null){const m=estimate(raw?.[k],ref,'history10');if(m){a.v10=m.v;a.estimate10=true;a.estimatedAsOf10=m.asof;a.proxy=proxy;a.beta10=m.beta;a.r2_10=m.r2;a.confidence10=m.confidence;a.anchor10=m.refDate;}}
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
 note.className='gmfq-chart-note';note.textContent='* STIMA β su data comune: CHF/EUR '+(all.CHF.confidence2||'N.D.')+'; NZD/AUD '+(all.NZD.confidence2||'N.D.')+'. Tratteggio = indicativo, non operativo.';
 if(!note.isConnected)curve.insertAdjacentElement('afterend',note);
}
function rateBar(doc,all,id,spread=false){
 const host=doc.getElementById(id);if(!host)return;
 const items=(spread?FX.filter(x=>x!=='USD'):FX).map(c=>{
 const row=all[c],us=all.USD,est=row.estimate2;
 const value=spread?(num(row.v2)!==null&&num(us.v2)!==null?100*(row.v2-us.v2):null):row.v2;
 return {ccy:c,v:value,estimate:est,asof:row.estimatedAsOf2||row.date,confidence:row.confidence2,r2:row.r2_2,anchor:row.anchor2,proxy:row.proxy};
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
 note.className='gmfq-chart-note';note.textContent=items.some(x=>x.estimate)?
 '* STIMA β (non operativa): '+items.filter(x=>x.estimate).map(x=>x.ccy+'/'+x.proxy+' '+(x.confidence||'NON VALIDATA')+' (R² '+fmt(x.r2,2)+', base '+x.anchor+')').join(' · ')+'.':
 'Rendimenti governativi verificati.';
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
    return `<div class="oisrow gmfq-nzd-proxy" data-ccy="NZD" tabindex="0" role="link" aria-label="Apri RBNZ e proxy futures NZD" title="${htmlEscape(msg)} · ASX ${htmlEscape(proxy?.as_of||'n.d.')}"><span>RBNZ <em>PX</em></span><div class="track"><div class="fill" style="width:${change===null?0:Math.min(95,Math.abs(change)*4)}%"></div></div><strong>${v===null?'—':fmt(v,2)+'%'}</strong></div>`;
  }
  const w=x.d===null?0:Math.max(2,Math.abs(x.d)/maximum*100);
  return `<div class="oisrow" data-ccy="${x.k}" tabindex="0" role="link" aria-label="Apri OIS ${x.k}" title="${x.k} · ${x.quality} · ${x.asof||'n.d.'}">
  <span>${BANK[x.k]} <em>${x.d===null?'—':x.quality==='UFFICIALE'?'O':'S'}</em></span>
  <div class="track"><div class="fill ${x.d!==null&&x.d<0?'alt':''}" style="width:${w}%"></div></div>
  <strong>${x.d===null?'—':(x.d>=0?'+':'')+fmt(x.d,0)+' bp'}</strong></div>`;
 }).join('');
 html+='<div class="oisnote">Δ6M policy: O ufficiale, S stima. NZD/PX = PROXY BB ≠ OIS (tasso %).</div>';
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
/* Home status: a successful network fetch is NOT evidence that every dataset
   is current or operational. This only explains source coverage; it never
   mutates market data, rates, policy deltas, biases, sizing or trading signals. */
function mountHomeFreshnessAudit(doc,fx,rates,ois,dxy){
 if(!home()||frame.contentDocument!==doc||doc.documentElement.dataset.marketMode!=='live')return;
 const head=doc.querySelector('.mast .fresh'),state=doc.getElementById('liveState'),
  stamp=doc.getElementById('liveAsOf');
 if(!head||!state||!stamp||doc.getElementById('gmfq-home-data-audit'))return;
 const datePattern=/^\d{4}-\d{2}-\d{2}$/;
 const fxDay=fx?.schema==='GMFQ_ECB_G8_PRICE_HISTORY_V1'&&
  fx.status==='CURRENT_OFFICIAL_HISTORY'&&datePattern.test(fx.last_as_of||'')?
  fx.last_as_of:null;
 const fxCurrent=fxDay!==null&&fresh(fxDay,4);
 const ratesCurrent=FX.filter(k=>{
  const x=rates?.[k];
  return x&&String(x.quality||'').includes('OFFICIAL')&&fresh(x.date,5)&&
   num(x['2Y'])!==null&&num(x['10Y'])!==null;
 });
 const oisCurrent=FX.filter(k=>{
  const x=ois?.currencies?.[k];
  return x?.operational_status==='GREEN_OFFICIAL'&&x.quality==='OFFICIAL_CERTIFIED'&&
   fresh(x.as_of,5)&&['3m','6m','12m'].every(t=>
    num(x.horizons?.[t]?.rate)!==null&&num(x.horizons?.[t]?.policy_delta_bp)!==null);
 });
 const dxyCurrent=validDxy(dxy);
 const complete=fxCurrent&&ratesCurrent.length===8&&oisCurrent.length===8&&dxyCurrent;
 state.textContent=complete?'FONTI VERIFICATE':'DATI PARZIALI';
 stamp.textContent=(fxCurrent?'FX '+fxDay.slice(8,10)+'/'+fxDay.slice(5,7):'FX non corr.')+' · OIS '+oisCurrent.length+'/8 ⓘ';
 head.setAttribute('role','button');head.tabIndex=0;
 head.setAttribute('aria-label','Apri verifica fonti: FX, rendimenti, pricing e DXY');
 head.setAttribute('aria-haspopup','dialog');head.setAttribute('aria-controls','gmfq-home-data-audit');
 head.setAttribute('aria-expanded','false');head.title='Apri lo stato e le date delle fonti';
 head.classList.add('gmfq-data-audit-trigger');
 // The approved mobile header hides .fresh below 600px. Surface the exact
 // same audit through a quiet, keyboard-accessible link below the hero eyebrow.
 const mobile=doc.createElement('button');
 mobile.type='button';mobile.id='gmfq-mobile-data-audit';
 mobile.textContent=state.textContent+' · '+stamp.textContent;
 mobile.setAttribute('aria-haspopup','dialog');
 mobile.setAttribute('aria-controls','gmfq-home-data-audit');
 mobile.setAttribute('aria-expanded','false');
 mobile.setAttribute('aria-label','Apri dettaglio fonti e aggiornamenti');
 doc.querySelector('.herobody .eyebrow')?.insertAdjacentElement('afterend',mobile);
 const style=doc.createElement('style');style.id='gmfq-home-data-audit-style';
 style.textContent='#gmfq-mobile-data-audit{display:none}@media(max-width:600px){#gmfq-mobile-data-audit{display:inline-block;max-width:100%;margin:8px 0 4px;padding:4px 0;background:transparent;color:#dbca9d;font:600 11px/1.45 Arial,sans-serif;white-space:normal;text-align:left;border:0;border-bottom:1px dotted #8d8060;cursor:pointer}#gmfq-mobile-data-audit:focus-visible{outline:2px solid #e3c77b;outline-offset:3px}}.mast .gmfq-data-audit-trigger{cursor:pointer}.mast .gmfq-data-audit-trigger:focus-visible{outline:2px solid #e6cb88;outline-offset:3px;border-radius:4px}.gmfq-home-data-audit{color:#e8f0f7;background:#091b2b;border:1px solid #355468;border-radius:10px;width:min(500px,calc(100vw - 32px));max-height:85vh;overflow:auto;padding:19px 20px;box-shadow:0 25px 70px #000b}.gmfq-home-data-audit::backdrop{background:#010a15be}.gmfq-home-data-audit h2{font:600 20px/1.2 Arial,sans-serif;margin:2px 0 8px}.gmfq-home-data-audit>p{font:12px/1.55 Arial,sans-serif;color:#a9c2d3;margin:8px 0 13px}.gmfq-home-data-audit .gmfq-audit-row{border-top:1px solid #284356;padding:12px 0}.gmfq-home-data-audit .gmfq-audit-row strong{display:block;font:600 13px Arial,sans-serif;color:#eaf0f5}.gmfq-home-data-audit .gmfq-audit-row p{color:#b7c8d7;font:12px/1.5 Arial,sans-serif;margin:5px 0 0}.gmfq-home-data-audit .gmfq-audit-close{float:right;border:1px solid #446378;border-radius:5px;background:#112b3e;color:#e7eef5;cursor:pointer;padding:6px 10px;font-size:12px}.gmfq-home-data-audit .gmfq-audit-close:focus-visible{outline:2px solid #e9cb83}.gmfq-home-data-audit .gmfq-audit-note{color:#d7bf86}';
 doc.head.appendChild(style);
 const withheldRates=FX.filter(k=>!ratesCurrent.includes(k));
 const withheldOis=FX.filter(k=>!oisCurrent.includes(k));
 const pairedCHF=rates?.CHF?.date;
 const line=(title,body)=>'<div class="gmfq-audit-row"><strong>'+htmlEscape(title)+'</strong><p>'+htmlEscape(body)+'</p></div>';
 const dialog=doc.createElement('dialog');dialog.id='gmfq-home-data-audit';dialog.className='gmfq-home-data-audit';
 dialog.setAttribute('aria-labelledby','gmfq-home-data-audit-title');
 dialog.innerHTML='<form method="dialog"><button class="gmfq-audit-close" aria-label="Chiudi verifica fonti">Chiudi ×</button></form>'+
  '<h2 id="gmfq-home-data-audit-title">Stato delle fonti</h2>'+
  '<p>Ultima osservazione verificata, non quotazioni in tempo reale. “Caricato” non significa necessariamente “aggiornato”.</p>'+
  line('FX G8 · fixing BCE',fxCurrent?'Ufficiale · '+fxDay+' · fine giornata, non intraday':
    'Non corrente o non disponibile · ultima data '+(fxDay||'non verificata'))+
  line('Rendimenti governativi 2Y/10Y',ratesCurrent.length+'/8 valute con 2Y e 10Y ufficiali sufficientemente recenti.'+
    (withheldRates.length?' Da aggiornare: '+withheldRates.join(', ')+'.':'')+
    (datePattern.test(pairedCHF||'')?' Ultima coppia CHF: '+pairedCHF+'.':''))+
  line('Market Pricing · OIS / futures',oisCurrent.length+'/8 valute con curve 3M/6M/12M certificate e recenti.'+
    (withheldOis.length?' Non certificate o datate: '+withheldOis.join(', ')+'.':'')+
    ' GBP OIS BoE; JPY, AUD e CAD futures monetari, non OIS puri.')+
  line('DXY sintetico · fixing BCE',dxyCurrent?
    'Stima informativa al '+dxy.as_of+'. Non è DXY ICE ufficiale e non è intraday.':
    'Stima assente o non corrente. Non è DXY ICE ufficiale.')+
  '<p class="gmfq-audit-note">Questi controlli non modificano bias, punteggi, segnali o backtest. Le date delle diverse fonti non sono intercambiabili.</p>';
 doc.body.appendChild(dialog);
 const open=()=>{head.setAttribute('aria-expanded','true');mobile.setAttribute('aria-expanded','true');if(!dialog.open)dialog.showModal()};
 const close=()=>{head.setAttribute('aria-expanded','false');mobile.setAttribute('aria-expanded','false');(mobile.getClientRects().length?mobile:head).focus()};
 mobile.addEventListener('click',open);
 head.addEventListener('click',open);
 head.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
 dialog.addEventListener('close',close);
 dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
}

async function applyHome(doc){
 const [rr,oo,pp,dd,ff]=await Promise.allSettled([
  feed('NATIVE_RATES_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json'),
  feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),feed('DXY_SYNTHETIC_ECB.json'),
  feed('ECB_G8_PRICE_HISTORY.json')]);
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
   mountHomeFreshnessAudit(doc,ff.status==='fulfilled'?ff.value:null,rates,ois,d);
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
/* The dedicated Rates page already renders all eight G8 rows, but the original
   design exposes only four country selectors. Complete the selectors in the
   additive adapter; a missing verified series still renders WITHHELD. */
function enhanceRatesDetail(doc){
 const select=doc.getElementById('rates-select');
 if(!select)return;
 const labels={AUD:'🇦🇺 AU',CAD:'🇨🇦 CA',NZD:'🇳🇿 NZ',CHF:'🇨🇭 CH'};
 for(const ccy of ['AUD','CAD','NZD','CHF']){
   if(select.querySelector('button[data-ccy="'+ccy+'"]'))continue;
   const b=doc.createElement('button');
   b.type='button';b.className='desk-filter';b.dataset.ccy=ccy;
   b.setAttribute('aria-pressed','false');
   b.textContent=labels[ccy];
   select.appendChild(b);
 }
}
/* Home cards with ?focus= must open the actual in-page section, not merely
   navigate to the generic Rates landing page. Nothing touches the data model. */
function focusRatesSection(doc){
 if(route()!=='tassi')return;
 const focus=new URLSearchParams(location.hash.split('?')[1]||'').get('focus');
 const sections={curve:'#rates-chart','2y':'#rates-rows',spread:'#rates-rows',ois:'#ois-rows'};
 const selector=sections[focus];
 if(!selector)return;
 const item=doc.querySelector(selector);if(!item)return;
 const section=item.closest('.desk-panel')||item;
 section.tabIndex=-1;
 section.focus({preventScroll:true});
 section.scrollIntoView({block:'start'});
}

/* Rates research overlay: observed validated curves are distinct from unsynchronised futures quotes.
   Display-only: no policy path can be inferred from secondary contract observations. */
function marketResearchCurves(data){
 const allowed=['GBP','JPY','AUD','CAD'],terms=['3m','6m','12m'];
 return allowed.flatMap(k=>{
  const x=data?.currencies?.[k];
  if(x?.operational_status!=='GREEN_OFFICIAL'||x.quality!=='OFFICIAL_CERTIFIED'||!fresh(x.as_of,4))return [];
  const pts=terms.map(t=>num(x.horizons?.[t]?.policy_delta_bp));
  return pts.every(v=>v!==null)?[{k,date:x.as_of,src:x.source||'',pts}]:[];
 });
}
function marketResearchSvg(curves){
 const vals=curves.flatMap(c=>c.pts);
 if(!vals.length)return '<p style="padding:24px;color:#e5c782">Curve omogenee non disponibili.</p>';
 const lo=Math.floor((Math.min(0,...vals)-12)/20)*20,hi=Math.ceil((Math.max(0,...vals)+12)/20)*20;
 const xs=[85,300,640],yy=v=>20+(170*(hi-v)/(hi-lo||1));
 let svg='';
 for(let i=0;i<5;i++){
  const n=lo+i*(hi-lo)/4,y=yy(n);
  svg+='<line x1="55" y1="'+y+'" x2="675" y2="'+y+'" stroke="#294658"/><text x="45" y="'+(y+4)+'" fill="#a3b8c8" font-size="12" text-anchor="end">'+n.toFixed(0)+'</text>';
 }
 ['3M','6M','12M'].forEach((t,i)=>svg+='<text x="'+xs[i]+'" y="220" text-anchor="middle" fill="#b4cadb" font-size="13">'+t+'</text>');
 for(const c of curves){
  svg+='<polyline fill="none" stroke="'+COLOR[c.k]+'" stroke-width="3" points="'+c.pts.map((v,i)=>xs[i]+','+yy(v)).join(' ')+'"/>';
  c.pts.forEach((v,i)=>svg+='<circle cx="'+xs[i]+'" cy="'+yy(v)+'" r="4" fill="'+COLOR[c.k]+'"/>');
 }
 svg+='<text x="678" y="14" text-anchor="end" fill="#a4bfce" font-size="11">Δ policy rate · bp</text>';
 return '<svg viewBox="0 0 720 234" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Pricing a 3, 6 e 12 mesi, confronto solo dati certificati">'+svg+'</svg>';
}
function marketResearchSecondary(data){
 const terms=['3m','6m','12m'];
 const cards=['USD','EUR','CHF'].flatMap(k=>{
  const x=data?.currencies?.[k],ctx=x?.secondary_quote_context;
  if(x?.operational_status!=='WITHHELD'||ctx?.status!=='INDICATIVE_OBSERVATIONS_NON_OIS'||
     ctx.full_curve_usable!==false||ctx.cross_date_join_allowed!==false||
     ctx.policy_delta_allowed!==false||ctx.repricing_signal_allowed!==false)return [];
  const lines=terms.map(t=>{
   const p=ctx.horizons?.[t],ok=num(p?.rate_indicative)!==null&&fresh(p?.quote_as_of,5)&&
     /^[A-Z0-9]+$/.test(p.contract||'')&&p.source_quality==='SECONDARY_VERIFIED_DAILY_BAR';
   return '<div class="gmfq-quote">'+t.toUpperCase()+' · '+(ok?
     '<strong>'+fmt(p.rate_indicative,3)+'%</strong> · '+htmlEscape(p.contract)+' · '+htmlEscape(p.quote_as_of):
     '<span>non verificato</span>')+'</div>';
  }).join('');
  return ['<article class="gmfq-quote-card"><b>'+FLAG[k]+' '+k+' · WITHHELD</b>'+lines+'</article>'];
 });
 return cards.length?'<div class="gmfq-research-separator"><h3>Quotazioni secondarie · solo contesto</h3>'+
  '<div class="gmfq-quote-cards">'+cards.join('')+'</div>'+
  '<p class="gmfq-research-note">Quotazioni di contratti futures anche su date differenti: non sono una curva OIS. Vietato collegare i punti, calcolare repricing o utilizzarli per segnali e backtest.</p></div>':'';
}
/* Compact source-unlock map: generated from live operational status and
   verified source/access audit. Never includes inferred market prices. */
function marketSourceReadinessHtml(view,operational){
 const ids=['USD','EUR','CHF','NZD'];
 const statusOk=view?.schema==='GMFQ_OIS_SOURCE_READINESS_VIEW_V1'&&
  view.status==='READ_ONLY_SOURCE_READINESS'&&fresh(view.as_of,3)&&
  view.prices_omitted===true&&view.no_automatic_promotions===true&&
  view.no_core_score_effect===true&&view.no_bias_effect===true&&
  view.no_sizing_effect===true&&view.no_backtest_effect===true&&
  ids.every(k=>view.currencies?.[k]?.status==='WITHHELD'&&
   typeof view.currencies[k].obstacle==='string'&&
   typeof view.currencies[k].activation_requirement==='string'&&
   ['WITHHELD','GREEN_ESTIMATED','GREEN_OFFICIAL'].includes(operational?.currencies?.[k]?.operational_status))&&
  view.blocked_currency_count===ids.length;
 const opening='<details class="gmfq-source-readiness" id="gmfq-source-readiness"><summary>Fonti da sbloccare · situazione e prossimi passi</summary>';
 if(!statusOk)return opening+'<p class="gmfq-research-note">Stato delle fonti da aggiornare: nessuna curva aggiuntiva viene certificata.</p></details>';
 const items=ids.filter(k=>view.currencies[k].status==='WITHHELD').map(k=>{
  const v=view.currencies[k],link=v.source_url;
  const validUrl=typeof link==='string'&&/^https:\/\/(www\.)?(cmegroup\.com|eurex\.com|ice\.com|nzfbf\.co\.nz)\//.test(link);
  const anchor=validUrl?'<a href="'+htmlEscape(link)+'" target="_blank" rel="noopener noreferrer">Fonte originale ↗</a>':'Fonte da verificare';
  const live=operational.currencies[k].operational_status;
  const state=live==='GREEN_OFFICIAL'?'CERTIFICATA · fonte operativa':
   live==='GREEN_ESTIMATED'?'SOLO INDICATIVA · non certificata':'WITHHELD · non certificata';
  return '<div class="gmfq-source-row"><div><b>'+FLAG[k]+' '+k+' · '+htmlEscape(state)+'</b>'+
   '<p>'+htmlEscape(v.obstacle)+'</p><small>Requisito per accesso ai dati ufficiali: '+htmlEscape(v.activation_requirement)+'</small></div>'+
   '<div class="gmfq-source-link">'+anchor+'</div></div>';
 }).join('');
 const chf=view.currencies.CHF?.government_rates;
 const swiss=chf?.has_new_verified_2y===false&&chf.cross_date_spread_allowed===false?
  '<p class="gmfq-research-note">🇨🇭 CHF governativi: l’ultima coppia 2Y/10Y omogenea nel feed è del '+
   htmlEscape(chf.last_paired_2y10y_as_of||'—')+
   '. Il 10Y SNB pubblicato separatamente non completa il 2Y e non permette uno spread aggiornato.</p>':'';
 return opening+'<p class="gmfq-research-note">Quattro dossier di accesso a fonti ufficiali. Il loro stato di accesso può essere precedente al runtime operativo: le quotazioni GREEN_ESTIMATED restano indicative, mai OIS ufficiali. Nessun dato indicativo è promosso a OIS o usato nei segnali. Revisione fonti: '+
  htmlEscape(view.source_reviewed_as_of)+'.</p>'+items+swiss+'</details>';
}

function mountMarketResearch(doc,ois,proxy,rates,snb10,sourceReadiness){
 if(route()!=='tassi'||frame.contentDocument!==doc)return;
 const table=doc.getElementById('ois-rows'),original=table?.closest('.desk-panel');
 if(!original||doc.getElementById('gmfq-pricing-research'))return;
 const style=doc.createElement('style');style.id='gmfq-pricing-research-style';
 style.textContent='#gmfq-pricing-research{margin-top:12px}#gmfq-pricing-research .gmfq-research-intro,#gmfq-pricing-research .gmfq-research-note{color:#a9c1d2;font-size:12px;line-height:1.55;margin:9px 0 14px}#gmfq-pricing-research h3{font-size:13px;color:#e5edf5;margin:0 0 10px}#gmfq-pricing-research .gmfq-research-plot{height:225px;max-width:100%;border:1px solid #284456;border-radius:7px;background:#0b2030;overflow:hidden}#gmfq-pricing-research svg{height:100%;width:100%;display:block}#gmfq-pricing-research .gmfq-research-tabs,#gmfq-pricing-research .gmfq-research-legend{display:flex;flex-wrap:wrap;gap:7px 13px;margin:9px 0}#gmfq-pricing-research button{cursor:pointer;background:#122c40;border:1px solid #34546b;padding:6px 12px;border-radius:5px;color:#c0d0e0;font:12px Arial,sans-serif}#gmfq-pricing-research button[aria-pressed=true]{background:#e2c87c;border-color:#e2c87c;color:#102132}#gmfq-pricing-research button:focus-visible{outline:2px solid #f7dfa0}#gmfq-pricing-research .gmfq-research-legend span{font-size:11px;color:#b4c9d8}#gmfq-pricing-research .gmfq-research-legend i{display:inline-block;width:13px;height:3px;margin-right:5px;vertical-align:middle}#gmfq-pricing-research .gmfq-research-separator{border-top:1px solid #294556;margin-top:18px;padding-top:16px}#gmfq-pricing-research .gmfq-quote-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:9px}#gmfq-pricing-research .gmfq-quote-card{background:#0b2232;border:1px solid #294659;border-radius:6px;padding:11px}#gmfq-pricing-research .gmfq-snb-spot{border:1px solid #315267;background:#0d2637;border-radius:7px;padding:12px 14px;margin:10px 0 12px;color:#aec6d7;font-size:12px;line-height:1.65}#gmfq-pricing-research .gmfq-snb-spot strong{color:#e6f1f8;font-size:20px;font-variant-numeric:tabular-nums}#gmfq-pricing-research .gmfq-snb-spot a{color:#e8cb8b;text-decoration:underline}#gmfq-pricing-research .gmfq-quote-card b{display:block;color:#f0d091;font-size:12px;margin-bottom:8px}#gmfq-pricing-research .gmfq-quote{color:#b6c9d8;font-size:11px;line-height:1.7}#gmfq-pricing-research .gmfq-quote strong{color:#e5eff5}#gmfq-pricing-research .gmfq-source-readiness{border-top:1px solid #294556;margin-top:18px;padding-top:14px}#gmfq-pricing-research .gmfq-source-readiness summary{font-size:13px;font-weight:700;color:#e9d192;cursor:pointer;outline-offset:4px}#gmfq-pricing-research .gmfq-source-row{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid #203c4d}#gmfq-pricing-research .gmfq-source-row b{font-size:12px;color:#dbe9f3}#gmfq-pricing-research .gmfq-source-row p{font-size:12px;color:#adbfcd;margin:5px 0}#gmfq-pricing-research .gmfq-source-row small{display:block;color:#c4d3dd;line-height:1.45;font-size:11px}#gmfq-pricing-research .gmfq-source-link{flex:0 0 auto;font-size:11px}#gmfq-pricing-research .gmfq-source-link a{color:#e6c57f;text-decoration:underline}@media(max-width:600px){#gmfq-pricing-research .gmfq-source-row{display:block}#gmfq-pricing-research .gmfq-source-link{margin-top:7px}}@media(max-width:600px){#gmfq-pricing-research .gmfq-research-plot{height:190px}#gmfq-pricing-research .gmfq-quote-cards{grid-template-columns:1fr}}';
 doc.head.appendChild(style);
 const curves=marketResearchCurves(ois),host=doc.createElement('section');
 host.id='gmfq-pricing-research';host.className='desk-panel';
 host.innerHTML='<h2 class="desk-panel-title">Market Pricing · curve comparate e affidabilità</h2>'+
  '<div class="desk-panel-body"><p class="gmfq-research-intro">Cosa sta prezzando il mercato su 3, 6 e 12 mesi? Il grafico mostra solo le scadenze validate, espresse come differenza dal policy rate. Non sono probabilità per meeting.</p>'+
  '<div class="gmfq-research-tabs" role="group" aria-label="Filtra pricing certificato"></div>'+
  '<div class="gmfq-research-plot"></div><div class="gmfq-research-legend"></div>'+
  '<p class="gmfq-research-note">Certificato significa fonte verificata, non OIS puro: GBP è OIS BoE; JPY, AUD e CAD provengono da futures monetari. Ogni curva mostra punti di mercato per scadenza, non una previsione certa della banca centrale.</p>'+
  marketResearchSecondary(ois)+'<div class="gmfq-research-separator"><h3>Fonti incomplete</h3>'+
  '<div class="gmfq-snb-spot" id="gmfq-chf-snb-10y-context" role="note"></div>'+
  '<p class="gmfq-research-note" id="gmfq-nzd-pricing-context"></p>'+
  '<p class="gmfq-research-note" id="gmfq-chf-rates-context"></p></div>'+marketSourceReadinessHtml(sourceReadiness,ois)+'</div>';
 original.insertAdjacentElement('afterend',host);
 const labels=[['ALL','Tutte'],...curves.map(c=>[c.k,FLAG[c.k]+' '+c.k])];
 const tabs=host.querySelector('.gmfq-research-tabs'),plot=host.querySelector('.gmfq-research-plot'),legend=host.querySelector('.gmfq-research-legend');
 let selected='ALL';
 for(const [key,value] of labels){
  const b=doc.createElement('button');b.type='button';b.dataset.pricingCcy=key;b.textContent=value;tabs.appendChild(b);
 }
 const draw=()=>{
  const shown=selected==='ALL'?curves:curves.filter(x=>x.k===selected);
  plot.innerHTML=marketResearchSvg(shown);
  legend.innerHTML=shown.map(c=>'<span title="'+htmlEscape(c.src)+'"><i style="background:'+COLOR[c.k]+'"></i>'+FLAG[c.k]+' '+c.k+' · '+htmlEscape(c.date)+'</span>').join('');
  tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.pricingCcy===selected)));
 };
 tabs.addEventListener('click',e=>{const b=e.target.closest('button[data-pricing-ccy]');if(b){selected=b.dataset.pricingCcy;draw()}});
 draw();
 const nz=proxy?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&proxy.status==='LIVE_DIRECTIONAL_PROXY_READY'&&fresh(proxy.as_of,4)?
   num(proxy.horizons?.['6m']?.implied_bank_bill_rate):null;
 host.querySelector('#gmfq-nzd-pricing-context').textContent=nz===null?
  '🇳🇿 NZD: curva OIS non certificata; proxy Bank Bill non disponibile o fuori data.':
  '🇳🇿 NZD Bank Bill 6M · '+fmt(nz,2)+'% · '+proxy.as_of+' — proxy direzionale, NON curva OIS né policy delta.';
 const official10=snb10?.schema==='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'&&
  snb10.status==='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'&&snb10.currency==='CHF'&&snb10.tenor==='10Y'&&
  snb10.yield_type==='SWISS_CONFEDERATION_ZERO_COUPON_SPOT'&&
  snb10.operational_rates_2y10y_untouched===true&&snb10.has_current_2y===false&&
  snb10.eligible_for_curve_spreads===false&&snb10.eligible_for_core_signals===false&&
  snb10.eligible_for_backtests===false&&snb10.ois_or_saron===false&&
  snb10.source_url==='https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates'&&
  fresh(snb10.as_of,4)&&num(snb10.value_percent)!==null&&
  snb10.value_percent>=-3&&snb10.value_percent<=18;
 const snbBox=host.querySelector('#gmfq-chf-snb-10y-context');
 if(official10){
   snbBox.innerHTML='🇨🇭 <strong>CHF 10Y SNB '+fmt(snb10.value_percent,3)+'%</strong> · spot Confederazione · '+htmlEscape(snb10.as_of)+
    '. Dato ufficiale singolo, SOLO INFORMATIVO; il 2Y resta privo di aggiornamento omogeneo, nessuno spread o segnale è calcolato. '+
    '<a target="_blank" rel="noopener noreferrer" href="https://www.snb.ch/en/the-snb/mandates-goals/statistics/statistics-pub/current_interest_exchange_rates">Fonte SNB ↗</a>';
 }else snbBox.textContent='🇨🇭 CHF 10Y SNB: contesto ufficiale non disponibile o non corrente. Nessuna ricostruzione di 2Y, spread o segnali.';
 
 const ch=rates?.CHF;
 host.querySelector('#gmfq-chf-rates-context').textContent=ch?.date&&!fresh(ch.date,4)?
  '🇨🇭 CHF 2Y/10Y (serie omogenea): ultimo snapshot canonico '+ch.date+'. Non corrente; il 10Y SNB sopra è separato e non completa il 2Y né lo spread. La stima della Home è solo illustrativa.':
  '';
}
async function applyMarketResearch(doc){
 const all=await Promise.allSettled([feed('OIS_OPERATIONAL_VIEW.json'),feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),feed('NATIVE_RATES_DATA.json'),feed('CHF_SNB_10Y_SPOT_CONTEXT.json'),feed('OIS_SOURCE_READINESS_VIEW.json')]);
 mountMarketResearch(doc,...all.map(x=>x.status==='fulfilled'?x.value:null));
}

/* Pair research journey, added next to (not replacing) the original 28-pair
   deep dive. Source as-of != today's ECB fixing. No derived trade signals. */
/* Research-only Macro/2Y/10Y/6M comparator.
   Structural Macro/Policy sides come ONLY from the 28-pair canonical model,
   independently dated sovereign yields ONLY from official native Rates.
   Never derive a curve/spread from mismatched or stale dates. */
function pairMacroRatesComparison(code,pair,rates,ois,modelDay,macroDay){
 const a=code.slice(0,3),b=code.slice(3,6),s=pair?.decision_frame||{};
 const safeSide=(v)=>v===a||v===b?v:null;
 const macroSide=safeSide(s.macroSide),policySide=safeSide(s.policySide);
 const sideText=(v)=>v===a?'Favorisce '+FLAG[a]+' '+a:v===b?'Favorisce '+FLAG[b]+' '+b:
  'Non distingue chiaramente le due valute';
 const sovereign=(c)=>{
   const r=rates?.[c],d=r?.date;
   const certified=!!r&&String(r.quality||'').includes('OFFICIAL')&&fresh(d,5)&&
    num(r['2Y'])!==null&&num(r['10Y'])!==null;
   return {date:d||null,certified, y2:certified?num(r['2Y']):null,y10:certified?num(r['10Y']):null};
 };
 const repricing=(c)=>{
   const o=ois?.currencies?.[c];
   const ok=o?.operational_status==='GREEN_OFFICIAL'&&o.quality==='OFFICIAL_CERTIFIED'&&
    o.official_status==='ACTIVE'&&fresh(o.as_of,5)&&
    num(o.horizons?.['6m']?.policy_delta_bp)!==null;
   const instrument=c==='GBP'?'OIS BoE':c==='JPY'?'futures TONA':
    c==='AUD'?'futures IB':c==='CAD'?'futures CORRA':'strumento non certificato';
   return {ok, date:o?.as_of||null,delta:ok?o.horizons['6m'].policy_delta_bp:null,instrument};
 };
 const leg=(c)=>{
  const r=sovereign(c),p=repricing(c);
  const ratesLine=r.certified?
   '2Y '+fmt(r.y2,2)+'% · 10Y '+fmt(r.y10,2)+'% · '+r.date:
   '2Y / 10Y WITHHELD · ultima data '+(r.date||'non verificata');
  const fwd=p.ok?('6M '+(p.delta>0?'+':'')+fmt(p.delta,1)+' bp · '+p.instrument+
   ' · '+p.date):'6M pricing WITHHELD · '+(p.date||'non verificato');
  return '<div class="gmfq-compare-leg" data-gmfq-compare-ccy="'+c+'"><strong>'+
   FLAG[c]+' '+c+'</strong><small>'+htmlEscape(ratesLine)+'</small>'+
   '<small>'+htmlEscape(fwd)+'</small></div>';
 };
 const A=sovereign(a),B=sovereign(b);
 // Same date is mandatory; do not use the latest separately published CHF 10Y
 // to fill in a missing 2Y. A dated yield gap is NOT a policy prediction.
 const same=A.certified&&B.certified&&A.date===B.date;
 const spread=same?Math.round((A.y2-B.y2)*100):null;
 const spreadMsg=same?
  'Spread 2Y governativi (base − quotata): '+(spread>0?'+':'')+spread+
    ' bp · stesso giorno '+A.date+'. Differenza di livello, non segnale FX.':
  'Spread 2Y osservato: WITHHELD. Le due scadenze devono essere ufficiali, recenti e riferite allo stesso giorno.';
 const verdict=macroSide&&policySide&&macroSide===policySide?
  'Macro e Tassi/banche centrali favoriscono la stessa valuta nel modello.':
  macroSide&&policySide&&macroSide!==policySide?
   'Macro e Tassi/banche centrali favoriscono valute opposte: nessun allineamento completo.':
   macroSide||policySide?
    'Solo un pilastro distingue le valute: vantaggio strutturale parziale, non un ingresso.':
    'Nessun vantaggio convergente dimostrato dai due pilastri nel modello.';
 const watch=typeof s.watch==='string'?s.watch:'Non ci sono condizioni sufficienti per una lettura operativa.';
 return '<section class="gmfq-compare" id="gmfq-pair-macro-rates" aria-label="Confronto Macro Rates delle due valute">'+
  '<h3>Macro e Rates · confronto '+FLAG[a]+' '+a+' / '+FLAG[b]+' '+b+'</h3>'+
  '<div class="gmfq-compare-score"><div><span>MACRO · baseline '+htmlEscape(macroDay||'non certificata')+'</span>'+
    '<strong>'+htmlEscape(sideText(macroSide))+'</strong></div>'+
    '<div><span>TASSI / BANCHE CENTRALI · baseline '+htmlEscape(macroDay||'non certificata')+'</span>'+
    '<strong>'+htmlEscape(sideText(policySide))+'</strong></div></div>'+
  '<p class="gmfq-compare-explain">'+htmlEscape(verdict)+'</p>'+
  '<div class="gmfq-compare-legs">'+leg(a)+leg(b)+'</div>'+
  '<p class="gmfq-compare-spread" data-same-date="'+(same?'true':'false')+'">'+htmlEscape(spreadMsg)+'</p>'+
  '<p class="gmfq-compare-note"><strong>Cosa controllare:</strong> '+htmlEscape(watch)+'</p>'+
  '<p class="gmfq-compare-disclaimer">I giudizi Macro e Tassi/CB sono quelli dello snapshot del motore, non vengono ricalcolati con i rendimenti mostrati. Il 6M descrive strumenti OIS/futures differenti: non sottrarre i loro delta e non trasformarli in previsioni di cambio.</p></section>';
}

/* What Changed = separate historical, measured yield change from the dated,
   qualitative canonical model diagnosis. An absent/mismatched interval is NOT
   a 1D, 1W or inferred live CB repricing. Read-only, no model reconstruction. */
function pairWhatChangedEvidence(code,pair,rates,modelDay){
 const a=code.slice(0,3),b=code.slice(3,6),dynamic=pair?.relative_dynamics;
 const modelValid=!!dynamic&&dynamic.a===a&&dynamic.b===b&&
  dynamic.A?.withheld===false&&dynamic.B?.withheld===false&&
  Array.isArray(dynamic.A.details)&&Array.isArray(dynamic.B.details)&&
  fresh(modelDay,5);
 const observation=(ccy)=>{
  const item=rates?.[ccy],history=item?.history2,date=item?.date;
  const base=!!item&&String(item.quality||'').includes('OFFICIAL')&&fresh(date,5)&&
   num(item['2Y'])!==null;
  const dates=history?.dates,values=history?.values;
  if(!base||!Array.isArray(dates)||!Array.isArray(values)||
     dates.length!==values.length||dates.length<2)
   return {status:'WITHHELD',text:'2Y: variazione non certificabile · '+(date||'data assente')};
  const current=dates.length-1;
  const latest=dates[current],previous=dates[current-1],nowValue=num(values[current]),oldValue=num(values[current-1]);
  const gap=(Date.parse(latest+'T00:00:00Z')-Date.parse(previous+'T00:00:00Z'))/86400000;
  const eligible=latest===date&&Number.isFinite(gap)&&gap>0&&gap<=5&&
   nowValue!==null&&oldValue!==null&&Math.abs(nowValue-item['2Y'])<=0.001;
  if(!eligible)return {status:'WITHHELD',text:'2Y: variazione non confrontabile · ultima osservazione '+date+
   (Number.isFinite(gap)&&gap>5?' · intervallo storico troppo lungo':'')};
  const delta=Math.round((nowValue-oldValue)*1000)/10;
  const label=delta>0.05?'sale':delta< -0.05?'scende':'stabile';
  return {status:'MEASURED',delta,prev:previous,latest,description:label,
   text:'2Y '+label+' '+(delta>0?'+':'')+fmt(delta,1)+' bp · '+previous+' → '+latest+
   ' · stessa serie ufficiale'};
 };
 const modelLeg=(ccy,key)=>{
  if(!modelValid)return '<p class="gmfq-change-model">Lettura Macro del motore non disponibile o non aggiornata.</p>';
  const data=dynamic[key],detail=data.details.filter(t=>typeof t==='string'&&
   /^(Crescita|Lavoro|Rates|Inflazione): /.test(t)).slice(0,4);
  if(!detail.length)return '<p class="gmfq-change-model">Il motore non identifica una dinamica interpretabile.</p>';
  return '<p class="gmfq-change-model">'+detail.map(v=>htmlEscape(v)).join(' · ')+'</p>';
 };
 const leg=(c,key)=>{
  const ob=observation(c);
  return '<div class="gmfq-change-leg" data-gmfq-change-currency="'+c+
    '" data-gmfq-yield-change="'+ob.status+'"><strong>'+FLAG[c]+' '+c+'</strong>'+
    '<span>LETTURA MODELLO · '+htmlEscape(modelDay)+'</span>'+
    modelLeg(c,key)+
    '<span>VARIAZIONE 2Y · DATI OSSERVATI</span><p class="gmfq-change-measured">'+
    htmlEscape(ob.text)+'</p></div>';
 };
 const phase=modelValid&&typeof pair?.transition?.state==='string'?
  htmlEscape(pair.transition.state):'Dinamica del motore non verificata';
 return '<section class="gmfq-what-changed" id="gmfq-pair-what-changed" aria-label="Cosa sta cambiando, modello contro fatti osservati">'+
  '<h3>Cosa sta cambiando · modello vs dati</h3>'+
  '<p>Il motore riassume la dinamica Macro dello snapshot; il 2Y misura invece un movimento realmente osservato. Non sono la stessa prova.</p>'+
  '<div class="gmfq-change-legs">'+leg(a,'A')+leg(b,'B')+'</div>'+
  '<p class="gmfq-change-summary">Dinamica relativa del modello ('+htmlEscape(modelDay)+'): '+phase+'. È una diagnosi qualitativa, non un nuovo rilascio economico.</p>'+
  '<p class="gmfq-change-warning">Il confronto 2Y indica la variazione tra due date ufficiali dichiarate, non necessariamente 24 ore; con serie vecchie o intervalli troppo lunghi la variazione resta non confrontabile. Nessun dato cambia la tesi, il sizing o i trigger.</p>'+
  '</section>';
}

/* Relative Rates -> FX consistency audit, not event study, attribution, signal
   or inference from model bias. Select ONLY exactly date-matched published ECB
   fixing AND official 2Y observations for both currency legs. */
function pairMarketReactionAudit(code,rates,fx){
 const a=code.slice(0,3),b=code.slice(3,6);
 const withheld=(why)=>'<section id="gmfq-pair-market-reaction" class="gmfq-reaction" data-reaction-status="WITHHELD" aria-label="Audit reazione dei mercati">'+
  '<h3>Il mercato ha reagito come doveva?</h3>'+
  '<p class="gmfq-reaction-verdict">NON VALUTABILE · '+htmlEscape(why)+'</p>'+
  '<p class="gmfq-reaction-note">Per un confronto servono due date comuni con rendimenti governativi 2Y ufficiali di entrambe le valute e fixing BCE della coppia. Nessun segnale ricostruito.</p></section>';
 if(!/^[A-Z]{6}$/.test(code)||!FX.includes(a)||!FX.includes(b)||a===b)
  return withheld('coppia non riconosciuta');
 const hist=(c)=>{
  const v=rates?.[c],h=v?.history2;
  if(!v||!String(v.quality||'').includes('OFFICIAL')||!fresh(v.date,5)||
     num(v['2Y'])===null||!Array.isArray(h?.dates)||!Array.isArray(h?.values)||
     h.dates.length!==h.values.length||h.dates.length<2)return null;
  const last=h.dates.length-1;
  if(h.dates[last]!==v.date||num(h.values[last])===null||
     Math.abs(h.values[last]-v['2Y'])>0.001)return null;
  const rows=new Map();
  let prev='';
  // Strictly validate the last five observations. This is a short dated
  // audit; older legacy JPY history rows can use non-ISO dates and should
  // neither contaminate nor suppress the RECENT independently certified rows.
  for(let i=Math.max(0,h.dates.length-5);i<h.dates.length;i++){
   const d=h.dates[i],val=num(h.values[i]);
   if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||d<=prev||val===null||d>v.date)return null;
   rows.set(d,val);prev=d;
  }
  return rows;
 };
 const ah=hist(a),bh=hist(b);
 if(!ah||!bh)return withheld('2Y di una o entrambe le valute non attuali o non certificati');
 if(fx?.schema!=='GMFQ_ECB_G8_PRICE_HISTORY_V1'||
    fx.status!=='CURRENT_OFFICIAL_HISTORY'||!fresh(fx.last_as_of,5)||
    !Array.isArray(fx.rows)||fx.pair_count!==28)
  return withheld('storico fixing BCE non attuale o non verificato');
 const quotes=new Map();
 let prev='';
 for(const row of fx.rows){
  const d=row?.Date;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(d)||d<=prev||d>fx.last_as_of)
   return withheld('date dello storico BCE non ordinate o non verificate');
  prev=d;
  const base=a==='EUR'?1:num(row?.[a]),quote=b==='EUR'?1:num(row?.[b]);
  if(base!==null&&quote!==null&&base>0&&quote>0)
   quotes.set(d,quote/base); // ECB rates are currency units per 1 EUR.
 }
 const common=[...ah.keys()].filter(d=>bh.has(d)&&quotes.has(d)&&fresh(d,5)).sort();
 if(common.length<2)
  return withheld('meno di due date ufficiali comuni recenti tra FX e rendimenti 2Y');
 const end=common[common.length-1],start=common[common.length-2];
 const gap=(Date.parse(end+'T00:00:00Z')-Date.parse(start+'T00:00:00Z'))/86400000;
 if(!Number.isFinite(gap)||gap<=0||gap>5)
  return withheld('intervallo tra date comuni troppo lungo · ultima data '+end);
 // The strongest guard: all THREE observations on each date are official
 // matched snapshots. Do NOT mix same-week independently dated bond levels.
 const spread0=(ah.get(start)-bh.get(start))*100;
 const spread1=(ah.get(end)-bh.get(end))*100;
 const deltaSpread=spread1-spread0;
 const q0=quotes.get(start),q1=quotes.get(end);
 const fxPct=(q1/q0-1)*100;
 if(![spread0,spread1,deltaSpread,q0,q1,fxPct].every(Number.isFinite)||q0<=0||q1<=0)
  return withheld('valori delle osservazioni non validi');
 const rateSign=deltaSpread>=2?1:deltaSpread<=-2?-1:0;
 const priceSign=fxPct>=0.05?1:fxPct<=-0.05?-1:0;
 const state=rateSign&&priceSign?(rateSign===priceSign?'COERENTE':'DIVERGENTE'):'NON_CONCLUSIVO';
 const dir=rateSign>0?FLAG[a]+' '+a:rateSign<0?FLAG[b]+' '+b:'nessuna valuta chiaramente';
 const interpretation=state==='COERENTE'?
  'Coerenza direzionale: la coppia si è mossa nella stessa direzione suggerita dalla variazione relativa dei 2Y.':
  state==='DIVERGENTE'?
   'Divergenza: il cambio si è mosso in direzione opposta a quella suggerita dalla variazione relativa dei 2Y.':
   'Movimenti troppo piccoli per una conclusione direzionale con la soglia descrittiva adottata.';
 const label=state==='COERENTE'?'COERENTE':state==='DIVERGENTE'?'DIVERGE':'NON CONCLUSIVO';
 const sign=(x,d)=>((x>0?'+':'')+fmt(x,d));
 const pairLabel=FLAG[a]+' '+a+' / '+FLAG[b]+' '+b;
 return '<section id="gmfq-pair-market-reaction" class="gmfq-reaction" data-reaction-status="'+state+
  '" data-window-start="'+start+'" data-window-end="'+end+'" data-reaction-fx-side="'+(priceSign>0?a:priceSign<0?b:'')+'" aria-label="Audit reazione dei mercati">'+
  '<h3>Il mercato ha reagito come doveva?</h3>'+
  '<p>Controllo di <strong>coerenza direzionale</strong>, non spiegazione causale. Si confronta lo stesso intervallo per i due rendimenti 2Y e per il fixing FX.</p>'+
  '<div class="gmfq-reaction-window">FONTI UFFICIALI · '+start+' → '+end+' · '+gap+
   (gap===1?' giorno':' giorni')+' di calendario</div>'+
  '<div class="gmfq-reaction-metrics"><div><span>VARIAZIONE SPREAD 2Y · '+FLAG[a]+' '+a+' − '+FLAG[b]+' '+b+
   '</span><strong>'+sign(deltaSpread,1)+' bp</strong><small>Spread osservato '+sign(spread0,1)+' → '+sign(spread1,1)+' bp</small></div>'+
   '<div><span>CAMBIO · '+pairLabel+'</span><strong>'+sign(fxPct,2)+'%</strong><small>Fixing BCE '+fmt(q0,b==='JPY'?2:4)+
   ' → '+fmt(q1,b==='JPY'?2:4)+'</small></div></div>'+
  '<div class="gmfq-reaction-verdict" data-reaction-verdict="'+state+'"><strong>'+label+'</strong> · '+
   htmlEscape(interpretation)+'</div>'+
  '<p class="gmfq-reaction-note">Lettura teorica limitata: un aumento dello spread 2Y (base − quotata) tende, a parità di altri fattori, a favorire '+FLAG[a]+' '+a+
   '; un calo favorirebbe '+FLAG[b]+' '+b+'. Questa volta lo spostamento relativo suggerisce '+htmlEscape(dir)+
   '. Soglie di lettura: ±2 bp sui rendimenti e ±0,05% sul FX.</p>'+
  '<p class="gmfq-reaction-warning">Sono fixing BCE e rendimenti governativi di fine giornata, non prezzi intraday sincronizzati né la reazione a una singola notizia. Altri fattori possono dominare il cambio. Questo audit non modifica la tesi, non prova causalità e non genera ordini, trigger o livelli.</p></section>';
}

/* Bridging an official SAME-DATE 2Y/FX observation with the canonical
   decision frame. Do not promote a short-term FX move to a model verdict.
   Canonical structural preference & setup quality remain separate. */
/* A dated, qualitative set of questions for the next research review,
   using only canonical engine fields and the verified FX/2Y diagnosis.
   These are NOT forecasted triggers, price levels, or executable entries. */
function pairEvidenceChecklist(code,pair,modelDay,reactionHtml,macroDay){
 const a=code.slice(0,3),b=code.slice(3,6),src=pair?.setup||{},frame=pair?.decision_frame||{};
 const fav=[a,b].includes(src.structuralFav)?src.structuralFav:null;
 const other=fav===a?b:fav===b?a:null;
 const audited=/data-reaction-status="(COERENTE|DIVERGENTE|NON_CONCLUSIVO|WITHHELD)"/.exec(reactionHtml||'')?.[1]||'WITHHELD';
 const windowEnd=/data-window-end="(\d{4}-\d{2}-\d{2})"/.exec(reactionHtml||'')?.[1]||null;
 const side=/data-reaction-fx-side="([A-Z]{3})"/.exec(reactionHtml||'')?.[1]||null;
 const measured=windowEnd&&fresh(windowEnd,5)&&['COERENTE','DIVERGENTE'].includes(audited)&&[a,b].includes(side);
 const observation=measured?('Ultima finestra confrontabile fino al '+windowEnd+': fixing FX favorevole a '+FLAG[side]+' '+side+'.'):
  'La finestra recente non dà una verifica direzionale confrontabile: non usare un segnale surrogato.';
 const partial=!!fav&&(![a,b].includes(frame.macroSide)||![a,b].includes(frame.policySide));
 const need=typeof frame.missing==='string'&&frame.missing?frame.missing:'Differenziazione Macro/Rates ancora da verificare.';
 const confirm=fav?
  'Verificare nuovi fixing BCE nella direzione di '+FLAG[fav]+' '+fav+
   ', confrontati con i 2Y sulle stesse date. '+
   (partial?'Controllare se il pilastro Macro o Tassi/CB oggi non decisivo diventa più chiaro.':
    'Controllare che entrambi i pilastri strutturali restino dalla stessa parte.'):
  'Prima serve una preferenza Macro/Tassi/CB verificabile e non soltanto uno spread governativo elevato.';
 const weakens=fav?
  'Nuovi fixing nella direzione di '+FLAG[other]+' '+other+
   ' e peggioramento dei driver strutturali renderebbero meno convincente la lettura favorevole a '+
   fav+'. Da soli non definiscono un livello di invalidazione.':
  'Se Macro e Tassi/CB restano non discriminanti, eventuali movimenti di prezzo non sono una conferma strutturale.';
 const blockers=[];
 if(!fav)blockers.push('Il motore non individua una valuta favorita.');
 if(src.price?.state==='BAD'||src.price?.state==='NEUTRAL')
  blockers.push('Prezzo nel modello: '+src.price.text+'.');
 if(src.extension?.state==='ADVANCED')
  blockers.push('Estensione del prezzo: '+(src.extension.text||'già avanzato')+'.');
 if(typeof src.timing?.text==='string')blockers.push('Timing: '+src.timing.text+'.');
 if(['HIGH','DIVERGENT'].includes(src.cot?.state)&&typeof src.cot.text==='string')
  blockers.push('Posizionamento: '+src.cot.text+'.');
 if(src.liquidity?.state==='BAD'&&typeof src.liquidity.text==='string')
  blockers.push('Liquidità: '+src.liquidity.text+'.');
 if(!blockers.length)blockers.push('Serve ancora un ingresso tecnico verificato e un rapporto rischio/rendimento definito esternamente al modello.');
 const row=(name,text)=>'<div class="gmfq-evidence-row"><b>'+htmlEscape(name)+'</b><p>'+htmlEscape(text)+'</p></div>';
 return '<section id="gmfq-pair-evidence-checklist" class="gmfq-evidence-checklist" aria-label="Condizioni qualitative da verificare">'+
  '<h4>Cosa controllare al prossimo aggiornamento</h4>'+
  '<p class="gmfq-evidence-intro">Domande di ricerca, non condizioni operative già soddisfatte. Prezzo del modello: '+htmlEscape(modelDay)+' · baseline Macro/Tassi: '+htmlEscape(macroDay||'non certificata')+(fresh(macroDay,10)?'.':' (NON CORRENTE: tesi da rivalidare).')+'</p>'+
  '<div class="gmfq-evidence-rows">'+
   row('Confermerebbe la direzione',confirm)+
   row('Indebolirebbe la lettura',weakens)+
   row('Prima di valutare il trade',blockers.join(' '))+
  '</div>'+
  '<p class="gmfq-evidence-provenance">'+htmlEscape(observation)+' '+htmlEscape(need)+'</p>'+
  '<p class="gmfq-evidence-caution">Senza aggiornamento verificato di Macro, Tassi/CB e Prezzo queste condizioni restano ipotesi da controllare. Nessun trigger numerico o livello tecnico viene derivato automaticamente.</p>'+
  '</section>';
}

function pairThesisReactionBridge(code,pair,modelDay,reactionHtml,macroDay){
 const base=code.slice(0,3),quote=code.slice(3,6),meta=pair?.setup||{},frame=pair?.decision_frame||{};
 const favored=meta.structuralFav===base||meta.structuralFav===quote?meta.structuralFav:null;
 const status=/data-reaction-status="(COERENTE|DIVERGENTE|NON_CONCLUSIVO|WITHHELD)"/.exec(reactionHtml||'')?.[1]||'WITHHELD';
 const observedSide=/data-reaction-fx-side="([A-Z]{3})"/.exec(reactionHtml||'')?.[1]||null;
 const validSide=(observedSide===base||observedSide===quote)&&['COERENTE','DIVERGENTE'].includes(status);
 const state=validSide&&favored?(observedSide===favored?'CONFERMA_DIREZIONE':'CONTRO_TESI'):
  'NON_DETERMINATO';
 const trend=state==='CONTRO_TESI'?
  'Il fixing recente ha favorito '+FLAG[observedSide]+' '+observedSide+
   ', contro la preferenza strutturale '+FLAG[favored]+' '+favored+
   '. Una coerenza 2Y–FX non equivale a conferma della tesi.':
  state==='CONFERMA_DIREZIONE'?
   'Il fixing recente ha favorito '+FLAG[favored]+' '+favored+
   ', nella direzione della tesi. È una conferma di direzione nel periodo, non un nuovo ingresso.':
  favored?'Nessuna conferma o invalidazione dal fixing in questa finestra: audit assente, incompleto o non conclusivo.':
   'Il motore non identifica una valuta strutturalmente favorita: il confronto Rates/FX non crea da solo una tesi.';
 const structural=favored?'Favore '+FLAG[favored]+' '+favored:'Nessuna preferenza netta';
 const quality=typeof frame.quality==='string'&&frame.quality?frame.quality:'Non disponibile';
 const setupQuality=typeof meta.quality==='string'&&meta.quality?meta.quality:'Non valutabile';
 const setupTiming=typeof meta.timing?.text==='string'?meta.timing.text:'Timing non certificato';
 const watch=typeof frame.watch==='string'&&frame.watch?frame.watch:'Servono nuove evidenze Macro e Rates certificate.';
 const price=typeof frame.priceNote==='string'&&frame.priceNote?frame.priceNote:'Prezzo del modello non verificato';
 const label=status==='COERENTE'?'Coerente tra 2Y e FX':status==='DIVERGENTE'?'Divergente tra 2Y e FX':
  status==='NON_CONCLUSIVO'?'Non conclusivo':'Non valutabile';
 return '<section id="gmfq-pair-decision-bridge" class="gmfq-decision-bridge" data-bridge-status="'+state+'" aria-label="Tesi, setup e reazione recente">'+
  '<h3>Dalla tesi alla decisione · cosa conta davvero</h3>'+
  '<p>Tre piani distinti. La lettura recente dei 2Y non ricalcola il modello, e la qualità di un setup non significa che sia già il momento di entrare.</p>'+
  '<div class="gmfq-decision-cols"><div><span>TESI STRUTTURALE · baseline '+htmlEscape(macroDay||'non certificata')+'</span><strong>'+
  structural+'</strong><small>'+htmlEscape(quality)+'</small></div>'+
  '<div><span>OPERABILITÀ · SETUP DEL MODELLO</span><strong>'+htmlEscape(setupQuality)+'</strong><small>'+
  htmlEscape(setupTiming)+'</small></div>'+
  '<div><span>REAZIONE OSSERVATA · RATES / FX</span><strong>'+htmlEscape(label)+'</strong><small>'+
  htmlEscape(trend)+'</small></div></div>'+
  '<div class="gmfq-decision-watch"><strong>Cosa monitorare secondo il modello</strong><p>'+htmlEscape(watch)+'</p></div>'+
  pairEvidenceChecklist(code,pair,modelDay,reactionHtml,macroDay)+
  '<p class="gmfq-decision-context">Lettura prezzo del modello ('+htmlEscape(modelDay)+'): '+htmlEscape(price)+'</p>'+
  '<p class="gmfq-decision-disclaimer">Non sono disponibili trigger numerici certificati di conferma, invalidazione o ingresso in questo feed. Nessun livello, stop, score o segnale viene creato da questa sezione.</p></section>';
}

async function mountPairResearch(doc){
 if(route()!=='coppie'||frame.contentDocument!==doc)return;
 const host=doc.getElementById('pair-detail');
 if(!host)return;
 const inputs=await Promise.allSettled([
  feed('PAIR_SETUP_OPERATIONAL_VIEW.json'),feed('ECB_G8_PRICE_HISTORY.json'),
  feed('NATIVE_RATES_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json')]);
 if(frame.contentDocument!==doc||route()!=='coppie')return;
 const [setup,fx,rates,ois]=inputs.map(x=>x.status==='fulfilled'?x.value:null);
 const ok=setup?.schema==='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'&&
  setup.status==='CURRENT_CANONICAL_ENGINE'&&setup.pair_count===28&&
  Object.keys(setup.pairs||{}).length===28&&setup.price_audit?.status==='PASS'&&
  setup.price_audit.as_of===setup.price_asof&&setup.thesis_is_not_entry===true&&
  setup.entry_level_published===false&&fresh(setup.price_asof,5);
 const fxOk=fx?.schema==='GMFQ_ECB_G8_PRICE_HISTORY_V1'&&
  fx.status==='CURRENT_OFFICIAL_HISTORY'&&fx.pair_count===28&&fresh(fx.last_as_of,5);
 if(!ok||!host||doc.getElementById('gmfq-pair-research-path'))return;
 const style=doc.createElement('style');style.id='gmfq-pair-path-style';
 style.textContent='#gmfq-pair-research-path{margin-top:12px}#gmfq-pair-research-path .gmfq-path-body{padding:13px 17px 16px}#gmfq-pair-research-path p{color:#b8cad7;font-size:12px;line-height:1.55;margin:7px 0 12px}#gmfq-pair-research-path .gmfq-path-evidence{color:#e0c788;font-size:11px;line-height:1.5}#gmfq-pair-research-path .gmfq-path-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}#gmfq-pair-research-path .gmfq-path-leg{border:1px solid #294457;border-radius:6px;background:#0a2232;padding:12px 13px;min-width:0}#gmfq-pair-research-path .gmfq-path-leg strong{color:#ebf2f7;font-size:14px;display:block}#gmfq-pair-research-path .gmfq-path-leg small{display:block;color:#9db6c8;font-size:11px;margin:5px 0 9px;line-height:1.4}#gmfq-pair-research-path .gmfq-path-links{display:flex;flex-wrap:wrap;gap:6px}#gmfq-pair-research-path button{border:1px solid #3a596d;background:#122d40;border-radius:5px;padding:6px 9px;color:#e6edf4;font:11px Arial,sans-serif;cursor:pointer}#gmfq-pair-research-path button:hover{border-color:#e3c57c;color:#f1d894}#gmfq-pair-research-path button:focus-visible{outline:2px solid #e3c57c;outline-offset:2px}#gmfq-pair-research-path .gmfq-path-warning{color:#dfc894;border-top:1px solid #2a4759;padding-top:10px}@media(max-width:600px){#gmfq-pair-research-path .gmfq-path-legs{grid-template-columns:1fr}#gmfq-pair-research-path .gmfq-path-body{padding:11px}}';
 style.textContent+='.gmfq-compare{border-top:1px solid #2b4757;margin-top:14px;padding-top:13px}.gmfq-compare h3{margin:0 0 11px;font:600 14px/1.3 Arial,sans-serif;color:#e5eff6}.gmfq-compare-score{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.gmfq-compare-score>div{border-left:2px solid #997e4d;padding:7px 10px;background:#0e2534;min-width:0}.gmfq-compare-score span{display:block;font:10px/1.4 Arial,sans-serif;color:#a6bac7}.gmfq-compare-score strong{display:block;font:600 12px/1.5 Arial,sans-serif;color:#e5edf3;margin-top:4px}.gmfq-compare-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.gmfq-compare-leg{min-width:0;padding:10px 12px;border-radius:5px;background:#0a1f2d;border:1px solid #274453}.gmfq-compare-leg strong{display:block;color:#e5eefa;font:600 12px Arial,sans-serif;margin-bottom:5px}.gmfq-compare-leg small{display:block;color:#b2c6d4;font:11px/1.5 Arial,sans-serif;margin:5px 0;overflow-wrap:anywhere}.gmfq-compare p{font:12px/1.55 Arial,sans-serif;margin:10px 0 0}.gmfq-compare .gmfq-compare-spread{color:#e1c990}.gmfq-compare .gmfq-compare-note{color:#cadbe5}.gmfq-compare .gmfq-compare-disclaimer{font-size:10px;color:#9ab4c5}@media(max-width:600px){.gmfq-compare-score,.gmfq-compare-legs{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-what-changed{border-top:1px solid #284354;margin-top:16px;padding-top:14px}.gmfq-what-changed h3{margin:0;color:#e9f1f7;font:600 14px/1.4 Arial,sans-serif}.gmfq-what-changed>p{font:12px/1.55 Arial,sans-serif;color:#abc3d2;margin:7px 0 11px}.gmfq-change-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.gmfq-change-leg{border-left:2px solid #58718a;padding:9px 11px;background:#0d2332;min-width:0}.gmfq-change-leg strong{display:block;font:600 13px Arial,sans-serif;color:#e8f0f6;margin-bottom:8px}.gmfq-change-leg span{display:block;font:10px/1.4 Arial,sans-serif;color:#a0b6c5;letter-spacing:.02em}.gmfq-change-leg p{font:12px/1.5 Arial,sans-serif;color:#d2e0e9;margin:4px 0 11px;overflow-wrap:anywhere}.gmfq-change-leg .gmfq-change-measured{color:#e1c78a;margin-bottom:0}.gmfq-what-changed .gmfq-change-summary{color:#c5d7e2}.gmfq-what-changed .gmfq-change-warning{color:#93abba;font-size:10px}@media(max-width:600px){.gmfq-change-legs{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-reaction{border-top:1px solid #294557;margin-top:15px;padding-top:14px}.gmfq-reaction h3{font:600 14px/1.4 Arial,sans-serif;margin:0 0 9px;color:#e6eff5}.gmfq-reaction p{color:#b4c8d5;font:12px/1.55 Arial,sans-serif;margin:7px 0 11px}.gmfq-reaction .gmfq-reaction-window{font:11px/1.5 Arial,sans-serif;color:#dec98f;padding:5px 0}.gmfq-reaction-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:9px 0}.gmfq-reaction-metrics>div{border:1px solid #294554;border-radius:5px;padding:11px 12px;min-width:0;background:#0b2434}.gmfq-reaction-metrics span{display:block;color:#a4bbc9;font:10px/1.45 Arial,sans-serif}.gmfq-reaction-metrics strong{display:block;color:#edf2f7;font:600 21px/1.4 Arial,sans-serif;font-variant-numeric:tabular-nums;margin:3px 0}.gmfq-reaction-metrics small{display:block;color:#b4c7d5;font:11px/1.45 Arial,sans-serif;overflow-wrap:anywhere}.gmfq-reaction .gmfq-reaction-verdict{border-left:2px solid #a08b58;padding:8px 11px;background:#102638;color:#cbdce7}.gmfq-reaction-verdict strong{color:#e6d59c}.gmfq-reaction-verdict[data-reaction-verdict="COERENTE"]{border-color:#3ac998}.gmfq-reaction-verdict[data-reaction-verdict="DIVERGENTE"]{border-color:#e36a79}.gmfq-reaction .gmfq-reaction-note{color:#a9bdcb}.gmfq-reaction .gmfq-reaction-warning{color:#94abbc;font-size:10px}@media(max-width:600px){.gmfq-reaction-metrics{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-decision-bridge{border-top:1px solid #294456;margin-top:14px;padding-top:13px}.gmfq-decision-bridge h3{font:600 14px/1.4 Arial,sans-serif;margin:0 0 9px;color:#ebf2f6}.gmfq-decision-bridge>p{color:#a8bfcd;font:12px/1.55 Arial,sans-serif;margin:7px 0 10px}.gmfq-decision-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:11px}.gmfq-decision-cols>div{border-left:2px solid #577a90;background:#0b2231;padding:9px 11px;min-width:0}.gmfq-decision-cols>div:nth-child(2){border-color:#ae935d}.gmfq-decision-cols>div:nth-child(3){border-color:#699cba}.gmfq-decision-cols span{display:block;color:#9db3c3;font:10px/1.4 Arial,sans-serif}.gmfq-decision-cols strong{display:block;color:#e9f1f6;font:600 12px/1.5 Arial,sans-serif;margin:4px 0}.gmfq-decision-cols small{display:block;color:#b7cad6;font:11px/1.5 Arial,sans-serif;overflow-wrap:anywhere}.gmfq-decision-watch{padding:10px 0 0;margin-top:10px;border-top:1px solid #264254}.gmfq-decision-watch strong{color:#e5d199;font:600 12px/1.4 Arial,sans-serif}.gmfq-decision-watch p{color:#bcd0dc;font:12px/1.55 Arial,sans-serif;margin:4px 0 0}.gmfq-decision-bridge .gmfq-decision-context{color:#b1c4d1}.gmfq-decision-bridge .gmfq-decision-disclaimer{font-size:10px;color:#93aabb}@media(max-width:700px){.gmfq-decision-cols{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-evidence-checklist{border-top:1px solid #294252;margin-top:13px;padding-top:11px}.gmfq-evidence-checklist h4{font:600 13px/1.45 Arial,sans-serif;color:#e8eef5;margin:0 0 6px}.gmfq-evidence-checklist .gmfq-evidence-intro{color:#aebfcd;font:11px/1.5 Arial,sans-serif;margin:0 0 9px}.gmfq-evidence-rows{display:grid;grid-template-columns:1fr;gap:0}.gmfq-evidence-row{padding:8px 0;border-top:1px solid #243f4e}.gmfq-evidence-row b{color:#e3ce95;font:600 11px/1.4 Arial,sans-serif}.gmfq-evidence-row:nth-child(2) b{color:#d7a3ac}.gmfq-evidence-row p{color:#c0d2dc;font:12px/1.5 Arial,sans-serif;margin:4px 0;overflow-wrap:anywhere}.gmfq-evidence-checklist .gmfq-evidence-provenance{color:#d0dfeb;font:11px/1.55 Arial,sans-serif;margin:9px 0 4px}.gmfq-evidence-checklist .gmfq-evidence-caution{color:#91a9b8;font:10px/1.55 Arial,sans-serif;margin:7px 0}';
 doc.head.appendChild(style);
 const panel=doc.createElement('section');
 panel.id='gmfq-pair-research-path';panel.className='desk-panel';
 panel.setAttribute('aria-label','Collegamenti analisi delle due valute');
 host.insertAdjacentElement('afterend',panel);
 const pairIds=new Set(Object.keys(setup.pairs||{}));
 const labels={macro:'Macro',tassi:'Tassi / OIS',banche:'Banche centrali',cot:'COT'};
 const leg=(c)=>{
  const r=rates?.[c],o=ois?.currencies?.[c];
  const rateDay=r?.date,rateState=r&&String(r.quality||'').includes('OFFICIAL')&&fresh(rateDay,5) &&
   num(r['2Y'])!==null&&num(r['10Y'])!==null;
  const oisDay=o?.as_of,oisState=o?.operational_status==='GREEN_OFFICIAL'&&
   o.quality==='OFFICIAL_CERTIFIED'&&fresh(oisDay,5);
  const rateText='2Y/10Y '+(rateState?'ufficiali':'non correnti o incompleti')+
   ' · '+(rateDay||'n.d.');
  const oisText='pricing '+(oisState?'certificato':'non certificato')+
   ' · '+(oisDay||'n.d.');
  return '<article class="gmfq-path-leg"><strong>'+FLAG[c]+' '+c+' · '+BANK[c]+'</strong>'+
   '<small>'+htmlEscape(rateText)+'; '+htmlEscape(oisText)+'</small>'+
   '<div class="gmfq-path-links">'+Object.entries(labels).map(([r,n])=>
    '<button type="button" data-gmfq-study-route="'+r+'" data-gmfq-study-currency="'+c+
    '" aria-label="Apri '+htmlEscape(n)+' '+c+'">'+htmlEscape(n)+'</button>').join('')+
   '</div></article>';
 };
 const refresh=()=>{
  if(frame.contentDocument!==doc||route()!=='coppie')return;
  if(doc.documentElement.dataset.pairState!=='READY')return;
  const marker=host.querySelector('.desk-kicker')?.textContent||'';
  const match=marker.match(/PAIR DEEP DIVE\s*[·:]\s*([A-Z]{6})/);
  const code=match?.[1];if(!code||!pairIds.has(code))return;
  if(panel.dataset.pair===code)return;
  panel.dataset.pair=code;
  const [a,b]=[code.slice(0,3),code.slice(3,6)];
  const fav=setup.pairs[code]?.setup?.structuralFav;
  const fxDay=fxOk?fx.last_as_of:null;
  const differs=fxDay&&fxDay!==setup.price_asof;
  const macroDay=setup.macro_baseline_asof;
  const macroWarning=!fresh(macroDay,10)?'Baseline Macro/Tassi del motore ('+(macroDay||'as-of non certificato')+') non corrente: la preferenza strutturale è storica e va rivalidata. ':'';
  const sourceMsg=differs?'Il fixing BCE è più recente dello snapshot della tesi. Il movimento dal '+
    setup.price_asof+' al '+fxDay+' non aggiorna automaticamente il giudizio del motore.':
    'La data del fixing e quella del motore coincidono, oppure il fixing più recente non è verificato.';
  panel.innerHTML='<h2 class="desk-panel-title">Percorso di ricerca · '+FLAG[a]+' '+a+' / '+FLAG[b]+' '+b+'</h2>'+
   '<div class="gmfq-path-body"><p>Prima confronta Macro e Tassi delle due valute, poi guarda Banche centrali e COT. Torna al Prezzo per verificare conferma o divergenza. Il dettaglio sopra resta la lettura canonica della tesi, non un segnale di ingresso.</p>'+
   '<div class="gmfq-path-evidence">Modello: '+htmlEscape(setup.price_asof)+' · Fixing BCE: '+htmlEscape(fxDay||'non verificato')+
   ' · Baseline Macro/Tassi: '+htmlEscape(macroDay||'non certificata')+' · Valuta favorita dal motore: '+htmlEscape(fav||'nessuna')+'</div>'+
   pairMacroRatesComparison(code,setup.pairs[code],rates,ois,setup.price_asof,macroDay)+pairWhatChangedEvidence(code,setup.pairs[code],rates,setup.price_asof)+(reaction=>reaction+pairThesisReactionBridge(code,setup.pairs[code],setup.price_asof,reaction,macroDay))(pairMarketReactionAudit(code,rates,fx))+'<div class="gmfq-path-legs">'+leg(a)+leg(b)+'</div>'+
   '<p class="gmfq-path-warning">'+htmlEscape(macroWarning+sourceMsg)+' I futures indicativi non sono curve OIS e non determinano da soli un trade.</p>'+
   '<div class="gmfq-path-links"><button type="button" data-gmfq-study-route="screener">Apri Screener 28 coppie ↗</button></div></div>';
 };
 const obs=new MutationObserver(refresh);
 obs.observe(host,{childList:true});
 const selected=()=>{const x=host.querySelector('.desk-kicker')?.textContent||'';return x.includes('PAIR DEEP DIVE')};
 if(selected())refresh();
 doc.addEventListener('click',e=>{
  const b=e.target.closest('button[data-gmfq-study-route]');
  if(b&&panel.contains(b)){
   const r=b.dataset.gmfqStudyRoute,ccy=b.dataset.gmfqStudyCurrency;
   if(r==='screener'){go('#/screener');return}
   if(['macro','tassi','banche','cot'].includes(r)&&FX.includes(ccy))go('#/'+r+'?ccy='+ccy);
   return;
  }
  const row=e.target.closest('button.pair-open[data-pair]');
  if(row&&doc.getElementById('pair-index')?.contains(row)){
   const code=row.dataset.pair;
   if(pairIds.has(code))history.replaceState(history.state,'','#/coppie?pair='+code);
  }
 },true); // capture: original pair buttons can stop bubbling after updating the detail
}
function mountScreenerPairBridge(doc){
 if(route()!=='screener'||frame.contentDocument!==doc)return;
 const code=new URLSearchParams(location.hash.split('?')[1]||'').get('pair')?.toUpperCase();
 if(!/^[A-Z]{6}$/.test(code||''))return;
 // No fabricated pair details: link to the existing canonical analysis only.
 const main=doc.querySelector('.desk-main'),hero=doc.querySelector('.desk-hero');
 if(!main||!hero||doc.getElementById('gmfq-screener-pair-bridge'))return;
 const p=doc.createElement('p');
 p.id='gmfq-screener-pair-bridge';
 p.style.cssText='margin:10px 0;padding:10px 14px;border:1px solid #2d4b5e;border-radius:5px;color:#c3d2dd;font-size:12px;background:#102639';
 p.textContent='Coppia selezionata: '+FLAG[code.slice(0,3)]+' '+FLAG[code.slice(3,6)]+' '+code+' · ';
 const b=doc.createElement('button');b.type='button';b.textContent='Apri Pair Deep Dive ↗';
 b.style.cssText='cursor:pointer;border:1px solid #587080;border-radius:4px;background:#20394a;color:#f1d28e;padding:5px 8px';
 b.addEventListener('click',()=>go('#/coppie?pair='+code));p.appendChild(b);
 hero.insertAdjacentElement('afterend',p);
}


/* Additive Cross-Asset Gold readout. Never alters the 32 approved visual parts. */
function validCrossGold(doc,gold){
 const govern=doc?.governance||{};
 if(doc?.schema!=='GMFQ_ESTIMATED_RESIDUAL_GAPS_V1'||doc?.official_lanes_untouched!==true||
    govern.core_score_effect!=='NONE'||govern.bias_effect!=='NONE'||
    govern.sizing_effect!=='NONE'||govern.pair_engine_effect!=='NONE'||
    govern.forward_logger_effect!=='NONE'||govern.backtest_eligible_as_official!==false)return false;
 if(gold?.status!=='MARKET_PROXY_ACTIVE_SECONDARY'||gold.vendor_symbol!=='GC=F'||
    gold.currency!=='USD'||gold.instrument_type!=='FUTURE'||
    gold.official_canonical_untouched!==true||
    gold.source_endpoint!=='https://query1.finance.yahoo.com/v8/finance/chart/GC=F'||
    !/^20\d{2}-\d{2}-\d{2}$/.test(gold.proxy_as_of||'')||
    typeof gold.value!=='number'||!Number.isFinite(gold.value)||gold.value<=0)return false;
 const date=new Date(gold.proxy_as_of+'T00:00:00Z');
 if(Number.isNaN(date.getTime())||date.toISOString().slice(0,10)!==gold.proxy_as_of)return false;
 const today=new Date(),day=Date.UTC(today.getUTCFullYear(),today.getUTCMonth(),today.getUTCDate());
 const gap=(day-date.getTime())/86400000;
 return gap>=0;
}
function crossGoldAge(iso){
 const now=new Date(),day=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
 return Math.round((day-Date.parse(iso+'T00:00:00Z'))/86400000);
}
function crossGoldNumber(x){return typeof x==='number'&&Number.isFinite(x)?x.toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}
function crossGoldPct(x){return typeof x==='number'&&Number.isFinite(x)?(x>0?'+':'')+x.toFixed(2)+'%':'—'}
async function mountCrossGold(doc){
 if(route()!=='cross'||frame.contentDocument!==doc)return;
 const main=doc.querySelector('.desk-main'),anchor=main?.querySelector('.desk-grid');
 if(!anchor||doc.getElementById('gmfq-cross-gold-v10'))return;
 const style=doc.createElement('style');
 style.id='gmfq-cross-gold-v10-style';
 style.textContent=
  '#gmfq-cross-gold-v10{margin:0 0 14px;min-width:0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-body{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:13px;padding:14px 17px 16px;min-width:0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-column{min-width:0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-quote{font:650 28px/1.2 Arial,sans-serif;color:#e8f0f7;font-variant-numeric:tabular-nums;margin:9px 0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-badge{font:600 10px/1.5 Arial,sans-serif;color:#e3ca83}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-badge[data-state="WITHHELD"]{color:#efa7b1}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-line{font:11px/1.55 Arial,sans-serif;color:#afc4d2;margin:7px 0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-changes{display:flex;gap:15px;flex-wrap:wrap;font:12px Arial,sans-serif;color:#e1d19a;margin:12px 0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-spot{padding:12px 14px;border-left:2px solid #90784f;background:#0e2534;min-width:0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-spot strong{display:block;font:600 13px/1.4 Arial,sans-serif;color:#d5e3ee;margin-bottom:7px}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-fine{padding:0 17px 13px;color:#8fa8b9;font:10px/1.55 Arial,sans-serif}'+
  '@media(max-width:700px){#gmfq-cross-gold-v10 .gmfq-gold-body{grid-template-columns:1fr;padding:12px;gap:10px}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-quote{font-size:25px}#gmfq-cross-gold-v10 .gmfq-gold-fine{padding:0 12px 12px}}';
 doc.head.appendChild(style);
 const title=doc.getElementById('queued-title'),copy=doc.getElementById('queued-copy');
 if(title)title.textContent='Cross-Asset · Metalli';
 if(copy)copy.textContent='Primo layer informativo attivo: oro futures. Gli altri approfondimenti Cross-Asset restano in preparazione.';
 const panel=doc.createElement('section');
 panel.id='gmfq-cross-gold-v10';panel.className='desk-panel';
 panel.setAttribute('aria-label','Gold futures e disponibilità del fixing spot ufficiale');
 panel.dataset.sourceStatus='LOADING';
 panel.innerHTML='<h2 class="desk-panel-title">Gold · contesto di rischio</h2><div class="desk-panel-body">Verifica della fonte in corso…</div>';
 anchor.insertAdjacentElement('beforebegin',panel);
 let gold=null,valid=false;
 try{
  const data=await feed('ESTIMATED_RESIDUAL_GAPS.json');
  if(frame.contentDocument!==doc||route()!=='cross')return;
  gold=data?.lanes?.['GOLD.market_proxy'];
  valid=validCrossGold(data,gold);
 }catch(e){console.warn('[GMFQ Gold secondary WITHHELD]',String(e))}
 const current=valid&&crossGoldAge(gold.proxy_as_of)<=3;
 const state=!valid?'WITHHELD':current?'SECONDARY_CURRENT':'SECONDARY_HISTORICAL';
 const asof=valid?gold.proxy_as_of:'—';
 const headline=current?'FUTURES INDICATIVO · RECENTE':state==='SECONDARY_HISTORICAL'?'FUTURES INDICATIVO · NON CORRENTE':'FUTURES · DATI NON VERIFICABILI';
 panel.dataset.sourceStatus=state;
 panel.dataset.goldAsOf=asof;
 panel.innerHTML='<h2 class="desk-panel-title">Gold · contesto di rischio</h2>'+
  '<div class="gmfq-gold-body"><div class="gmfq-gold-column">'+
  '<div class="gmfq-gold-badge" data-state="'+state+'">'+headline+'</div>'+
  '<div class="gmfq-gold-quote">'+(valid?crossGoldNumber(gold.value)+' <small style="font-size:12px">USD/oz</small>':'—')+'</div>'+
  '<div class="gmfq-gold-line">GC=F · futures COMEX indicativo · as-of '+htmlEscape(asof)+'</div>'+
  '<div class="gmfq-gold-changes"><span>Δ 1D: '+(valid?crossGoldPct(gold.change_1d_pct):'—')+
  '</span><span>Δ ~1W: '+(valid?crossGoldPct(gold.change_1w_pct):'—')+'</span></div>'+
  '<div class="gmfq-gold-line">Fonte: Yahoo Finance, quotazione futures secondaria'+
   (state==='SECONDARY_HISTORICAL'?'. Dato storico, non utilizzabile come prezzo corrente.':'.')+'</div></div>'+
  '<div class="gmfq-gold-spot"><strong>Gold Price LBMA · WITHHELD</strong>'+
  '<p class="gmfq-gold-line">Nessuna quotazione spot ufficiale certificata in questo feed. Le tre osservazioni Gold legacy non hanno provenienza verificata e non sono usate in questo confronto.</p>'+
  '<p class="gmfq-gold-line">Un futures indicativo non equivale a oro spot o fixing LBMA: non confondere strumenti, orari di rilevazione e metodologie.</p></div></div>'+
  '<div class="gmfq-gold-fine">Solo contesto cross-asset · Non è un prezzo di regolamento certificato, un segnale, un livello operativo o un input per Macro/FX, bias, sizing e backtest.</div>';
 doc.defaultView.GMFQ_CROSS_GOLD={status:state,as_of:asof,instrument:'GC=F',core_effect:'NONE',lbma_spot:'WITHHELD'};
}


/* Native v10 Cross-Asset risk / energy. Strictly informational; no FX model inputs. */
function crossRiskObservation(series,instrument){
 const ds=series?.dates,vs=series?.values;
 if(!Array.isArray(ds)||!Array.isArray(vs)||ds.length<2||ds.length!==vs.length)
   return {state:'WITHHELD',value:null,asof:'—',delta:null};
 const date=ds.at(-1),value=vs.at(-1);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||
    series.last_date!==date||
    typeof value!=='number'||!Number.isFinite(value)||value<=0||
    typeof series.last_value!=='number'||!Number.isFinite(series.last_value)||
    series.last_value!==value||
    (instrument==='WTI'&&(series.source!=='U.S. Energy Information Administration'||
      series.benchmark_key!=='RWTC')))
   return {state:'WITHHELD',value:null,asof:'—',delta:null};
 const day=new Date(date+'T00:00:00Z');
 if(Number.isNaN(day.getTime())||day.toISOString().slice(0,10)!==date)return {state:'WITHHELD',value:null,asof:'—',delta:null};
 const age=crossGoldAge(date);
 if(age<0)return {state:'WITHHELD',value:null,asof:'—',delta:null};
 const prev=vs.at(-2);
 const prevDate=ds.at(-2);
 const change=typeof prev==='number'&&Number.isFinite(prev)&&prev>0&&
   /^\d{4}-\d{2}-\d{2}$/.test(prevDate||'')&&prevDate<date?(value/prev-1)*100:null;
 return {state:age<=3?'OFFICIAL_RECENT':'OFFICIAL_HISTORICAL',
   value,asof:date,delta:change};
}
function crossRiskBrent(res){
 const b=res?.lanes?.['BRENT.market_proxy'],g=res?.governance||{};
 const governance=res?.schema==='GMFQ_ESTIMATED_RESIDUAL_GAPS_V1'&&
   res.official_lanes_untouched===true&&
   g.core_score_effect==='NONE'&&g.bias_effect==='NONE'&&
   g.sizing_effect==='NONE'&&g.pair_engine_effect==='NONE'&&
   g.forward_logger_effect==='NONE'&&g.backtest_eligible_as_official===false;
 const allowed=governance&&b?.status==='MARKET_PROXY_ACTIVE_SECONDARY'&&
   b.vendor_symbol==='BZ=F'&&b.instrument_type==='FUTURE'&&
   b.currency==='USD'&&b.official_canonical_untouched===true&&
   b.source_endpoint==='https://query1.finance.yahoo.com/v8/finance/chart/BZ=F'&&
   typeof b.value==='number'&&Number.isFinite(b.value)&&b.value>0&&
   /^\d{4}-\d{2}-\d{2}$/.test(b.proxy_as_of||'');
 if(!allowed)return {state:'WITHHELD',value:null,asof:'—',delta:null,week:null};
 const day=new Date(b.proxy_as_of+'T00:00:00Z');
 if(Number.isNaN(day.getTime())||day.toISOString().slice(0,10)!==b.proxy_as_of)
   return {state:'WITHHELD',value:null,asof:'—',delta:null,week:null};
 const age=crossGoldAge(b.proxy_as_of);
 if(age<0)return {state:'WITHHELD',value:null,asof:'—',delta:null,week:null};
 return {state:age<=3?'SECONDARY_RECENT':'SECONDARY_HISTORICAL',
   value:b.value,asof:b.proxy_as_of,delta:b.change_1d_pct,week:b.change_1w_pct};
}
function crossRiskCard(code,row,description,source,secondary){
 const current=['OFFICIAL_RECENT','SECONDARY_RECENT'].includes(row.state);
 const unavailable=row.state==='WITHHELD';
 const badge=unavailable?'WITHHELD · non verificato':current?
   (secondary?'FUTURES INDICATIVO · RECENTE':'FONTE UFFICIALE · ULTIMA OSSERVAZIONE'):
   (secondary?'FUTURES INDICATIVO · STORICO':'FONTE UFFICIALE · NON CORRENTE');
 const change=unavailable?'—':crossGoldPct(row.delta);
 const quoted=unavailable?'—':crossGoldNumber(row.value)+(code==='VIX'?'':' <small>USD/barile</small>');
 return '<article class="gmfq-cross-risk-card" data-cross-instrument="'+code+
   '" data-cross-status="'+row.state+'">'+
   '<div class="gmfq-cross-risk-header"><strong>'+code+'</strong><span class="gmfq-cross-risk-badge" data-state="'+
   row.state+'">'+badge+'</span></div>'+
   '<p class="gmfq-cross-risk-source">'+htmlEscape(description)+'</p>'+
   '<div class="gmfq-cross-risk-value">'+quoted+'</div>'+
   '<p class="gmfq-cross-risk-source">as-of '+htmlEscape(row.asof)+'</p>'+
   '<div class="gmfq-cross-risk-changes"><span>Δ '+(secondary?'1D':'oss. prec.')+
   ' '+change+'</span>'+(secondary?'<span>Δ ~1W '+(unavailable?'—':crossGoldPct(row.week))+'</span>':'')+'</div>'+
   '<p class="gmfq-cross-risk-source">'+htmlEscape(source)+'</p></article>';
}
async function mountCrossRisk(doc){
 if(route()!=='cross'||frame.contentDocument!==doc)return;
 const goldPanel=doc.getElementById('gmfq-cross-gold-v10');
 const main=doc.querySelector('.desk-main'),anchor=main?.querySelector('.desk-grid');
 if(!anchor||doc.getElementById('gmfq-cross-risk-v10'))return;
 const panel=doc.createElement('section');
 panel.id='gmfq-cross-risk-v10';
 panel.className='desk-panel';
 panel.dataset.sourceStatus='LOADING';
 panel.setAttribute('aria-label','VIX, WTI spot EIA e Brent futures indicativo');
 panel.innerHTML='<h2 class="desk-panel-title">Volatilità e petrolio · verifica delle fonti</h2>'+
   '<div class="desk-panel-body">Caricamento fonti…</div>';
 if(goldPanel)goldPanel.insertAdjacentElement('afterend',panel);
 else anchor.insertAdjacentElement('beforebegin',panel);
 const style=doc.createElement('style');
 style.id='gmfq-cross-risk-v10-style';
 style.textContent=
  '#gmfq-cross-risk-v10{margin:0 0 14px;min-width:0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-intro{padding:12px 16px 4px;font:12px/1.55 Arial,sans-serif;color:#abc2d0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:10px 16px;min-width:0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-card{min-width:0;padding:13px;background:#0b2333;border:1px solid #254457;border-radius:6px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-header{display:flex;flex-wrap:wrap;gap:7px;align-items:center;justify-content:space-between}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-header strong{font:650 15px/1.4 Arial,sans-serif;color:#ebf2f6}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-badge{font:600 9px/1.4 Arial,sans-serif;color:#86d6b3}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-badge[data-state*="HISTORICAL"]{color:#e8c080}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-badge[data-state="WITHHELD"]{color:#e9a0af}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-source{font:10px/1.5 Arial,sans-serif;color:#9db6c5;margin:6px 0;overflow-wrap:anywhere}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-value{font:650 26px/1.3 Arial,sans-serif;color:#e9f1f7;margin:11px 0 4px;font-variant-numeric:tabular-nums}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-value small{font:11px Arial,sans-serif;color:#afc2d0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-changes{color:#dacb9d;font:11px/1.5 Arial,sans-serif;display:flex;flex-wrap:wrap;gap:9px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-note{border-top:1px solid #213f50;padding:12px 16px;color:#a9c1cf;font:11px/1.6 Arial,sans-serif}'+
  '@media(max-width:820px){#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{grid-template-columns:1fr}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-intro{padding:12px 12px 4px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{padding:10px 12px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-note{padding:12px}}';
 doc.head.appendChild(style);
 const title=doc.getElementById('queued-title'),copy=doc.getElementById('queued-copy');
 if(title)title.textContent='Cross-Asset · Rischio e commodities';
 if(copy)copy.textContent='Gold, VIX ed energia: dati distinti per fonte e aggiornamento. Altri approfondimenti restano in preparazione.';
 let d=null,res=null;
 try{
  const settled=await Promise.allSettled([feed('D.json'),feed('ESTIMATED_RESIDUAL_GAPS.json')]);
  if(frame.contentDocument!==doc||route()!=='cross')return;
  d=settled[0].status==='fulfilled'?settled[0].value:null;
  res=settled[1].status==='fulfilled'?settled[1].value:null;
 }catch(e){console.warn('[GMFQ Cross Risk WITHHELD]',String(e))}
 const v=crossRiskObservation(d?.risk?.VIX,'VIX'),
   w=crossRiskObservation(d?.risk?.WTI,'WTI'),b=crossRiskBrent(res);
 const states=[v.state,w.state,b.state];
 const global=states.every(x=>x==='WITHHELD')?'WITHHELD':
   states.some(x=>x==='WITHHELD'||x.endsWith('HISTORICAL'))?'PARTIAL':'AVAILABLE';
 panel.dataset.sourceStatus=global;
 panel.innerHTML='<h2 class="desk-panel-title">Volatilità e petrolio · stato delle fonti</h2>'+
  '<p class="gmfq-cross-risk-intro">VIX e WTI sono osservazioni ufficiali con una data di riferimento, NON quotazioni intraday. Brent è un futures indicativo e non sostituisce il prezzo spot certificato.</p>'+
  '<div class="gmfq-cross-risk-grid">'+
   crossRiskCard('VIX',v,'Volatilità implicita S&P 500','Cboe · storico ufficiale VIX',false)+
   crossRiskCard('WTI',w,'Spot Cushing · RWTC','U.S. Energy Information Administration',false)+
   crossRiskCard('BRENT',b,'Futures BZ=F · non spot','Yahoo Finance · futures secondario',true)+
  '</div>'+
  '<div class="gmfq-cross-risk-note"><strong>Come leggere questi dati:</strong> il VIX misura volatilità implicita, non da solo la direzione del mercato. WTI e Brent non sono la stessa serie né lo stesso strumento: domanda, offerta, scadenza dei futures e differenze di rilevazione contano. <strong>Brent spot ufficiale: WITHHELD.</strong> Nessun confronto di spread fra spot e futures; nessun giudizio di risk-on/risk-off, segnale o sizing automatico.</div>';
 doc.defaultView.GMFQ_CROSS_RISK={status:global,
   vix:{status:v.state,as_of:v.asof},wti:{status:w.state,as_of:w.asof},
   brent:{status:b.state,as_of:b.asof},core_effect:'NONE',
   official_brent:'WITHHELD'};
}

const mountedDocuments=new WeakSet();
function onFrameLoad(){
 let doc;try{doc=frame.contentDocument}catch(_){return}
 if(!doc?.body||mountedDocuments.has(doc))return;
 mountedDocuments.add(doc);
 if(!home()){
   if(route()==='cross')mountCrossGold(doc).catch(e=>console.warn('[GMFQ Cross-Asset Gold WITHHELD]',e));
   if(route()==='cross')mountCrossRisk(doc).catch(e=>console.warn('[GMFQ Cross-Asset Risk WITHHELD]',e));
   if(route()==='tassi'){enhanceRatesDetail(doc);focusRatesSection(doc);applyMarketResearch(doc).catch(e=>console.warn('[GMFQ market pricing WITHHELD]',e))}
   if(route()==='coppie')mountPairResearch(doc).catch(e=>console.warn('[GMFQ pair research WITHHELD]',e));
   if(route()==='screener')mountScreenerPairBridge(doc);
   focusCurrency(doc);
   return;
 }
 style(doc);navigation(doc);applyHome(doc).catch(e=>console.warn('[GMFQ home extension WITHHELD]',e));
}
frame.addEventListener('load',onFrameLoad);
// The approved page can load its iframe before this additive script subscribes.
// Reuse the same guarded mount path; never double-inject into one document.
try{if(frame.contentDocument?.readyState==='complete')onFrameLoad()}catch(_){/* cross-document transition */}
})();
