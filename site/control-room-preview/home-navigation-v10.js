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
/* Italy-facing research day, independent of viewer timezone and CET/CEST.
   Source as-of dates stay unchanged; this function is display eligibility only. */
function romeTodayIso(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Europe/Rome',
   year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
 const val=k=>parts.find(p=>p.type===k)?.value;
 return val('year')+'-'+val('month')+'-'+val('day');
}
function romeCalendarAge(date,now=new Date()){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))return null;
 const t=Date.parse(date+'T00:00:00Z');
 if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,10)!==date)return null;
 return (Date.parse(romeTodayIso(now)+'T00:00:00Z')-t)/86400000;
}
function fresh(date,max=4){const days=romeCalendarAge(date);return days!==null&&days>=0&&days<=max}
/* Same approved operational pricing eligibility in Home, Rates, Pair.
   Rates 2Y/10Y have their own distinct 5-day observation contract.
   The backend's 28-pair source coverage audit also uses 4 days for OIS. */
function officialPricingCurrent(x){
 return !!x&&x.operational_status==='GREEN_OFFICIAL'&&
  x.official_status==='ACTIVE'&&x.quality==='OFFICIAL_CERTIFIED'&&
  x.backtest_eligible_as_official===true&&fresh(x.as_of,4)&&
  ['3m','6m','12m'].every(t=>num(x.horizons?.[t]?.rate)!==null&&
   num(x.horizons?.[t]?.policy_delta_bp)!==null);
}

/* Fed policy decisions and Fed Funds futures have separate observation dates.
   Keep stale policy-book pricing and pre-FOMC secondary quotes visible ONLY as
   explicitly dated research context, never as post-meeting repricing. */
function fedPricingFreshnessAudit(fed,usd,today){
 const policy=typeof fed?.last_date==='string'?fed.last_date:'';
 const raw=typeof fed?.market_pricing?.as_of==='string'?fed.market_pricing.as_of:'';
 const legacyMonth=/^20\d{2}-\d{2}/.exec(raw)?.[0]||null;
 const legacyStale=!!legacyMonth&&legacyMonth<today.slice(0,7);
 const expected=['3m','6m','12m'];
 const rows=expected.map(h=>usd?.horizons?.[h]||{});
 const dated=rows.map(x=>x.quote_as_of);
 const sameDate=dated.every(d=>/^20\d{2}-\d{2}-\d{2}$/.test(d||'')&&d===dated[0]);
 const date=dated[0]||null;
 const verified=usd?.operational_status==='GREEN_ESTIMATED'&&
  usd.quality==='ESTIMATED_INFORMATIONAL'&&
  usd.backtest_eligible_as_official===false&&
  typeof usd.source==='string'&&usd.source.includes('TradingView')&&
  sameDate&&date===usd.as_of&&date<=today&&
  (Date.parse(today+'T00:00:00Z')-Date.parse(date+'T00:00:00Z'))<=4*86400000&&
  rows.every(x=>x.quote_timestamp_verified===true&&
   /^ZQ[A-Z]\d{4}$/.test(x.contract||'')&&
   typeof x.rate==='number'&&Number.isFinite(x.rate)&&
   typeof x.futures_price==='number'&&Number.isFinite(x.futures_price)&&
   Math.abs(x.rate-(100-x.futures_price))<0.0002);
 const preDecision=verified&&/^20\d{2}-\d{2}-\d{2}$/.test(policy)&&date<policy;
 const label='🇺🇸 Fed · pricing separato: ';
 const legacy=legacyStale?'lo snapshot futures nel registro delle banche centrali è storico ('+
  legacyMonth+'), NON un pricing aggiornato. ':
  'la data del pricing nel registro CB va verificata separatamente. ';
 const context=verified?
  'Futures ZQ indicativi al '+date+': 3M '+rows[0].rate.toFixed(2)+'%, 6M '+
   rows[1].rate.toFixed(2)+'%, 12M '+rows[2].rate.toFixed(2)+'%. '+
   (preDecision?'Quotazioni PRECEDENTI alla decisione Fed del '+policy+
    ': non misurano il repricing successivo. ':
    'Quotazioni successive/allineate alla decisione, ma non certificano un repricing di meeting. '):
  'Nessun set 3M/6M/12M di futures USD simultaneamente datato e verificato utilizzabile qui. ';
 return {
  state:legacyStale?(preDecision?'LEGACY_STALE_PRE_DECISION':verified?
   'LEGACY_STALE_SECONDARY_ONLY':'LEGACY_STALE_NO_SECONDARY'):'LEGACY_DATE_UNVERIFIED',
  legacy_month:legacyMonth,quote_date:verified?date:null,pre_decision:!!preDecision,
  quoted_levels_visible:!!verified,
  text:label+legacy+context+'Fonte secondaria, non OIS; nessuna probabilità di rialzo, policy delta o segnale FX derivato.'
 };
}
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
  #ylegend .gmfq-legend-item{background:transparent;border:1px solid transparent;border-radius:4px;padding:1px 3px;cursor:pointer;white-space:nowrap}
  #ylegend .gmfq-legend-item[aria-pressed=true]{background:#1b3a4b;border-color:#648199;color:#f2e4c2}
  #ylegend .gmfq-legend-item:focus-visible{outline:2px solid #edcf8b;outline-offset:2px}
  #ylegend .gmfq-tiny-flag{font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;font-size:12px;vertical-align:middle;margin-right:2px}
  .gridtop .yieldpanel #ylegend .gmfq-legend-row{justify-content:center;gap:2px 4px}
  @media(max-width:600px){#ylegend .gmfq-legend-item{font-size:9px;padding:1px}#ylegend .gmfq-tiny-flag{font-size:11px}}
  .gmfq-chart-note{color:#93a7b8;font:10px/1.35 Arial,sans-serif;margin-top:5px}
  .gmfq-est-note{color:#e0bb6c}
  .gmfq-dxy-dialog{border:1px solid #29465b;border-radius:10px;color:#e4edf5;background:#071827;
    max-width:590px;width:calc(100vw - 24px);box-sizing:border-box;padding:22px 23px;box-shadow:0 24px 65px #000a}
  .gmfq-dxy-dialog::backdrop{background:#020a14be}
  .gmfq-dxy-dialog h2{font:600 20px/1.2 Arial,sans-serif;color:#f2f7fb;margin:0 0 10px}
  .gmfq-dxy-dialog p{font:13px/1.5 Arial,sans-serif;color:#b0c3d2;margin:7px 0}
  .gmfq-dxy-dialog .gmfq-dxy-val{font:600 36px/1.1 Arial,sans-serif;color:#f0f6fe;font-variant-numeric:tabular-nums}
  .gmfq-dxy-dialog button{border:1px solid #435f73;border-radius:6px;color:#dce9f3;background:#12283b;padding:8px 14px;cursor:pointer}
  .gmfq-dxy-dialog .gmfq-source{color:#e6c778;font-size:12px}
  .gmfq-dxy-dialog a{color:#e6c778;text-decoration:underline}
  .gmfq-dxy-dialog svg{width:100%;height:174px;display:block;margin:8px 0 11px}
  .gmfq-dxy-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border-top:1px solid #29465b;border-bottom:1px solid #29465b;margin:12px 0 8px}
  .gmfq-dxy-metrics>div{min-width:0;padding:11px 8px 10px;border-right:1px solid #29465b}
  .gmfq-dxy-metrics>div:first-child{padding-left:0}
  .gmfq-dxy-metrics>div:last-child{border-right:0}
  .gmfq-dxy-metrics small{display:block;color:#9cb2c2;font:10px/1.4 Arial,sans-serif}
  .gmfq-dxy-metrics strong{display:block;color:#e9d092;font:600 15px/1.35 Arial,sans-serif;margin-top:3px;font-variant-numeric:tabular-nums;white-space:nowrap}
  .gmfq-dxy-dialog .gmfq-dxy-context-limit{color:#9fb6c6;font:11px/1.45 Arial,sans-serif}
  @media(max-width:600px){.gmfq-dxy-dialog .gmfq-dxy-metrics strong{font-size:12px}.gmfq-dxy-dialog .gmfq-dxy-metrics>div{padding:9px 5px}}

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
/* Official Japanese yield feed contains unpadded month/day strings and rows
   lexically sorted by those raw strings. Normalize DATE ONLY, preserving each
   value at its original index, then sort the paired observations by ISO day.
   No writeback to source feeds, model scores, rates, CB pricing or ranking. */
function normalizeHistoryDate(raw){
 if(typeof raw!=='string')return null;
 const m=/^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(raw);
 if(!m)return null;
 const y=Number(m[1]),month=Number(m[2]),day=Number(m[3]);
 if(y<1900||y>2100||month<1||month>12||day<1||day>31)return null;
 const dt=new Date(Date.UTC(y,month-1,day));
 if(dt.getUTCFullYear()!==y||dt.getUTCMonth()!==month-1||dt.getUTCDate()!==day)return null;
 return m[1]+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0');
}
function dateHistory(x,which){
 const h=x?.[which];if(!h)return[];
 const cutoff=x?.date?normalizeHistoryDate(x.date):null;
 if(x?.date&&!cutoff)return[];
 const arr=Array.isArray(h)?h.map(p=>({date:p.date,v:num(p.value)})):Array.isArray(h.dates)?h.dates.map((date,i)=>({date,v:num(h.values?.[i])})):[];
 const paired=arr.map(p=>({date:normalizeHistoryDate(p.date),v:p.v}))
   .filter(p=>p.date&&p.v!==null&&(!cutoff||p.date<=cutoff))
   .sort((a,b)=>a.date.localeCompare(b.date));
 // Two source strings must never silently alias to the same trading day.
 for(let i=1;i<paired.length;i++)if(paired[i].date===paired[i-1].date)return[];
 return paired;
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
 const allData=FX.map(c=>({c,series:all[c][key].slice(-90),now:all[c][currentKey],est:which==='2Y'?all[c].estimate2:all[c].estimate10,latest:which==='2Y'?(all[c].estimatedAsOf2||all[c].date):(all[c].estimatedAsOf10||all[c].date)})).filter(x=>x.series.length>4);
 const legendNode=doc.getElementById('ylegend');
 const wanted=legendNode?.dataset.gmfqCurrencyFocus||'USD';
 const focus=wanted==='ALL'||allData.some(x=>x.c===wanted)?wanted:'ALL';
 const data=focus==='ALL'?allData:allData.filter(x=>x.c===focus);
 if(legendNode)legendNode.dataset.gmfqCurrencyFocus=focus;
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
   svg+=`<polyline points="${pts}" fill="none" stroke="${COLOR[x.c]}" stroke-width="${focus==='ALL'?'1.85':'2.9'}" stroke-linecap="round" stroke-linejoin="round" opacity=".98"><title>${x.c} · rendimento ${which} · storico</title></polyline>`;
   if(x.now!==null && x.latest && x.latest>x.series.at(-1).date && !x.est){const last=x.series.at(-1);svg+=`<line x1="${xx(last.date)}" y1="${yy(last.v)}" x2="${xx(x.latest)}" y2="${yy(x.now)}" stroke="${COLOR[x.c]}" stroke-width="1.2" stroke-dasharray="2 3"/><circle cx="${xx(x.latest)}" cy="${yy(x.now)}" r="2.2" fill="${COLOR[x.c]}"/>`;}
   if(x.est&&x.now!==null){const last=x.series.at(-1);svg+=`<line x1="${xx(last.date)}" y1="${yy(last.v)}" x2="${xx(x.latest)}" y2="${yy(x.now)}" stroke="#e8c46d" stroke-width="1.8" stroke-dasharray="3 3"/><circle cx="${xx(x.latest)}" cy="${yy(x.now)}" r="2.6" fill="#e8c46d"/>`}
 }
 svg+=`<text x="${L}" y="${H-2}" fill="#819bad" font-size="9">${min.slice(5)}</text><text x="${W-R}" y="${H-2}" text-anchor="end" fill="#819bad" font-size="9">${max.slice(5)}</text>`;
 const curve=doc.getElementById('curves'),legend=doc.getElementById('ylegend');
 if(!curve||!legend)return;
 curve.dataset.gmfqYieldFocus=focus;curve.dataset.gmfqYieldTenor=which;
 curve.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Serie ${which} di tutte le otto valute G8; eventuali tratti stimati tratteggiati">${svg}</svg>`;
 const chosen=legend.dataset.gmfqYieldMode||'2Y';
 legend.innerHTML=`<div class="gmfq-legend-row">${allData.map(x=>`<button type="button" data-gmfq-ccy-focus="${x.c}" aria-pressed="${focus===x.c}" class="gmfq-legend-item ${x.est?'est':''}" title="Isola ${x.c}; tocca ancora per mostrare tutto il G8"><span class="gmfq-tiny-flag" aria-hidden="true">${FLAG[x.c]}</span><i style="background:${COLOR[x.c]}"></i>${x.c}${x.est?'*':''}</button>`).join('')}
 <button type="button" data-gmfq-tenor="2Y" aria-pressed="${chosen==='2Y'}" style="background:transparent;border:0;color:${chosen==='2Y'?'#f1ca6d':'#93b1c3'};cursor:pointer;padding:0 3px">2Y</button>
 <button type="button" data-gmfq-tenor="10Y" aria-pressed="${chosen==='10Y'}" style="background:transparent;border:0;color:${chosen==='10Y'?'#f1ca6d':'#93b1c3'};cursor:pointer;padding:0 3px">10Y</button></div>`;
 const note=curve.parentElement?.querySelector('.gmfq-chart-note')||doc.createElement('div');
 note.className='gmfq-chart-note';
 const picked=data.length===1?data[0]:null;
 note.textContent=(picked?FLAG[picked.c]+' '+picked.c+' · '+which+' '+fmt(picked.now!==null?picked.now:picked.series.at(-1).v,2)+'% · '+(picked.latest||picked.series.at(-1).date)+(picked.est?' · STIMA':' · rilevato'):'G8 · '+which+' · confronto tra tutte le valute')+
  '. Tocca una bandierina per isolare la valuta o tornare al confronto. * Il tratteggio oro indica stime β: non sono segnali.';
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
 let svg='<defs><linearGradient id="gmfq-bars-sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#fff" stop-opacity=".10"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>';
 for(let i=0;i<=4;i++){
  const guide=T+(H-T-B)*i/4;
  svg+=`<line x1="${L}" x2="${W-R}" y1="${guide}" y2="${guide}" stroke="#294659" stroke-width=".7" stroke-dasharray="2 5" opacity=".7"/>`;
 }
 svg+=`<line x1="${L}" x2="${W-R}" y1="${zero}" y2="${zero}" stroke="#56758a" stroke-width="1.15"/>`;
 items.forEach((x,i)=>{
   const cx=L+dx*(i+.5),X=cx-barW/2,v=x.v;
   if(v!==null){const y=yy(v),h=Math.max(1,Math.abs(y-zero));svg+=`<rect x="${X}" y="${Math.min(y,zero)}" width="${barW}" height="${h}" rx="3" fill="${x.estimate?'#debd6d':COLOR[x.ccy]}" ${x.estimate?'opacity=".9"':''}/>`;}
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
 const host=doc.getElementById('ois');if(!host)return;
 // Exactly eight currencies. Uncertified futures are NOT policy deltas.
 const names=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
 const api=window.GMFQ_OIS_RESEARCH_V1;
 let indicative={};
 if(ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
    typeof api?.indicativeSixMonth==='function'){
  try{indicative=api.indicativeSixMonth(ois,romeTodayIso())||{}}
  catch(e){console.warn('[GMFQ 6M indicative WITHHELD]',String(e))}
 }
 let scenarios={};
 if(ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
    typeof api?.scenarioSixMonth==='function'){
  try{scenarios=api.scenarioSixMonth(ois,proxy,romeTodayIso())||{};}
  catch(e){console.warn('[GMFQ Home NZD scenario unavailable]',String(e))}
 }
 const nzReady=proxy?.schema==='GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1'&&
  proxy.status==='LIVE_DIRECTIONAL_PROXY_READY'&&fresh(proxy.as_of,4)&&
  proxy.governance?.substitutes_for_ois_level===false&&
  proxy.governance?.policy_delta_from_proxy_allowed===false&&
  proxy.governance?.pair_engine_effect==='NONE';
 const rows=names.map(k=>{
  const x=ois?.currencies?.[k];
  const official=officialPricingCurrent(x),delta=official?num(x.horizons['6m'].policy_delta_bp):null;
  const p=indicative[k],v=p&&p.is_official_ois===false&&p.policy_delta_allowed===false&&
    p.pair_effect==='NONE'&&num(p.value)!==null&&fresh(p.quote_as_of,4)?p:null;
  const q=k==='NZD'?scenarios.NZD:null;
  const sc=q&&q.currency==='NZD'&&q.type==='SCENARIO'&&
   q.is_official_ois===false&&q.policy_delta_allowed===false&&
   q.pair_effect==='NONE'&&q.core_effect==='NONE'&&
   q.backtest_eligible_as_official===false&&fresh(q.quote_as_of,5)&&
   Array.isArray(q.range)&&q.range.length===2&&
   num(q.value)!==null&&num(q.range[0])!==null&&num(q.range[1])!==null&&
   q.range[0]<q.value&&q.value<q.range[1]?q:null;
  const bill=k==='NZD'&&nzReady?num(proxy.horizons?.['6m']?.implied_bank_bill_rate):null;
  // All G8 lanes show the same financial quantity: 6M level in %.
  // Certified Δ-policy is available separately, never the main displayed unit.
  const level=official?num(x?.horizons?.['6m']?.rate):
    v?num(v.value):sc?num(sc.value):bill;
  return {k,delta,official,indicative:v,scenario:sc,bill,level};
 });
 const max=Math.max(65,...rows.map(x=>Math.abs(x.delta||0)));
 const displayed=rows.filter(x=>num(x.level)!==null).length;
 const certified=rows.filter(x=>x.official&&num(x.level)!==null).length;
 const estimated=displayed-certified;
 host.dataset.gmfqSixMonthDisplayed=String(displayed);
 host.dataset.gmfqSixMonthOfficial=String(certified);
 host.dataset.gmfqSixMonthEstimated=String(estimated);
 host.dataset.gmfqSixMonthUnit='RATE_PCT';
 host.innerHTML=rows.map(x=>{
  const state=x.official?'OFFICIAL_REPRICING':x.indicative?'FUTURES_LEVEL_ONLY':
   x.scenario?'CASH_CARRY_SCENARIO':x.k==='NZD'&&x.bill!==null?'BANK_BILL_PROXY':'WITHHELD';
  const day=x.official?ois.currencies[x.k].as_of:
   x.indicative?x.indicative.quote_as_of:x.scenario?x.scenario.quote_as_of:
   state==='BANK_BILL_PROXY'?proxy.as_of:'—';
  const subtitle=state==='OFFICIAL_REPRICING'?'Δ 6M da fonte certificata':
   state==='FUTURES_LEVEL_ONLY'?'Futures indicativo · solo livello':
   state==='CASH_CARRY_SCENARIO'?'Stima Bank Bill–OCR · fascia '+fmt(x.scenario.range[0],2)+'–'+fmt(x.scenario.range[1],2)+'% · NON ΔOIS':
   state==='BANK_BILL_PROXY'?'Bank Bill · non OIS':'OIS/6M non certificato';
  const readable=state==='OFFICIAL_REPRICING'?
   fmt(x.level,2)+'%':
   state==='FUTURES_LEVEL_ONLY'?'≈'+fmt(x.indicative.value,2)+'% PX':
   state==='CASH_CARRY_SCENARIO'?'≈'+fmt(x.scenario.value,2)+'% ST':
   state==='BANK_BILL_PROXY'?'≈'+fmt(x.bill,2)+'% BB':'NON CERT.';
  const w=x.official?Math.max(2,Math.abs(x.delta)/max*100):0;
  return '<div class="oisrow gmfq-six-month-row'+(x.k==='NZD'?' gmfq-nzd-proxy':'')+'" data-ccy="'+x.k+'" data-pricing-state="'+state+
   '" data-policy-delta-allowed="'+(x.official?'true':'false')+
   '" tabindex="0" role="link" aria-label="Apri '+x.k+' '+htmlEscape(subtitle)+'"'+
   ' title="'+htmlEscape(x.k+' · '+subtitle+' · '+day)+'">'+
   '<span class="gmfq-six-month-name"><i aria-hidden="true">'+FLAG[x.k]+'</i><b>'+x.k+'</b><small>'+BANK[x.k]+'</small></span>'+
   '<div class="track"><div class="fill'+(x.official&&x.delta<0?' alt':'')+
   '" style="width:'+w+'%"></div></div>'+
   '<strong>'+readable+'</strong></div>';
 }).join('')+
 '<div class="oisnote" data-six-month-coverage="'+displayed+'/8"><b>6M · '+displayed+
 '/8 valute</b> · '+certified+' fonti certificate · '+estimated+
 ' stime/proxy. Tutti i valori sono livelli di tasso in %, NON Δ policy in bp. '+
 'PX = futures indicativi (non OIS); ST = scenario NZD Bank Bill corretto per basis (non OIS). PROXY BB ≠ OIS. '+
 'Δ policy e date nel dettaglio; 3M / 6M / 12M nella pagina Tassi. '+
 'Nessuna stima è una quotazione OIS ufficiale o un segnale FX.</div>';
}
function dxyLine(data){
 if(!Array.isArray(data?.history)||data.history.length<3)
   return '<div class="gmfq-chart-note">Storico in fase di costruzione dal fixing BCE.</div>';
 const arr=data.history.slice(-90).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.date)&&num(x.value)!==null);
 if(arr.length<3)return'';
 const W=540,H=174,L=43,R=13,T=11,B=25;
 const lo=Math.min(...arr.map(x=>x.value))-.16,hi=Math.max(...arr.map(x=>x.value))+.16,span=hi-lo||1;
 const xx=i=>L+i/(arr.length-1)*(W-L-R),yy=v=>T+(H-T-B)*(hi-v)/span;
 const points=arr.map((x,i)=>xx(i).toFixed(1)+','+yy(x.value).toFixed(1)).join(' ');
 const last=arr.at(-1),xLast=xx(arr.length-1).toFixed(1),yLast=yy(last.value).toFixed(1);
 const area=L+','+(H-B)+' '+points+' '+xLast+','+(H-B);
 const grid=[hi,(hi+lo)/2,lo].map(v=>{
   const y=yy(v).toFixed(1);
   return '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+
    '" stroke="#315166" stroke-width=".8" opacity=".7"/><text x="'+(L-8)+
    '" y="'+(+y+3)+'" text-anchor="end" fill="#9db7c8" font-size="10">'+
    v.toFixed(2)+'</text>';
 }).join('');
 return '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img" aria-label="DXY sintetico, storico BCE: valori ricostruiti dal fixing giornaliero, non ICE intraday">'+
 '<defs><linearGradient id="gmfq-dxy-fill" x1="0" x2="0" y1="0" y2="1">'+
 '<stop offset="0%" stop-color="#dabd76" stop-opacity=".22"/>'+
 '<stop offset="100%" stop-color="#dabd76" stop-opacity="0"/></linearGradient></defs>'+
 grid+'<polygon points="'+area+'" fill="url(#gmfq-dxy-fill)"/>'+
 '<polyline points="'+points+'" fill="none" stroke="#e7c675" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>'+
 '<circle cx="'+xLast+'" cy="'+yLast+'" r="4" fill="#e7c675" stroke="#091b2b" stroke-width="2"/>'+
 '<text x="'+L+'" y="'+(H-4)+'" fill="#98b0c3" font-size="10">'+htmlEscape(arr[0].date)+'</text>'+
 '<text x="'+(W-R)+'" y="'+(H-4)+'" text-anchor="end" fill="#98b0c3" font-size="10">'+htmlEscape(last.date)+'</text></svg>';
}
function validDxy(x){return x?.schema==='GMFQ_DXY_SYNTHETIC_ECB_V1'&&x.status==='ESTIMATED_INFORMATIONAL'&&x.not_official_ice===true&&x.usable_as_official_ice_or_trade_signal===false&&fresh(x.as_of,4)&&num(x.value)!==null&&Array.isArray(x.history)&&x.history.at(-1)?.date===x.as_of}
function dxyResearchContext(data){
 // Only draw derivative returns when all input fixing observations reconcile.
 // This never creates an ICE DXY quote, a trade signal, or a backtest series.
 if(!validDxy(data)||data.history.length<6)return null;
 const h=data.history,tail=h.slice(-20);
 if(tail.length<6||tail.some((x,i)=>!x||!/^\d{4}-\d{2}-\d{2}$/.test(x.date)||
    num(x.value)===null||x.value<=0||(i>0&&x.date<=tail[i-1].date)))return null;
 const latest=tail.at(-1),prior=tail.at(-2),base5=tail.at(-6);
 if(Math.abs(latest.value-data.value)>0.00011||
    num(data.previous_value)===null||
    Math.abs(prior.value-data.previous_value)>0.00011)return null;
 const vals=tail.map(x=>x.value);
 return {oneSessionPct:100*(latest.value/prior.value-1),
   fiveSessionPct:100*(latest.value/base5.value-1),
   low:Math.min(...vals),high:Math.max(...vals),
   count:tail.length,firstDate:tail[0].date,asOf:latest.date,
   officialIce:false,signalsAllowed:false};
}
function dxyContextHtml(data){
 const x=dxyResearchContext(data);
 if(!x)return '<p class="gmfq-dxy-context-limit">Confronti temporali non verificabili con il fixing disponibile.</p>';
 const pct=v=>(v>0?'+':'')+fmt(v,2)+'%';
 return '<div class="gmfq-dxy-metrics" data-research-only="true" data-ice-official="false" aria-label="Variazioni e intervallo del DXY sintetico">'+
 '<div><small>Ultima seduta</small><strong>'+pct(x.oneSessionPct)+'</strong></div>'+
 '<div><small>5 sedute</small><strong>'+pct(x.fiveSessionPct)+'</strong></div>'+
 '<div><small>Intervallo '+x.count+' sedute</small><strong>'+fmt(x.low,2)+' – '+fmt(x.high,2)+'</strong></div>'+
 '</div><p class="gmfq-dxy-context-limit">Variazioni calcolate sulla serie sintetica BCE, non sull’indice ICE né su prezzi intraday. Ultimo fixing '+htmlEscape(x.asOf)+'.</p>';
}
function mountHomeCurrencyFlags(doc){
 const tiles=[...doc.querySelectorAll('#valute .cc[data-filter]')];
 for(const tile of tiles){
  const c=tile.dataset.filter,flag=c==='DXY'?'🇺🇸':FLAG[c];
  if(!flag)continue;
  const head=tile.querySelector('.tickerhead');if(!head)continue;
  let node=head.querySelector('.flag');
  if(!node){node=doc.createElement('span');node.className='flag';head.insertBefore(node,head.firstChild)}
  node.textContent=flag;
  node.setAttribute('aria-label',c==='DXY'?'Indice dollaro sintetico':c);
  node.dataset.gmfqFlag=c;
  node.style.cssText='font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;font-size:21px;line-height:1.1;display:inline-flex;align-items:center;justify-content:center;min-width:25px;opacity:1;filter:none';
  if(c==='DXY'&&!tile.querySelector('.gmfq-home-dxy-origin')){
   const label=doc.createElement('small');
   label.className='gmfq-home-dxy-origin';
   label.textContent='INDICE SINTETICO · BCE';
   label.title='DXY ricostruito da fixing BCE; non è l’indice ICE ufficiale';
   tile.appendChild(label);
  }
 }
}
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
 <p class="gmfq-source">INPUT: FIXING BCE · INDICE: STIMA SINTETICA · ${ok?htmlEscape(dxyFeed.as_of):'NON DISPONIBILE'} · non ICE</p>
 ${ok?dxyContextHtml(dxyFeed):''}
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
/* One source contract for Home, Valute, Macro and Pair Deep Dive.
   Only source labels and read-only decisions; never alters source payloads. */
function canonicalMacroBaselineAsOf(model){
 const d=model?.asOf;
 if(!d||macroSeriesPeriod(d)!==d||
    !Array.isArray(model.currencies)||model.currencies.length!==8||
    !FX.every(c=>model.currencies.includes(c)&&
      ['growth','labour','inflation'].every(k=>num(model.macro?.[c]?.[k])!==null)))
   return null;
 return d;
}
function canonicalPairMacroBaseline(setup,model){
 const d=canonicalMacroBaselineAsOf(model);
 return setup?.schema==='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'&&
  setup?.pair_count===28&&setup?.status==='CURRENT_CANONICAL_ENGINE'&&
  d!==null&&setup.macro_baseline_asof===d?d:null;
}

/* Home research order — one compact editorial rail, never a new scorecard.
   Reuses the SAME certified-source decisions used by the Home source audit. */
function mountHomeReadingPath(doc,context){
 if(!home()||frame.contentDocument!==doc||
    doc.documentElement.dataset.marketMode!=='live'||doc.getElementById('gmfq-home-reading-path'))return;
 const hero=doc.querySelector('.hero'),grid=doc.querySelector('.gridtop');
 if(!hero||!grid||!hero.contains(doc.querySelector('.herobody')))return;
 const {macroDay,fxCurrent,fxDay,oisCount,setup}=context;
 const pairCounts=setup?.quality_distribution,rows=setup?.pairs;
 const validSetup=setup?.schema==='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'&&
   setup.status==='CURRENT_CANONICAL_ENGINE'&&setup.pair_count===28&&
   Object.keys(rows||{}).length===28&&setup.price_audit?.status==='PASS'&&
   setup.price_audit.as_of===setup.price_asof&&
   setup.thesis_is_not_entry===true&&setup.entry_level_published===false&&
   typeof pairCounts?.['NON VALUTABILE']==='number'&&
   Number.isInteger(pairCounts['NON VALUTABILE'])&&pairCounts['NON VALUTABILE']>=0&&
   pairCounts['NON VALUTABILE']<=28&&
   Object.values(rows||{}).filter(x=>x?.setup?.quality==='NON VALUTABILE').length===
     pairCounts['NON VALUTABILE']&&
   Object.values(pairCounts).every(x=>Number.isInteger(x)&&x>=0)&&
   Object.values(pairCounts).reduce((a,b)=>a+b,0)===28&&
   fresh(setup.price_asof,5);
 const macroVerified=typeof macroDay==='string'&&macroSeriesPeriod(macroDay)===macroDay;
 const macroCurrent=macroVerified&&fresh(macroDay,10);
 // Editorial research-navigation priority, never a trade ranking or model score.
 // Use exactly the validated/fail-closed source states shown by the Home audit.
 const sourceCountVerified=Number.isInteger(oisCount)&&oisCount>=0&&oisCount<=8;
 const priority=!macroVerified?
  {key:'macro',state:'WITHHELD',
   text:'Prima verifica la baseline Macro: lo snapshot non è riconciliato con il modello delle coppie.'}:
  !macroCurrent?
  {key:'macro',state:'HISTORICAL',
   text:'Prima rivalida la tesi Macro: la baseline del '+macroDay+' è storica. I setup non sono segnali correnti.'}:
  !sourceCountVerified?
  {key:'pricing',state:'WITHHELD',
   text:'Prima verifica il Market Pricing: la copertura delle fonti non è certificabile.'}:
  oisCount<8?
  {key:'pricing',state:'PARTIAL',
   text:'Prima confronta il Market Pricing: '+oisCount+'/8 valute con fonti certificate. La copertura incompleta limita le conclusioni.'}:
  !validSetup?
  {key:'pairs',state:'WITHHELD',
   text:'Prima verifica lo Screener: i giudizi sulle 28 coppie non sono riconciliati.'}:
  {key:'pairs',state:'RESEARCH_ONLY',
   text:'Passa allo Screener: '+pairCounts['NON VALUTABILE']+'/28 coppie senza tesi robusta. Poi approfondisci le altre, senza dedurre ingressi.'};
 const steps=[
  {key:'macro',url:'#/macro',description:!macroVerified?'Macro · baseline non verificabile':
   'Macro · '+macroDay+(macroCurrent?' · snapshot':' · da rivalidare')},
  {key:'pricing',url:'#/tassi?focus=ois',description:Number.isInteger(oisCount)&&oisCount>=0&&oisCount<=8?
   'Pricing · '+oisCount+'/8 fonti certificate':'Pricing · copertura non verificabile'},
  {key:'pairs',url:'#/screener',description:validSetup?
   'Screener · '+pairCounts['NON VALUTABILE']+'/28 non valutabili':
   'Screener · giudizi non verificabili'}
 ];
 const style=doc.createElement('style');style.id='gmfq-home-reading-path-style';
 style.textContent='#gmfq-home-reading-path{display:flex;flex-direction:column;align-items:flex-start;gap:4px;min-width:0;margin:8px 0 14px;padding:10px 11px;border-top:1px solid #2d4659;border-bottom:1px solid #294253;color:#a8bccb;font:11px/1.45 Arial,sans-serif}'+
 '#gmfq-home-reading-path .gmfq-reading-priority{margin:0 0 3px;font:600 13px/1.55 Arial,sans-serif;color:#e3edf4;overflow-wrap:anywhere}'+
 '#gmfq-home-reading-path[data-priority-state="HISTORICAL"] .gmfq-reading-priority,#gmfq-home-reading-path[data-priority-state="WITHHELD"] .gmfq-reading-priority{color:#e2c98d}'+
 '#gmfq-home-reading-path .gmfq-reading-heading{font:600 10px/1.45 Arial,sans-serif;letter-spacing:.07em;color:#d2bd87;white-space:nowrap}'+
 '#gmfq-home-reading-path .gmfq-reading-steps{display:flex;align-items:center;gap:5px 12px;flex-wrap:wrap;min-width:0}'+
 '#gmfq-home-reading-path button{border:0;border-bottom:1px solid transparent;background:transparent;padding:3px 0;color:#c2d2df;font:11px/1.5 Arial,sans-serif;cursor:pointer;text-align:left;max-width:100%;overflow-wrap:anywhere}'+
 '#gmfq-home-reading-path button[data-reading-priority="true"]{color:#efd99e;border-color:#88764f;font-weight:600}'+
 '#gmfq-home-reading-path button:hover,#gmfq-home-reading-path button:focus-visible{color:#f1dcac;border-color:#e2c98c;outline-offset:3px}'+
 '#gmfq-home-reading-path .gmfq-reading-arrow{color:#718da1;font:11px Arial,sans-serif}'+
 '#gmfq-home-reading-path .gmfq-reading-trust{color:#8da5b5;font-size:10px;white-space:normal}'+
 '@media(max-width:600px){#gmfq-home-reading-path{margin:8px 0 12px;padding:9px 8px}'+
 '#gmfq-home-reading-path .gmfq-reading-priority{font-size:12px;line-height:1.55}'+
 '#gmfq-home-reading-path .gmfq-reading-steps{gap:5px 9px}'+
 '#gmfq-home-reading-path button{font-size:10px}#gmfq-home-reading-path .gmfq-reading-trust{flex-basis:100%}}';
 doc.head.appendChild(style);
 // Genuine first-screen composition: the original 32-part artwork and Home
 // data remain untouched. Only the live Home layout changes, responsively.
 const visual=doc.createElement('style');visual.id='gmfq-home-visual-edition-css';
 visual.textContent=
  '#gmfq-home-reading-path{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(285px,.85fr);gap:18px;align-items:center;min-width:0;margin:11px 0 15px;padding:16px 19px;border:1px solid #344f62;border-left:3px solid #d7b76e;border-radius:7px;background:linear-gradient(110deg,#0d293b 0%,#091a29 82%);box-sizing:border-box}'+
  '#gmfq-home-reading-path .gmfq-reading-main,#gmfq-home-reading-path .gmfq-reading-side{min-width:0}'+
  '#valute .cc .tickerhead .flag{display:inline-flex!important;align-items:center;justify-content:center;min-width:25px;opacity:1!important}'+
  '#valute .cc .gmfq-home-dxy-origin{display:block;font:600 9px/1.3 Arial,sans-serif;letter-spacing:.04em;color:#d4bd86;margin:2px 0 0;white-space:normal}'+
  '#gmfq-home-reading-path .gmfq-reading-heading{display:block;font:600 10px/1.55 Arial,sans-serif;letter-spacing:.09em;color:#d9c48b;margin-bottom:7px}'+
  '#gmfq-home-reading-path .gmfq-reading-priority{font:600 17px/1.48 Arial,sans-serif;color:#f0f3f7;max-width:670px;margin:0 0 9px;overflow-wrap:anywhere}'+
  '#gmfq-home-reading-path .gmfq-reading-trust{display:block;font:11px/1.5 Arial,sans-serif;color:#9eb8c9}'+
  '#gmfq-home-reading-path .gmfq-reading-side{padding-left:17px;border-left:1px solid #355163}'+
  '#gmfq-home-reading-path .gmfq-reading-side-title{font:600 10px/1.5 Arial,sans-serif;letter-spacing:.08em;color:#8caaba}'+
  '#gmfq-home-reading-path .gmfq-reading-steps{display:grid;grid-template-columns:1fr;gap:0;margin-top:5px;counter-reset:gmfq-steps}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button{counter-increment:gmfq-steps;display:block;width:100%;padding:7px 2px;border-bottom:1px solid #304c5d;text-align:left;font:12px/1.4 Arial,sans-serif;color:#d3e0e9}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button:last-child{border-bottom:0}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button:before{content:"0" counter(gmfq-steps);display:inline-block;min-width:29px;color:#799aaf;font:600 10px/1.4 Arial,sans-serif}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button[data-reading-priority="true"]{color:#f0d48b;font-weight:600}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button:focus-visible{outline:2px solid #e4c77f;outline-offset:2px}'+
  '.gridtop{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:minmax(285px,auto) minmax(270px,auto);height:auto;gap:12px;margin-bottom:14px}'+
  '.gridtop>.hero{grid-column:1/-1;grid-row:1;min-height:285px;height:auto;padding:25px 30px}'+
  '.gridtop>.hero .globe{width:62%;background-size:auto 100%;background-position:right center;opacity:1}'+
  '.gridtop>.hero .herobody{max-width:630px}'+
  '.gridtop>.hero h1{font-size:32px;line-height:1.17;max-width:650px}'+
  '.gridtop>.panel:not(.hero){grid-row:2;min-width:0;min-height:270px;height:auto}'+
  '.gridtop>.panel:nth-child(2){grid-column:1}'+
  '.gridtop>.yieldpanel{grid-column:2;display:block}'+
  '.gridtop>.panel:not(.hero) .heading{font:600 16px/1.25 Arial,sans-serif;min-height:42px;height:auto;padding:11px 15px;white-space:normal}'+
  '.gridtop .prob{padding:0 15px 10px}'+
  '.gridtop .oisrow{grid-template-columns:minmax(75px,110px) minmax(0,1fr) 67px;gap:9px;margin:5px 0;font-size:12px}'+
  '.gridtop .oisrow:first-child{margin-top:6px}'+
  '.gridtop .oisrow .track{height:13px}'+
  '.gridtop .oisrow strong{font-size:12px}'+
  '.gridtop .yieldplot{height:167px}'+
  '@media(max-width:850px){#gmfq-home-reading-path{grid-template-columns:1fr;gap:13px;padding:14px 15px}'+
  '#gmfq-home-reading-path .gmfq-reading-side{padding:10px 0 0;border-left:0;border-top:1px solid #355163}'+
  '#gmfq-home-reading-path .gmfq-reading-steps{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button{padding:6px 0}'+
  '.gridtop>.hero{padding:20px 22px}.gridtop>.hero h1{font-size:28px}}'+
  '@media(max-width:600px){#gmfq-home-reading-path{padding:13px 12px;gap:10px;margin:10px 0 13px}'+
  '#gmfq-home-reading-path .gmfq-reading-priority{font-size:15px;line-height:1.48}'+
  '#gmfq-home-reading-path .gmfq-reading-steps{grid-template-columns:1fr;gap:0}'+
  '#gmfq-home-reading-path .gmfq-reading-steps button{font-size:11px;padding:6px 1px}'+
  '.gridtop{grid-template-columns:1fr;grid-template-rows:none;gap:11px;margin-bottom:13px}'+
  '.gridtop>.hero{grid-column:1;grid-row:auto;min-height:315px;height:auto;padding:18px 16px}'+
  '.gridtop>.hero .globe{width:90%;background-size:auto 100%;opacity:.64}'+
  '.gridtop>.hero .herobody{max-width:100%}'+
  '.gridtop>.hero h1{font-size:23px;line-height:1.2}'+
  '.gridtop>.panel:not(.hero){grid-column:1;grid-row:auto;min-height:265px}'+
  '.gridtop>.panel:not(.hero) .heading{font-size:15px;padding:11px 13px}'+
  '.gridtop .prob{padding:0 12px 10px}'+
  '.gridtop .oisrow{grid-template-columns:minmax(68px,92px) minmax(0,1fr) 62px;gap:7px;font-size:11px}'+
  '.gridtop .yieldplot{height:175px}}';
 // The second half of Home is also visually composed, not just annotated:
 // bigger analytical charts; full-width pair table, then the full messages feed.
 visual.textContent+=
  '.gmfq-home-chapter{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:5px 16px;padding:8px 2px 10px;margin:0;min-width:0}'+
  '.gmfq-home-chapter h2{font:600 17px/1.35 Arial,sans-serif;color:#e8f1f6;margin:0}'+
  '.gmfq-home-chapter .gmfq-home-chapter-number{color:#d8c08b;font:600 11px/1.4 Arial,sans-serif;margin-right:10px}'+
  '.gmfq-home-chapter p{margin:0;color:#9fb7c7;font:11px/1.55 Arial,sans-serif;overflow-wrap:anywhere}'+
  '.mid{height:auto;grid-template-columns:minmax(0,.96fr) minmax(0,1.36fr) minmax(0,1.06fr);gap:12px;margin-bottom:13px}'+
  '.mid>.panel{height:auto;min-height:286px;min-width:0}'+
  '.mid>.panel:nth-child(2){border-color:#476173;background:linear-gradient(145deg,#0b2536,#071825)}'+
  '.mid>.panel:nth-child(2) .heading{color:#f0d79c}'+
  '.mid .heading{font:600 15px/1.3 Arial,sans-serif;padding:11px 14px;min-height:45px;height:auto}'+
  '.mid .chartbody{height:211px;padding:8px 10px 13px;box-sizing:content-box}'+
  '.mid .chartbody svg{width:100%;height:100%;display:block}'+
  '.bottom{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;min-height:0;margin-bottom:13px}'+
  '.bottom>.panel{min-width:0}'+
  '.bottom>.panel:first-child .heading{min-height:45px;height:auto;padding:11px 15px;font:600 16px/1.35 Arial,sans-serif;gap:10px}'+
  '.bottom>.panel:last-child .heading{min-height:43px;height:auto;padding:10px 15px;font:600 15px/1.35 Arial,sans-serif}'+
  '.bottom .messagebox{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px;padding:4px 16px 11px}'+
  '.bottom .msg{min-width:0;line-height:1.45;min-height:56px;padding:11px 0}'+
  '@media(max-width:900px){.mid{grid-template-columns:repeat(2,minmax(0,1fr))}'+
  '.mid>.panel:last-child{grid-column:1/-1}'+
  '.gmfq-home-chapter{display:block}.gmfq-home-chapter p{margin-top:4px}}'+
  '@media(max-width:600px){.gmfq-home-chapter{padding:6px 2px 9px}'+
  '.gmfq-home-chapter h2{font-size:15px}'+
  '.gmfq-home-chapter p{font-size:10px}'+
  '.mid{grid-template-columns:1fr;gap:11px;margin-bottom:13px}'+
  '.mid>.panel,.mid>.panel:last-child{grid-column:1;min-height:275px;height:auto}'+
  '.mid .heading{min-height:43px;font-size:15px;padding:10px 12px}'+
  '.mid .chartbody{height:205px;padding:7px 9px 11px}'+
  '.bottom{grid-template-columns:1fr;gap:11px}'+
  '.bottom .messagebox{grid-template-columns:1fr;padding:3px 13px 10px}'+
  '.bottom .msg{min-height:51px;padding:9px 0}'+
  '.bottom>.panel:first-child .heading,.bottom>.panel:last-child .heading{padding:10px 12px;font-size:14px}}';
 // Source-safe G8 card and premium chart polish. Values and datasets untouched.
 visual.textContent+=
  '.gridtop>.panel:nth-child(2){min-height:322px}'+
  '.gridtop #ois{padding:4px 14px 10px}'+
  '.gridtop #ois .gmfq-six-month-row{height:auto;min-height:29px;margin:0;display:grid;grid-template-columns:115px minmax(0,1fr) 100px;gap:9px;align-items:center;border-top:1px solid #1b3547;font:11px/1.4 Arial,sans-serif}'+
  '.gridtop #ois .gmfq-six-month-row:first-child{border-top:0}'+
  '.gridtop #ois .gmfq-six-month-name{display:flex;gap:6px;align-items:center;min-width:0;white-space:nowrap}'+
  '.gridtop #ois .gmfq-six-month-name i{font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;font-style:normal;font-size:16px;flex-shrink:0}'+
  '.gridtop #ois .gmfq-six-month-name b{font:700 11px/1.4 Arial,sans-serif;color:#e8f0f6}'+
  '.gridtop #ois .gmfq-six-month-name small{font:10px/1.4 Arial,sans-serif;color:#8faec1}'+
  '.gridtop #ois .gmfq-six-month-row strong{text-align:right;font:600 11px/1.4 Arial,sans-serif;white-space:nowrap;color:#e6eff7}'+
  '.gridtop #ois .gmfq-six-month-row[data-pricing-state="FUTURES_LEVEL_ONLY"] strong{color:#e4c58a}'+
  '.gridtop #ois .gmfq-six-month-row[data-pricing-state="BANK_BILL_PROXY"] strong{color:#d6c28e}'+
  '.gridtop #ois .gmfq-six-month-row[data-pricing-state="WITHHELD"] strong{color:#b39bab}'+
  '.gridtop #ois .gmfq-six-month-row[data-pricing-state="FUTURES_LEVEL_ONLY"] .track,'+
    '.gridtop #ois .gmfq-six-month-row[data-pricing-state="BANK_BILL_PROXY"] .track,'+
    '.gridtop #ois .gmfq-six-month-row[data-pricing-state="WITHHELD"] .track{background:repeating-linear-gradient(90deg,#253f51 0px,#253f51 3px,#102637 3px,#102637 8px);opacity:.75}'+
  '.gridtop #ois .gmfq-six-month-row .track{height:10px;border-radius:5px;overflow:hidden}'+
  '.gridtop #ois .gmfq-six-month-row .fill{height:100%;border-radius:5px}'+
  '.gridtop #ois .oisnote{font:10px/1.4 Arial,sans-serif;color:#9eb5c6;margin-top:10px}'+
  '.gridtop .yieldplot svg,.mid .chartbody svg{border-radius:6px;overflow:visible}'+
  '.gridtop .yieldplot,.mid .chartbody{background:linear-gradient(160deg,#0b2231 0%,#071923 100%)}'+
  '.mid .chartbody svg rect{transition:opacity .15s ease}'+
  '.mid .chartbody svg rect:hover{opacity:.8}'+
  '.mid .chartbody svg text{paint-order:stroke fill;stroke:#061a27;stroke-width:.45px}'+
  '@media(max-width:600px){.gridtop>.panel:nth-child(2){min-height:330px}'+
  '.gridtop #ois{padding:3px 10px 10px}'+
  '.gridtop #ois .gmfq-six-month-row{grid-template-columns:102px minmax(0,1fr) 90px;gap:5px;min-height:30px}'+
  '.gridtop #ois .gmfq-six-month-name i{font-size:15px}'+
  '.gridtop #ois .gmfq-six-month-name small{font-size:9px}'+
  '.gridtop #ois .gmfq-six-month-row strong{font-size:10px}'+
  '.gridtop #ois .oisnote{font-size:9px}}';
 doc.head.appendChild(visual);
 const rail=doc.createElement('nav');
 rail.id='gmfq-home-reading-path';rail.setAttribute('aria-label','Da dove iniziare la lettura Macro FX');
 rail.dataset.visualEdition='home-composition-v1';
 rail.dataset.macroAsOf=macroVerified?macroDay:'';
 rail.dataset.macroStatus=macroVerified?(macroCurrent?'DATED_SNAPSHOT':'HISTORICAL'):'WITHHELD';
 rail.dataset.oisCertified=Number.isInteger(oisCount)?String(oisCount):'';
 rail.dataset.screenerCount=validSetup?String(pairCounts['NON VALUTABILE']):'';
 rail.dataset.fxAsOf=fxCurrent?fxDay:'';
 rail.dataset.sourceEffect='NONE';
 rail.dataset.priorityTarget=priority.key;
 rail.dataset.priorityState=priority.state;
 rail.innerHTML='<div class="gmfq-reading-main"><span class="gmfq-reading-heading">PRIORITÀ DEL RESEARCH DESK</span>'+
  '<p class="gmfq-reading-priority" aria-label="Prima verifica da effettuare">'+htmlEscape(priority.text)+'</p>'+
  '<span class="gmfq-reading-trust">Ricerca, non segnali: '+(fxCurrent?'fixing BCE '+htmlEscape(fxDay):'fixing BCE non verificato')+'</span></div>'+
  '<div class="gmfq-reading-side"><span class="gmfq-reading-side-title">PERCORSO DI VERIFICA</span>'+
  '<div class="gmfq-reading-steps">'+steps.map(x=>
   '<button type="button" data-reading-target="'+x.key+'" data-reading-priority="'+(x.key===priority.key?'true':'false')+'" aria-label="Apri '+htmlEscape(x.description)+'">'+
    htmlEscape(x.description)+'</button>').join('')+'</div></div>';
 // The native globe HERO is the first child of .gridtop. Keep the 3-column
 // original grid intact: position the editorial path BEFORE that entire grid.
 grid.insertAdjacentElement('beforebegin',rail);
 const mid=doc.querySelector('.mid'),bottom=doc.querySelector('.bottom');
 if(mid&&bottom&&mid.parentElement===bottom.parentElement){
  const chapter=(id,number,title,note)=>{
   const section=doc.createElement('header');section.id=id;section.className='gmfq-home-chapter';
   section.innerHTML='<h2><span class="gmfq-home-chapter-number">'+number+'</span>'+title+'</h2>'+
    '<p>'+note+'</p>';
   return section;
  };
  mid.insertAdjacentElement('beforebegin',chapter('gmfq-home-market-chapter','01','Mercati · come si muovono i fattori',
   'Forza FX, tassi 2Y e spread: misure diverse. Le stime restano contrassegnate.'));
  bottom.insertAdjacentElement('beforebegin',chapter('gmfq-home-pair-chapter','02','Coppie FX · dalla tesi alla verifica',
   'Tesi e condizioni del modello: contesto per approfondire, non segnali di ingresso.'));
 }
 rail.addEventListener('click',event=>{
  const button=event.target.closest('button[data-reading-target]');
  if(!button||!rail.contains(button))return;
  const target=steps.find(x=>x.key===button.dataset.readingTarget);
  if(target)go(target.url);
 });
}

/* Market Pulse is a dated MARKET PRICING recap, not a live headline feed.
   Only known instrument/source combinations may be classified. Fail closed
   on unknown rows; never promote repricing to an FX trade signal. */
function marketPulseReadings(feedData){
 const instrument={
  GBP:{pattern:/^Bank of England · estimated sterling OIS yield curves · daily OIS archive$/,label:'OIS BoE · curva stimata',kind:'OIS'},
  CAD:{pattern:/^Montréal Exchange public Market Review · Three-Month CORRA Futures \(CRA\)$/,label:'Futures CORRA',kind:'FUTURES'},
  JPY:{pattern:/^Tokyo Financial Exchange · Three-month TONA Futures$/,label:'Futures TONA',kind:'FUTURES'},
  AUD:{pattern:/^ASX Futures End of Day Data · 30 Day Interbank Cash Rate futures \(IB\)$/,label:'Futures cash rate',kind:'FUTURES'}
 };
 if(feedData?.schema!=='GMFQ_NEWS_PULSE_OPERATIONAL_V1'||
    feedData.status!=='ACTIVE_DETERMINISTIC_LAYERS'||
    feedData.scope?.claim!=='LATEST_VALIDATED_SIGNALS_NOT_GENERIC_HEADLINES'||
    !Array.isArray(feedData.items)||!fresh(feedData.content_as_of,2)||
    !Number.isFinite(Date.parse(feedData.generated_at_utc))||
    Date.parse(feedData.generated_at_utc)>Date.now()+3600000||
    !fresh(feedData.generated_at_utc.slice(0,10),2))return [];
 const used=new Set,rows=[];
 for(const x of feedData.items){
   if(!x||!instrument[x.ccy]||used.has(x.ccy)||x.category!=='OIS_REPRICING'||
      x.quality!=='OFFICIAL_CERTIFIED'||x.confidence!=='A'||
      !['HIGH','MEDIUM'].includes(x.importance)||
      x.as_of!==feedData.content_as_of||!fresh(x.as_of,2)||
      typeof x.title!=='string'||x.title.length>190||
      typeof x.detail!=='string'||x.detail.length>350||
      typeof x.source!=='string'||x.source.length>230||
      !instrument[x.ccy].pattern.test(x.source))continue;
   const m=/^Movimento 1D ([+-]\d+(?:\.\d+)?) bp sul bucket (3M|6M|12M); variazione 1W ([+-]\d+(?:\.\d+)?) bp\.$/.exec(x.detail);
   if(!m)continue;
   const one=Number(m[1]),week=Number(m[3]);
   if(!Number.isFinite(one)||!Number.isFinite(week)||Math.abs(one)>100||Math.abs(week)>200)continue;
   used.add(x.ccy);
   rows.push({ccy:x.ccy,asOf:x.as_of,one,week,horizon:m[2],
      instrument:instrument[x.ccy].label,kind:instrument[x.ccy].kind,
      source:x.source,detail:x.detail});
 }
 return rows.slice(0,4);
}
async function mountHomeMarketPulse(doc){
 if(!home()||frame.contentDocument!==doc||doc.documentElement.dataset.marketMode!=='live'||
   doc.getElementById('gmfq-market-pulse'))return;
 const grid=doc.querySelector('.gridtop');if(!grid)return;
 const style=doc.createElement('style');style.id='gmfq-market-pulse-style';
 style.textContent=
 '#gmfq-market-pulse{background:linear-gradient(135deg,#0b2030,#081a27);border:1px solid #2c4659;border-radius:7px;margin:0 0 14px;padding:15px 17px;color:#e4edf3;font-family:Arial,sans-serif;min-width:0}'+
 '#gmfq-market-pulse .gmfq-pulse-head{display:flex;gap:9px 16px;justify-content:space-between;align-items:baseline;flex-wrap:wrap;border-bottom:1px solid #2a4354;padding-bottom:9px}'+
 '#gmfq-market-pulse h2{font:600 16px/1.4 Arial,sans-serif;margin:0;color:#f0f4f8}'+
 '#gmfq-market-pulse .gmfq-pulse-date{font:600 11px/1.5 Arial,sans-serif;color:#dfc689}'+
 '#gmfq-market-pulse .gmfq-pulse-caption{font:11px/1.6 Arial,sans-serif;color:#a4bdcc;margin:9px 0 3px}'+
 '#gmfq-market-pulse .gmfq-pulse-lead{font:600 12px/1.55 Arial,sans-serif;color:#e5eef5;margin:10px 0 4px}'+
 '#gmfq-market-pulse .gmfq-pulse-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 22px}'+
 '#gmfq-market-pulse .gmfq-pulse-item{padding:12px 2px;border-bottom:1px solid #264153;min-width:0}'+
 '#gmfq-market-pulse .gmfq-pulse-item strong{font:600 13px/1.4 Arial,sans-serif;color:#e8eef5;overflow-wrap:anywhere}'+
 '#gmfq-market-pulse .gmfq-pulse-instrument{display:block;font:10px/1.5 Arial,sans-serif;color:#a2b9c9;margin-top:2px}'+
 '#gmfq-market-pulse .gmfq-pulse-metrics{display:flex;gap:9px 16px;flex-wrap:wrap;margin:8px 0 2px;align-items:baseline}'+
 '#gmfq-market-pulse .gmfq-pulse-metrics span{font:10px/1.5 Arial,sans-serif;color:#9db4c5}'+
 '#gmfq-market-pulse .gmfq-pulse-metrics b{font:600 17px/1.25 Arial,sans-serif;color:#e5edf3;font-variant-numeric:tabular-nums;margin-left:3px}'+
 '#gmfq-market-pulse .gmfq-pulse-metrics b[data-direction="UP"]{color:#80d7ad}'+
 '#gmfq-market-pulse .gmfq-pulse-metrics b[data-direction="DOWN"]{color:#c6a3e8}'+
 '#gmfq-market-pulse .gmfq-pulse-caution{display:block;font:10px/1.45 Arial,sans-serif;color:#b8c8d4;margin-top:5px}'+
 '#gmfq-market-pulse .gmfq-pulse-item details{margin-top:8px}'+
 '#gmfq-market-pulse .gmfq-pulse-item summary{cursor:pointer;color:#dac48d;font:600 10px/1.5 Arial,sans-serif;outline-offset:3px}'+
 '#gmfq-market-pulse .gmfq-pulse-item details p{font:10px/1.55 Arial,sans-serif;color:#a9bdcc;margin:5px 0;overflow-wrap:anywhere}'+
 '#gmfq-market-pulse .gmfq-pulse-links{border-top:1px solid #264153;margin-top:12px;padding-top:9px;display:flex;gap:8px 18px;align-items:baseline;flex-wrap:wrap;font:600 11px/1.5 Arial,sans-serif}'+
 '#gmfq-market-pulse .gmfq-pulse-links>span{font-weight:400;color:#a5bac8}'+
 '#gmfq-market-pulse a{color:#e2c784;text-decoration:underline;text-underline-offset:3px}'+
 '#gmfq-market-pulse a:focus-visible,#gmfq-market-pulse summary:focus-visible{outline:2px solid #e9cc88;outline-offset:3px}'+
 '@media(max-width:600px){#gmfq-market-pulse{padding:12px 13px}#gmfq-market-pulse .gmfq-pulse-grid{grid-template-columns:1fr}#gmfq-market-pulse h2{font-size:15px}#gmfq-market-pulse .gmfq-pulse-metrics b{font-size:15px}}';
 doc.head.appendChild(style);
 const host=doc.createElement('section');host.id='gmfq-market-pulse';
 host.dataset.sourceEffect='NONE';host.dataset.pulseStatus='LOADING';
 host.setAttribute('aria-label','Market Pulse: variazioni verificate del pricing monetario, separate dalle notizie esterne');
 host.innerHTML='<div class="gmfq-pulse-head"><h2>Market Pulse · tassi impliciti</h2><span class="gmfq-pulse-date">Verifica fonti in corso</span></div>'+
  '<p class="gmfq-pulse-caption">Movimenti di pricing monetario da fonti verificate, non titoli giornalistici in tempo reale. Non sono segnali FX.</p>'+
  '<p class="gmfq-pulse-lead"></p><div class="gmfq-pulse-grid"></div>'+
  '<div class="gmfq-pulse-links"><span>Notizie esterne, separate dai dati:</span>'+
  '<a href="https://www.reuters.com/markets/" target="_blank" rel="noopener noreferrer">Mercati · Reuters ↗</a>'+
  '<a href="https://www.ecb.europa.eu/press/html/index.en.html" target="_blank" rel="noopener noreferrer">Comunicati BCE ↗</a></div>';
 grid.insertAdjacentElement('afterend',host);
 const date=host.querySelector('.gmfq-pulse-date'),box=host.querySelector('.gmfq-pulse-grid'),
   lead=host.querySelector('.gmfq-pulse-lead');
 try{
  const data=await feed('NEWS_PULSE_OPERATIONAL.json');
  if(!host.isConnected||frame.contentDocument!==doc)return;
  const rows=marketPulseReadings(data);
  host.dataset.pulseStatus=rows.length?'RECENT_VALIDATED':'LOADING_REFERENCE';
  host.dataset.asOf=rows.length?data.content_as_of:'';
  date.textContent=rows.length?'Rilevazione '+data.content_as_of+' · non intraday':'Nessuna rilevazione recente verificata';
  const bp=v=>(v>0?'+':'')+fmt(v,1)+' bp';
  const largest=rows.reduce((v,x)=>!v||Math.abs(x.one)>Math.abs(v.one)?x:v,null);
  lead.textContent=largest?('Variazione 1D più ampia tra le '+rows.length+
    ' fonti disponibili: '+largest.ccy+' '+bp(largest.one)+' ('+largest.horizon+').'):'';
  box.innerHTML=rows.length?rows.map(x=>{
    const dir=v=>v>0?'UP':v<0?'DOWN':'FLAT';
    const opposite=x.one*x.week<0;
    return '<article class="gmfq-pulse-item" data-pulse-ccy="'+x.ccy+'" data-instrument-type="'+x.kind+'" data-research-only="true">'+
     '<strong>'+FLAG[x.ccy]+' '+x.ccy+' · '+htmlEscape(x.horizon)+'</strong>'+
     '<span class="gmfq-pulse-instrument">'+htmlEscape(x.instrument)+' · dato '+htmlEscape(x.asOf)+'</span>'+
     '<div class="gmfq-pulse-metrics"><span>1D <b data-direction="'+dir(x.one)+'">'+bp(x.one)+'</b></span>'+
     '<span>1W <b data-direction="'+dir(x.week)+'">'+bp(x.week)+'</b></span></div>'+
     (opposite?'<small class="gmfq-pulse-caution">1D e 1W in direzioni diverse: non estrapolare il movimento.</small>':'')+
     '<details><summary>Fonte e limiti della lettura</summary><p>'+htmlEscape(x.source)+
     ' · '+htmlEscape(x.asOf)+'</p><p>'+htmlEscape(x.detail)+
     '</p><p>Variazioni dei tassi impliciti dello strumento indicato; non equivalgono a decisioni della banca centrale o a movimenti FX osservati.</p></details></article>';
  }).join(''):
    '<p class="gmfq-pulse-caption">Il feed non contiene dati di pricing sufficientemente recenti o verificabili. Nessuna notizia datata è mostrata come corrente.</p>';
   if(!rows.length){
    // A missing 1D repricing release does not mean no dated 6M market reference.
    // Recover the same audited G8 research matrix as Rates; never invent deltas.
    let recovered=false;
    try{
     const audited=window.GMFQ_OIS_RESEARCH_V1?.matrix;
     if(typeof audited==='function'){
      const feeds=await Promise.all([feed('OIS_OPERATIONAL_VIEW.json'),feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json')]);
      if(!host.isConnected||frame.contentDocument!==doc)return;
      const reference=audited(feeds[0],feeds[1],romeTodayIso());
      const valid=reference.length===8&&reference.every(x=>
       ['OFFICIAL','PROXY','MIXED','SCENARIO'].includes(x.tier)&&
       num(x.points?.['6m']?.value)!==null&&fresh(x.points['6m'].date,5));
      if(valid){
       box.innerHTML=reference.map(x=>
        '<article class="gmfq-pulse-item" data-pulse-context-ccy="'+x.ccy+
        '" data-pulse-quality="'+x.tier+'" data-research-only="true">'+
        '<strong>'+FLAG[x.ccy]+' '+x.ccy+' · 6M</strong>'+
        '<span class="gmfq-pulse-instrument">'+htmlEscape(x.tier==='OFFICIAL'?'FONTE CERTIFICATA':
          x.tier==='SCENARIO'?'SCENARIO EMPIRICO · NON OIS':
          x.tier==='MIXED'?'FUTURES INDICATIVO · DATE NON SINCRONIZZATE':
          'FUTURES INDICATIVO')+' · '+htmlEscape(x.points['6m'].date)+'</span>'+
        '<div class="gmfq-pulse-metrics"><span>Livello 6M <b> '+(x.tier==='OFFICIAL'?'':'≈')+
        fmt(x.points['6m'].value,2)+'%</b></span></div>'+
        '<small class="gmfq-pulse-caution">Solo livello dello strumento. Variazioni 1D/1W non certificate; non è previsione di policy, trade o ΔOIS.</small></article>'
       ).join('');
       host.dataset.pulseStatus='DATED_LEVEL_CONTEXT';
       host.dataset.asOf=romeTodayIso();
       date.textContent='Livelli 6M · data distinta per valuta';
       lead.textContent='Nessuna variazione recente validata. Riferimenti monetari 6M per tutte le G8, con qualità e data di origine; non sono segnali.';
       recovered=true;
      }
     }
    }catch(error){console.warn('[GMFQ Home 6M research references unavailable]',String(error))}
    if(!recovered)host.dataset.pulseStatus='WITHHELD';
   }

 }catch(e){
  if(!host.isConnected)return;
  host.dataset.pulseStatus='WITHHELD';
  date.textContent='Aggiornamento non disponibile';
  box.innerHTML='<p class="gmfq-pulse-caption">Pricing non verificabile al momento; le notizie esterne restano accessibili separatamente.</p>';
 }
}

/* Home Event Risk uses existing official Calendar seed only. It does NOT
   claim a release already happened, infer surprises or schedule anything.
   Same-day rows are excluded because many source times are absent; their
   availability cannot be verified without a timestamped release feed. */
function eventRadarRows(data,now=new Date()){
 const day=romeTodayIso(now),today=Date.parse(day+'T00:00:00Z');
 if(data?.schema!=='GMFQ_CALENDAR_OPERATIONAL_VIEW_V3'||
    data.status!=='ACTIVE_CB_PLUS_MACRO_OFFICIAL_WITH_SECONDARY_CONTEXT'||
    data.scope?.central_bank_schedule!=='ACTIVE_OFFICIAL'||
    data.scope?.macro_release_schedule!=='ACTIVE_OFFICIAL_VERIFIED_SEED'||
    data.scope?.consensus_context_only!==true||
    data.scope?.core_score_impact!==0||
    !Array.isArray(data.events)||
    !Number.isFinite(Date.parse(data.generated_at_utc))||
    Date.parse(data.generated_at_utc)>now.getTime()+3600000||
    !fresh(data.generated_at_utc.slice(0,10),3))return [];
 const allowed=new Set(['OFFICIAL_CONFIRMED','OFFICIAL_CALENDAR',
   'OFFICIAL_SCHEDULE_RULE','OFFICIAL_PROVISIONAL','OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER']);
 const result=[],seen=new Set;
 for(const e of data.events){
   if(!e||!FX.includes(e.ccy)||typeof e.title!=='string'||e.title.length<3||e.title.length>160||
      typeof e.date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(e.date)||
      !allowed.has(e.quality)||
      !['CENTRAL_BANK_DECISION','INFLATION','LABOUR','LABOUR_COST','GROWTH'].includes(e.event_type))continue;
   const at=Date.parse(e.date+'T00:00:00Z');
   // Strictly future Rome calendar dates: never show today's potentially
   // already-published data as if it were still upcoming.
   if(!Number.isFinite(at)||new Date(at).toISOString().slice(0,10)!==e.date||
      at<=today||at-today>21*86400000)continue;
   const isCB=e.event_type==='CENTRAL_BANK_DECISION';
   const source=isCB?e.source_layer:e.source_family;
   if(isCB ? e.source_layer!=='NATIVE_CB_DATA'||
        e.quality!=='OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER'
     :e.source_layer!=='MACRO_RELEASE_OFFICIAL_SEED_V1'||
       typeof source!=='string'||source.length>100)continue;
   const key=e.ccy+'|'+e.date+'|'+e.event_type+'|'+e.title;
   if(seen.has(key))continue;
   seen.add(key);
   const validTime=typeof e.time_local==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(e.time_local)&&
     typeof e.timezone==='string'&&e.timezone.length<=70;
   const consensus=e.consensus_status==='AVAILABLE'&&
     typeof e.consensus==='string'&&e.consensus.length<=40&&
     e.consensus_provider==='FOREX_FACTORY_FAIR_ECONOMY_WEEKLY';
   result.push({ccy:e.ccy,date:e.date,eventType:e.event_type,title:e.title,
     quality:e.quality,importance:e.importance==='HIGH'?'HIGH':'STANDARD',
     timeLocal:validTime?e.time_local:null,timezone:validTime?e.timezone:null,
     source:isCB?(e.bank||e.source_layer):source,
     consensus:consensus?e.consensus:null,consensusProvider:consensus?e.consensus_provider:null,
     isCB});
 }
 result.sort((a,b)=>a.date.localeCompare(b.date)||
   (a.importance==='HIGH'?0:1)-(b.importance==='HIGH'?0:1)||
   FX.indexOf(a.ccy)-FX.indexOf(b.ccy)||a.title.localeCompare(b.title));
 return result.slice(0,6);
}
async function mountHomeEventRadar(doc){
 if(!home()||frame.contentDocument!==doc||doc.documentElement.dataset.marketMode!=='live'||
    doc.getElementById('gmfq-event-radar'))return;
 const grid=doc.querySelector('.gridtop');if(!grid)return;
 const host=doc.createElement('section');host.id='gmfq-event-radar';
 host.dataset.calendarStatus='LOADING';host.dataset.signalEffect='NONE';
 host.setAttribute('aria-label','Event Risk: prossime pubblicazioni ufficiali e decisioni G8');
 host.innerHTML='<div class="gmfq-event-radar-head"><h2>Event Risk · prossime pubblicazioni</h2>'+
  '<span class="gmfq-event-radar-asof">Calendario in verifica</span></div>'+
  '<p class="gmfq-event-radar-intro">Agenda ufficiale, non notizie né risultati già pubblicati. Consenso separato dalle fonti.</p>'+
  '<div class="gmfq-event-radar-content"></div>';
 const pulse=doc.getElementById('gmfq-market-pulse');
 (pulse||grid).insertAdjacentElement('afterend',host);
 if(!doc.getElementById('gmfq-event-radar-style')){
  const st=doc.createElement('style');st.id='gmfq-event-radar-style';
  st.textContent='#gmfq-event-radar{margin:-2px 0 14px;padding:12px 15px;border:1px solid #284758;border-radius:6px;background:#091d2b;color:#d9e7f0;min-width:0;font-family:Arial,sans-serif}'+
   '#gmfq-event-radar .gmfq-event-radar-head{display:flex;justify-content:space-between;align-items:baseline;gap:6px 16px;flex-wrap:wrap}'+
   '#gmfq-event-radar h2{font:600 13px/1.4 Arial,sans-serif;margin:0;color:#e5edf3}'+
   '#gmfq-event-radar .gmfq-event-radar-asof{font:10px/1.4 Arial,sans-serif;color:#dfc689}'+
   '#gmfq-event-radar .gmfq-event-radar-intro{margin:4px 0 8px;font:10px/1.5 Arial,sans-serif;color:#a5bbca}'+
   '#gmfq-event-radar .gmfq-event-radar-list{margin:0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}'+
   '#gmfq-event-radar .gmfq-event-radar-list li{min-width:0;padding:8px 0;border-top:1px solid #284454}'+
   '#gmfq-event-radar .gmfq-event-line{display:flex;gap:6px 12px;justify-content:space-between;align-items:baseline}'+
   '#gmfq-event-radar .gmfq-event-line strong{font:600 11px/1.45 Arial,sans-serif;color:#e1eaf1;overflow-wrap:anywhere}'+
   '#gmfq-event-radar .gmfq-event-line time{flex-shrink:0;white-space:nowrap;color:#d6bd87;font:600 10px Arial,sans-serif}'+
   '#gmfq-event-radar .gmfq-event-meta{font:10px/1.5 Arial,sans-serif;color:#9fb8c9;overflow-wrap:anywhere}'+
   '#gmfq-event-radar .gmfq-event-secondary{display:block;color:#c2b39b;font:10px/1.5 Arial,sans-serif}'+
   '#gmfq-event-radar details{margin-top:8px}#gmfq-event-radar summary{cursor:pointer;color:#e2c785;font:600 10px/1.6 Arial,sans-serif;outline-offset:3px}'+
   '#gmfq-event-radar summary:focus-visible{outline:2px solid #e2c785}'+
   '#gmfq-event-radar .gmfq-event-method{font:10px/1.5 Arial,sans-serif;color:#9fb8c9;margin:6px 0 2px}'+
   '@media(max-width:600px){#gmfq-event-radar{padding:11px 12px}#gmfq-event-radar .gmfq-event-radar-list{grid-template-columns:1fr}}';
  doc.head.appendChild(st);
 }
 const content=host.querySelector('.gmfq-event-radar-content'),stamp=host.querySelector('.gmfq-event-radar-asof');
 try{
  const calendar=await feed('CALENDAR_OPERATIONAL_VIEW.json');
  if(!host.isConnected||frame.contentDocument!==doc)return;
  const rows=eventRadarRows(calendar);
  host.dataset.calendarStatus=rows.length?'FUTURE_VERIFIED_AGENDA':'WITHHELD';
  host.dataset.asOf=rows.length?calendar.generated_at_utc.slice(0,10):'';
  stamp.textContent=rows.length?'Calendario generato '+calendar.generated_at_utc.slice(0,10):'Agenda non disponibile';
  if(!rows.length){
   content.innerHTML='<p class="gmfq-event-radar-intro">Nessun evento futuro con copertura e data sufficientemente verificate.</p>';return;
  }
  const item=e=>'<li data-event-ccy="'+e.ccy+'" data-event-date="'+e.date+'" data-event-quality="'+e.quality+'">'+
   '<div class="gmfq-event-line"><strong>'+FLAG[e.ccy]+' '+e.ccy+' · '+htmlEscape(e.title)+'</strong>'+
   '<time datetime="'+e.date+'">'+e.date.slice(8,10)+'/'+e.date.slice(5,7)+'</time></div>'+
   '<div class="gmfq-event-meta">'+(e.isCB?'Decisione banca centrale':'Dato macro')+
   ' · '+(e.timeLocal?htmlEscape(e.timeLocal+' · '+e.timezone)+' (ora locale)':'Orario non certificato')+
   ' · '+htmlEscape(e.source)+'</div>'+
   (e.quality==='OFFICIAL_PROVISIONAL'?'<small class="gmfq-event-secondary">Data ufficiale provvisoria</small>':'')+
   (e.consensus?'<small class="gmfq-event-secondary">Consenso SECONDARIO: '+htmlEscape(e.consensus)+' · Forecast Forex Factory, non dato effettivo</small>':'')+
   '</li>';
  content.innerHTML='<ul class="gmfq-event-radar-list">'+rows.slice(0,2).map(item).join('')+'</ul>'+
   (rows.length>2?'<details class="gmfq-event-radar-more"><summary>Altri '+(rows.length-2)+' eventi G8 nel calendario</summary>'+
    '<ul class="gmfq-event-radar-list">'+rows.slice(2).map(item).join('')+'</ul></details>':'')+
   '<p class="gmfq-event-method">Date future secondo il calendario ufficiale caricato; gli eventi della giornata non sono mostrati come “ancora da pubblicare” senza conferma dell’orario. Nessuna sorpresa, bias o segnale dedotto.</p>';
 }catch(_){
  if(!host.isConnected)return;
  host.dataset.calendarStatus='WITHHELD';
  stamp.textContent='Agenda non disponibile';
  content.innerHTML='<p class="gmfq-event-radar-intro">Calendario non verificabile: nessuna data presentata come imminente.</p>';
 }
}
/* Pure 08:00 study readout. Previous completed weekday session, not the
   wall-clock date, is the expected date for ECB/VIX market observations.
   Source publication holidays are flagged for review, never guessed. */
function romePreviousWeekday(now=new Date()){
 const d=romeTodayIso(now),utc=new Date(d+'T00:00:00Z');
 if(!Number.isFinite(utc.getTime()))return null;
 do{utc.setUTCDate(utc.getUTCDate()-1)}while([0,6].includes(utc.getUTCDay()));
 return utc.toISOString().slice(0,10);
}
function homeMorningStudySources(fx,model,setup,rates,ois,news,calendar,now=new Date()){
 const today=romeTodayIso(now),prior=romePreviousWeekday(now);
 if(!prior)return null;
 const dateOk=d=>/^\d{4}-\d{2}-\d{2}$/.test(d||'')&&d>=prior&&d<=today;
 const marketObs=d=>dateOk(d);
 const fxOk=fx?.status==='CURRENT_OFFICIAL_HISTORY'&&Array.isArray(fx?.rows)&&
   fx.rows.length>=21&&fx.row_count===fx.rows.length&&
   fx.rows[fx.rows.length-1]?.Date===fx.last_as_of&&marketObs(fx.last_as_of)&&
   FX.every(c=>num(fx.rows[fx.rows.length-1]?.[c])!==null&&fx.rows[fx.rows.length-1][c]>0);
 const pairOk=setup?.status==='CURRENT_CANONICAL_ENGINE'&&setup.pair_count===28&&
   setup.price_audit?.status==='PASS'&&setup.price_asof===fx?.last_as_of&&
   marketObs(setup.price_asof);
 const vix=model?.risk?.VIX;
 const vixOk=!!vix&&Array.isArray(vix.dates)&&vix.dates.length>0&&
   vix.dates[vix.dates.length-1]===vix.last_date&&num(vix.last_value)!==null&&
   marketObs(vix.last_date);
 const builtToday=feed=>{
   const stamp=feed?.generated_at_utc;
   // Do not promote an unzoned or future-dated source as available at 08:00.
   if(typeof stamp!=='string'||!/(Z|[+-]\d{2}:\d{2})$/i.test(stamp))return false;
   const x=new Date(stamp);
   return Number.isFinite(x.getTime())&&x.getTime()<=now.getTime()&&romeTodayIso(x)===today;
 };
 const checks={
   fx:!!fxOk,pairs:!!pairOk,vix:!!vixOk,
   news:builtToday(news),calendar:builtToday(calendar)
 };
 const confirmed=Object.values(checks).filter(Boolean).length;
 const rateRecent=FX.filter(c=>{
   const x=rates?.[c];
   return x&&String(x.quality||'').includes('OFFICIAL')&&fresh(x.date,5)&&
      num(x['2Y'])!==null&&num(x['10Y'])!==null;
 });
 const official=FX.filter(c=>officialPricingCurrent(ois?.currencies?.[c]));
 const estimated=FX.filter(c=>ois?.currencies?.[c]?.operational_status==='GREEN_ESTIMATED'&&
   !official.includes(c)&&fresh(ois.currencies[c].as_of,5));
 const withoutOis=FX.filter(c=>!official.includes(c)&&!estimated.includes(c));
 const macroDay=canonicalPairMacroBaseline(setup,model);
 return {checks,confirmed,total:5,prior,fxDay:fxOk?fx.last_as_of:null,
   vixDay:vixOk?vix.last_date:null,rateRecent,rateLag:FX.filter(c=>!rateRecent.includes(c)),
   official,estimated,withoutOis,macroDay,
   mode:confirmed===5?'DAILY_VERIFIED_WITH_GAPS':'DAILY_INCOMPLETE',
   sourceEffect:'NONE'};
}
function mountHomeFreshnessAudit(doc,fx,rates,ois,dxy,proxy,model,setup,news,calendar){
 if(!home()||frame.contentDocument!==doc||doc.documentElement.dataset.marketMode!=='live')return;
 const head=doc.querySelector('.mast .fresh'),state=doc.getElementById('liveState'),
  stamp=doc.getElementById('liveAsOf');
 if(!head||!state||!stamp||doc.getElementById('gmfq-home-data-audit'))return;
 const datePattern=/^\d{4}-\d{2}-\d{2}$/;
 const fxStatus=valuteFxSourceStatus(fx);
 const fxDay=fxStatus.asof;
 const fxCurrent=fxStatus.status==='OFFICIAL_FIXING_RECENT';
 const macroDay=canonicalMacroBaselineAsOf(model);
 const pairMacroDay=canonicalPairMacroBaseline(setup,model);
 const macroCurrent=pairMacroDay!==null&&fresh(pairMacroDay,10);
 const ratesCurrent=FX.filter(k=>{
  const x=rates?.[k];
  return x&&String(x.quality||'').includes('OFFICIAL')&&fresh(x.date,5)&&
   num(x['2Y'])!==null&&num(x['10Y'])!==null;
 });
 const oisCurrent=FX.filter(k=>{
  const x=ois?.currencies?.[k];
  return officialPricingCurrent(x);
 });
 // Independent read-only research coverage, computed from the same dated
 // per-tenor source guards as the G8 Rates matrix (never as official OIS).
 let research=null;
 const api=window.GMFQ_OIS_RESEARCH_V1;
 if(ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
    api&&typeof api.coverage==='function'){
   try{
     const r=api.coverage(ois,proxy,romeTodayIso());
     if(r?.schema==='GMFQ_OIS_G8_RESEARCH_COVERAGE_V1'&&r.total===8&&
        r.official_count===oisCurrent.length&&
        r.no_ois_official_promotion===true&&r.core_effect==='NONE'&&
        r.pair_effect==='NONE'&&r.backtest_estimated_as_official===false)research=r;
   }catch(e){console.warn('[GMFQ OIS coverage WITHHELD]',String(e))}
 }
 const contextCount=research?.covered_count??null;
 const contextCodes=research?.context_codes||[];
 const incompleteCodes=research?.incomplete_codes||[];
 const dxyCurrent=validDxy(dxy);
 const complete=fxCurrent&&ratesCurrent.length===8&&oisCurrent.length===8&&dxyCurrent&&macroCurrent;
 const morning=homeMorningStudySources(fx,model,setup,rates,ois,news,calendar);
 mountHomeReadingPath(doc,{macroDay:pairMacroDay,fxCurrent,fxDay,oisCount:oisCurrent.length,setup});
 // One editorial source line, not another card or a new reliability score.
 const rail=doc.getElementById('gmfq-home-reading-path');
 if(rail&&morning){
   const note=doc.createElement('p');
   note.id='gmfq-morning-study-readiness';
   note.setAttribute('role','status');
   note.dataset.state=morning.mode;
   note.dataset.sourceEffect='NONE';
   note.dataset.priorSession=morning.prior;
   note.dataset.verified=String(morning.confirmed);
   note.dataset.fx=String(morning.checks.fx);
   note.dataset.pairs=String(morning.checks.pairs);
   note.dataset.vix=String(morning.checks.vix);
   note.dataset.news=String(morning.checks.news);
   note.dataset.calendar=String(morning.checks.calendar);
   note.dataset.lagRates=morning.rateLag.join(',');
   note.dataset.withheldOis=morning.withoutOis.join(',');
   note.textContent='STUDIO MATTUTINO · '+morning.confirmed+'/5 fonti giornaliere verificate '+
     '(ultima seduta '+morning.prior+'). '+
     (morning.confirmed===5?'Prezzi FX, coppie, VIX e notizie/calendario verificati.':
     'Da verificare: '+Object.keys(morning.checks).filter(c=>!morning.checks[c]).join(', ')+'.')+
     ' Rendimenti recenti '+morning.rateRecent.length+'/8; OIS ufficiali '+
     morning.official.length+'/8, stime '+morning.estimated.length+'/8; '+
     'Macro '+(morning.macroDay||'non verificato')+' (baseline storica).';
   rail.querySelector('.gmfq-reading-main')?.appendChild(note);
   const st=doc.createElement('style');st.id='gmfq-morning-study-style';
   st.textContent='#gmfq-morning-study-readiness{color:#b7c7d1;font:11px/1.55 Arial,sans-serif;'+
     'margin:9px 0 0;padding:7px 0 0;border-top:1px solid #375366;max-width:700px;overflow-wrap:anywhere}'+
     '#gmfq-morning-study-readiness[data-state="DAILY_INCOMPLETE"]{color:#e7c187}'+
     '@media(max-width:600px){#gmfq-morning-study-readiness{font-size:10px}}';
   doc.head.appendChild(st);
 }
 state.textContent=complete?'FONTI VERIFICATE':'DATI PARZIALI';
 stamp.textContent=(fxCurrent?'FX '+fxDay.slice(8,10)+'/'+fxDay.slice(5,7):'FX non corr.')+' · OIS '+oisCurrent.length+'/8 cert. · Contesto '+(contextCount===null?'n.d.':contextCount+'/8')+' · Macro '+(macroCurrent?'verif.':'stor./n.v.')+' ⓘ';
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
  line('Studio delle 08:00 · ultime fonti giornaliere',
    morning?morning.confirmed+'/5 verifiche rispetto alla seduta '+morning.prior+'. '+
      'FX '+(morning.checks.fx?'OK':'DA VERIFICARE')+
      '; coppie '+(morning.checks.pairs?'OK':'DA VERIFICARE')+
      '; VIX '+(morning.checks.vix?'OK':'DA VERIFICARE')+
      '; News Pulse '+(morning.checks.news?'OK':'DA VERIFICARE')+
      '; calendario '+(morning.checks.calendar?'OK':'DA VERIFICARE')+
      '. Restano distinti i ritardi dei rendimenti, i proxy OIS e gli score Macro storici.':
      'Impossibile verificare la sessione precedente: non attribuire lo stato GREEN ai dati.')+
  line('FX G8 · fixing BCE',fxCurrent?'Ufficiale · '+fxDay+' · fine giornata, non intraday':
    'Non corrente o non disponibile · ultima data '+(fxDay||'non verificata'))+
  line('Rendimenti governativi 2Y/10Y',ratesCurrent.length+'/8 valute con 2Y e 10Y ufficiali sufficientemente recenti.'+
    (withheldRates.length?' Da aggiornare: '+withheldRates.join(', ')+'.':'')+
    (datePattern.test(pairedCHF||'')?' Ultima coppia CHF: '+pairedCHF+'.':''))+
  line('Market Pricing · fonti certificate',oisCurrent.length+'/8 valute con pricing 3M/6M/12M certificato e recente.'+
    (withheldOis.length?' Non certificate o datate: '+withheldOis.join(', ')+'.':'')+
    ' GBP OIS BoE; JPY, AUD e CAD futures monetari, non OIS puri (fonti certificate).')+
  line('Contesto monetario G8 · ricerca',research?
    contextCount+'/8 valute con tre orizzonti verificati entro cinque giorni. '+
    (contextCodes.length?'Futures indicativi/scenari: '+contextCodes.join(', ')+'. ':'')+
    (incompleteCodes.length?'Non completi o datati: '+incompleteCodes.join(', ')+'. ':'')+
    'EUR: osservazioni con date separate, non una curva OIS sincronizzata. NZD: proxy Bank Bill−cash calibrato su 19 osservazioni RBNZ (24 bp), non OIS osservato. Nessun impatto sulle 28 coppie.':
    'Copertura ricerca non verificabile. Non viene promossa alcuna stima a dato ufficiale.')+
  line('Macro/Tassi · baseline strutturale',pairMacroDay?
    'Snapshot verificato tra D.json e motore 28 coppie: '+pairMacroDay+
    (macroCurrent?'. Data entro il limite di freschezza; non è una nuova lettura.':
      '. NON CORRENTE: i 24 score e i bias strutturali sono storici, da rivalidare.'):
    'Baseline NON VERIFICABILE tra snapshot Macro e setup delle 28 coppie. D.json: '+
    (macroDay||'non certificato')+'; Pair: '+(setup?.macro_baseline_asof||'non certificato')+
    '. Non promuovere score o tesi senza riconciliazione.')+
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
 const [rr,oo,pp,dd,ff,mm,ss,nn,cc]=await Promise.allSettled([
  feed('NATIVE_RATES_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json'),
  feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),feed('DXY_SYNTHETIC_ECB.json'),
  feed('ECB_G8_PRICE_HISTORY.json'),feed('D.json'),feed('PAIR_SETUP_OPERATIONAL_VIEW.json'),
  feed('NEWS_PULSE_OPERATIONAL.json'),feed('CALENDAR_OPERATIONAL_VIEW.json')]);
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
         if(b){legend.dataset.gmfqYieldMode=b.dataset.gmfqTenor;yieldChart(doc,all,b.dataset.gmfqTenor);return;}
         const c=ev.target.closest('button[data-gmfq-ccy-focus]')?.dataset.gmfqCcyFocus;
         if(!FX.includes(c))return;
         legend.dataset.gmfqCurrencyFocus=legend.dataset.gmfqCurrencyFocus===c?'ALL':c;
         yieldChart(doc,all,legend.dataset.gmfqYieldMode||'2Y');
       });
     }
     rateBar(doc,all,'ratesbars');rateBar(doc,all,'spreads',true);
   }
   if(ois)oisAll(doc,ois,proxy);
   mountHomeCurrencyFlags(doc);
   renderDxy(doc);
   mountHomeMarketPulse(doc).catch(e=>console.warn('[GMFQ Market Pulse]',String(e)));
   mountHomeEventRadar(doc).catch(e=>console.warn('[GMFQ Event Risk]',String(e)));
   mountHomeFreshnessAudit(doc,ff.status==='fulfilled'?ff.value:null,rates,ois,d,proxy,
     mm.status==='fulfilled'?mm.value:null,ss.status==='fulfilled'?ss.value:null,
     nn.status==='fulfilled'?nn.value:null,cc.status==='fulfilled'?cc.value:null);
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

/* Restore existing sovereign chart from verified, same-day historical 2Y/10Y pairs. */
function sovereignHistoryPairs(rates,k){
 const r=rates?.[k],a=r?.history2,b=r?.history10,valid=d=>/^\d{4}-\d{2}-\d{2}$/.test(d||'');
 if(!r||!String(r.quality||'').includes('OFFICIAL')||!valid(r.date)||
    !Array.isArray(a?.dates)||!Array.isArray(a?.values)||
    !Array.isArray(b?.dates)||!Array.isArray(b?.values)||
    a.dates.length!==a.values.length||b.dates.length!==b.values.length)return [];
 const two=new Map(a.dates.map((d,i)=>[d,num(a.values[i])]));
 const rows=b.dates.map((d,i)=>({d,y2:two.get(d),y10:num(b.values[i])}))
  .filter(x=>valid(x.d)&&x.d<=r.date&&x.y2!==null&&x.y2!==undefined&&
    x.y10!==null&&x.y2>-5&&x.y2<30&&x.y10>-5&&x.y10<30)
  .sort((x,y)=>x.d.localeCompare(y.d));
 if(rows.length<2||rows.at(-1).d!==r.date||Math.abs(rows.at(-1).y2-r['2Y'])>.002||
    Math.abs(rows.at(-1).y10-r['10Y'])>.002)return [];
 const last=Date.parse(r.date+'T00:00:00Z'),recent=rows.filter(x=>
  Date.parse(x.d+'T00:00:00Z')>=last-184*86400000);
 return recent.length>=2?recent:rows.slice(-40);
}
function mountSovereignHistoryPlot(doc,rates){
 const host=doc.getElementById('rates-chart'),sel=doc.getElementById('rates-select');
 if(!host||!sel||host.dataset.sovereignPlotMounted)return;
 host.dataset.sovereignPlotMounted='true';
 const css=doc.createElement('style');css.textContent=
  '#rates-chart{height:auto!important;min-height:260px;overflow:visible!important}'+
  '#rates-chart [data-gmfq-sovereign-plot]{width:100%;height:auto;display:block;max-height:330px}'+
  '#rates-chart .gmfq-gov-source{display:flex;justify-content:space-between;flex-wrap:wrap;gap:5px;color:#b9ccda;font:11px/1.5 Arial,sans-serif}'+
  '#rates-chart .gmfq-gov-legend{color:#c4d7e7;font:11px/1.6 Arial,sans-serif}'+
  '#rates-chart .gmfq-gov-axes text{fill:#a4bfce;font:11px Arial,sans-serif}';
 doc.head.appendChild(css);
 const paint=()=>{
  if(route()!=='tassi'||frame.contentDocument!==doc||!host.isConnected)return;
  const k=(sel.querySelector('button[aria-pressed="true"][data-ccy]')||
   sel.querySelector('button.active[data-ccy]'))?.dataset.ccy||'USD';
  const rows=sovereignHistoryPairs(rates,k);host.dataset.gmfqSovereignCcy=k;
  host.dataset.gmfqSovereignCount=String(rows.length);
  if(rows.length<2){host.innerHTML='<p>Storico 2Y/10Y omogeneo insufficiente per '+k+
   '. Nessuna serie ricostruita.</p>';return;}
  const vals=rows.flatMap(x=>[x.y2,x.y10]),lo=Math.floor((Math.min(...vals)-.2)*4)/4,
   hi=Math.ceil((Math.max(...vals)+.2)*4)/4,span=hi-lo||1,
   first=Date.parse(rows[0].d+'T00:00:00Z'),last=Date.parse(rows.at(-1).d+'T00:00:00Z');
  const px=d=>62+814*(Date.parse(d+'T00:00:00Z')-first)/(last-first||1),
   py=v=>28+203*(hi-v)/span;
  const axes=Array.from({length:5},(_,i)=>{
   let v=lo+i*span/4,y=py(v);
   return '<line x1="62" x2="876" y1="'+y+'" y2="'+y+
    '" stroke="#29485b"/><text x="53" y="'+(y+4)+'" text-anchor="end">'+fmt(v,2)+'%</text>';
  }).join('')+[0,.25,.5,.75,1].map(q=>{
   let d=rows[Math.round(q*(rows.length-1))].d;
   return '<text x="'+px(d)+'" y="272" text-anchor="middle">'+d.slice(5)+'</text>';
  }).join('');
  const trace=(field,tenor,color)=>'<polyline data-tenor="'+tenor+
    '" fill="none" stroke="'+color+'" stroke-width="3" points="'+
    rows.map(x=>px(x.d).toFixed(1)+','+py(x[field]).toFixed(1)).join(' ')+
    '"/><circle cx="'+px(rows.at(-1).d)+'" cy="'+py(rows.at(-1)[field])+
    '" r="4" fill="'+color+'"/>';
  const asof=rows.at(-1).d,old=romeCalendarAge(asof)>5;
  host.innerHTML='<div class="gmfq-gov-source"><b>'+FLAG[k]+' '+k+
   ' · 2Y / 10Y</b><span>'+(old?'STORICO':'OSSERVATO')+' · '+asof+
   ' · '+rows.length+' date comuni</span></div>'+
   '<svg data-gmfq-sovereign-plot="TRUE" data-ccy="'+k+
   '" viewBox="0 0 900 285" role="img" aria-label="'+k+' storico 2Y e 10Y verificato">'+
   '<g class="gmfq-gov-axes">'+axes+'</g>'+trace('y2','2Y','#67bcff')+
   trace('y10','10Y','#e6c476')+'</svg><div class="gmfq-gov-legend">● 2Y azzurro · ● 10Y oro · NATIVE_RATES_DATA, date abbinate · non OIS</div>';
  const meta=doc.getElementById('rates-chart-meta');
  if(meta)meta.textContent=k+' · '+(old?'storico non corrente':'ultima rilevazione')+
   ' '+asof+' · solo rendimenti governativi';
 };
 sel.addEventListener('click',e=>{
  if(e.target.closest('button[data-ccy]')){
   doc.defaultView.setTimeout(paint,0);doc.defaultView.setTimeout(paint,120);
  }
 });
 const obs=new doc.defaultView.MutationObserver(()=>{
  if(host.dataset.gmfqSovereignCount!=='0'&&!host.querySelector('svg[data-gmfq-sovereign-plot]'))
   doc.defaultView.queueMicrotask(paint);
 });
 obs.observe(host,{childList:true});paint();
}
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

/* Date-coherent 2Y/10Y G8 snapshot for research only. Stale but audited
   observations are displayed as historical; beta scenarios never become spread
   data or a policy repricing input. Source alignment is verified per tenor. */
function yieldStudySnapshot(raw,derived){
 const rows=FX.map(ccy=>{
  const source=raw?.[ccy],day=source?.date,age=romeCalendarAge(day);
  const valid=source&&typeof source.quality==='string'&&source.quality.includes('OFFICIAL')&&
   Number.isInteger(age)&&age>=0&&
   ['2Y','10Y'].every((term)=>{
    const h=term==='2Y'?source.history2:source.history10;
    return Array.isArray(h?.dates)&&Array.isArray(h?.values)&&h.dates.length>=20&&
      h.dates.length===h.values.length&&h.dates.at(-1)===day&&
      num(h.values.at(-1))!==null&&num(source[term])!==null&&
      Math.abs(h.values.at(-1)-source[term])<=0.00001&&
      source[term]>-5&&source[term]<25;
   });
  const historic=!!valid&&age>4;
  let scenario=null;
  const model=derived?.[ccy],expected=ccy==='CHF'?'EUR':ccy==='NZD'?'AUD':null;
  if(historic&&expected&&model?.estimate2===true&&model?.estimate10===true&&
     model.proxy===expected&&model.estimatedAsOf2===model.estimatedAsOf10&&
     model.estimatedAsOf2===raw?.[expected]?.date&&
     Number.isInteger(romeCalendarAge(model.estimatedAsOf2))&&
     romeCalendarAge(model.estimatedAsOf2)>=0&&romeCalendarAge(model.estimatedAsOf2)<=4&&
     num(model.v2)!==null&&num(model.v10)!==null&&
     num(model.r2_2)!==null&&num(model.r2_10)!==null&&
     model.r2_2>=0&&model.r2_2<=1&&model.r2_10>=0&&model.r2_10<=1&&
     ['ALTA','MEDIA','BASSA'].includes(model.confidence2)&&
     ['ALTA','MEDIA','BASSA'].includes(model.confidence10)){
   scenario={v2:model.v2,v10:model.v10,proxy:expected,date:model.estimatedAsOf2,
     confidence2:model.confidence2,confidence10:model.confidence10};
  }
  return {ccy,asof:valid?day:null,v2:valid?source['2Y']:null,v10:valid?source['10Y']:null,
   status:!valid?'UNAVAILABLE':historic?'HISTORICAL':'RECENT',
   // Historical slope is real only at the historical same-date snapshot.
   slopeBp:valid?Math.round(100*(source['10Y']-source['2Y'])*10)/10:null,
   scenario};
 });
 return {rows,covered:rows.filter(r=>r.status!=='UNAVAILABLE').length,
  recent:rows.filter(r=>r.status==='RECENT').length,
  scenarios:rows.filter(r=>r.scenario).length};
}

/* Separate secondary market observations: not the SNB/RBNZ official 2Y,
   not a fresh 10Y slope, pair spread, V2 economic score or trading signal.
   A retained market observation must retain its actual timestamp forever. */
const SECONDARY_2Y_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/validation/rates/fixtures/chf_nzd_2y_secondary_market_2026-10-30.json';
async function fetchSecondary2Y(){
 const ctrl=new AbortController(),t=setTimeout(()=>ctrl.abort(),11000);
 try{const r=await fetch(SECONDARY_2Y_URL,{cache:'no-store',signal:ctrl.signal});
  if(!r.ok)throw Error('Secondary market 2Y HTTP '+r.status);
  return await r.json();
 }finally{clearTimeout(t)}
}
function secondary2YObservation(snap,rates,ccy){
 const allowed=['CHF','NZD'];
 const g=snap?.governance,r=snap?.observations?.[ccy],old=rates?.[ccy],q=r?.source_quotes;
 if(!allowed.includes(ccy)||
    snap?.schema!=='GMFQ_CHF_NZD_2Y_SECONDARY_MARKET_SNAPSHOT_V1'||
    snap.status!=='SECONDARY_OBSERVED_2Y_REFERENCE_RESEARCH_ONLY'||
    snap.source_quotes_not_guaranteed_identical_benchmark!==true||
    snap.values_not_independent_closing_auctions!==true||
    g?.canonical_native_rates_unchanged!==true||
    g?.official_rates_history_untouched!==true||
    g?.no_cross_country_spread!==true||
    g?.no_same_currency_2y_10y_slope!==true||
    g?.eligible_for_macro_score!==false||g?.eligible_for_28pair_bias!==false||
    g?.eligible_for_beta_or_forward!==false||g?.eligible_for_automatic_canonical_promotion!==false||
    g?.data_are_not_2y_OIS!==true||
    r?.currency!==ccy||r.tenor!=='2Y'||r.market_observation_date!==snap.as_of||
    !Array.isArray(q)||q.length!==(ccy==='CHF'?3:2)||
    r.quote_source_count!==q.length||
    r.range_kind!=='CROSS_PROVIDER_DISPERSION_NOT_CONFIDENCE_INTERVAL'||
    !['SECONDARY_MARKET_INDICATIVE_MIXED_INSTRUMENT_BASIS',
      'SECONDARY_MARKET_INDICATIVE_NOT_RBNZ_B2_CERTIFIED'].includes(r.quality)||
    !old||!String(old.quality||'').includes('OFFICIAL')||
    num(old['2Y'])===null||!Number.isInteger(romeCalendarAge(old.date))||
    !(r.market_observation_date>old.date))return null;
 const age=romeCalendarAge(r.market_observation_date);
 if(!Number.isInteger(age)||age<0)return null;
 const vals=[];
 for(const obs of q){
  let u;try{u=new URL(obs.url)}catch(_){return null}
  if(u.protocol!=='https:'||!['www.investing.com','tradingeconomics.com','www.worldgovernmentbonds.com'].includes(u.hostname)||
     obs.observation_date!==r.market_observation_date||
     num(obs.value_pct)===null||obs.value_pct < -5||obs.value_pct > 25)return null;
  vals.push(obs.value_pct);
 }
 const z=vals.slice().sort((a,b)=>a-b);
 const median=(z[Math.floor((z.length-1)/2)]+z[Math.ceil((z.length-1)/2)])/2;
 if(num(r.value_pct)===null||num(r.range_min_pct)===null||num(r.range_max_pct)===null||
    Math.abs(median-r.value_pct)>1e-8||Math.abs(z[0]-r.range_min_pct)>1e-8||
    Math.abs(z.at(-1)-r.range_max_pct)>1e-8)return null;
 return {ccy,value:r.value_pct,date:r.market_observation_date,age,
   min:r.range_min_pct,max:r.range_max_pct,sourceCount:q.length,
   tier:'SECONDARY_OBSERVED_NOT_OFFICIAL',sources:q.map(x=>({name:x.publisher,url:x.url})),
   noSpread:true,noSignal:true,stale:age>5};
}
function secondary2YReading(snap,rates,ccy){
 const old=rates?.[ccy];
 if(old&&String(old.quality||'').includes('OFFICIAL')&&
    fresh(old.date,5)&&num(old['2Y'])!==null)return null;
 return secondary2YObservation(snap,rates,ccy);
}

/* Two matching RBNZ B2 HTML reads: display-only, not independent XLSX review. */
function nzdWebReviewCandidate(canonical,c){
 const r=canonical?.NZD,g=c?.governance||{},e=c?.evidence||{};
 const age=romeCalendarAge(c?.as_of);
 if(c?.schema!=='GMFQ_NZD_B2_GOVT_WEB_REVIEW_CONTEXT_V1'||
   c.status!=='TWO_WEB_READS_MATCH__UNAPPROVED_RESEARCH_ONLY'||
   c.currency!=='NZD'||c.source!=='Reserve Bank of New Zealand'||
   c.instrument!=='RBNZ B2 NZFMA benchmark government bond indicative close'||
   c.source_url!=='https://www.rbnz.govt.nz/en/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'||
   c.released_on!=='2026-10-23'||r?.date!=='2026-10-16'||
   c.canonical_at_review?.as_of!==r.date||
   num(c.canonical_at_review?.['2Y'])===null||num(c.canonical_at_review?.['10Y'])===null||
   Math.abs(c.canonical_at_review['2Y']-r['2Y'])>0.00001||
   Math.abs(c.canonical_at_review['10Y']-r['10Y'])>0.00001||
   !(c.as_of>r.date)||!Number.isInteger(age)||age<0||age>14||
   num(c['2Y'])===null||num(c['10Y'])===null||
   !(c['2Y']>0&&c['2Y']<20&&c['10Y']>0&&c['10Y']<20)||
   num(c.curve_bp)===null||
   Math.abs(c.curve_bp-Math.round((c['10Y']-c['2Y'])*1000)/10)>0.001||
   e.first_web_review!=='FIRST_REVIEW_COMPLETE_SECOND_INDEPENDENT_REVIEW_PENDING'||
   e.second_web_review!=='SECOND_OFFICIAL_WEB_READ_MATCHES_FIRST_REVIEW__MANUAL_APPROVAL_PENDING'||
   e.matched_rows!==10||e.independent_xlsx_review_completed!==false||
   e.independent_human_reviewer_confirmed!==false||
   g.official_canonical_untouched!==true||g.eligible_for_rate_spreads!==false||
   g.core_score_effect!=='NONE'||g.pair_engine_effect!=='NONE'||
   g.bias_effect!=='NONE'||g.sizing_effect!=='NONE'||
   g.eligible_for_backtests!==false||g.eligible_for_automatic_promotion!==false||
   g.live_data_promotion_allowed!==false)return null;
 return {date:c.as_of,v2:c['2Y'],v10:c['10Y'],slopeBp:c.curve_bp,
   historical:age>4,source:c.source_url,approval:'PENDING'};
}

/* Keep observed historical NZD and CHF sovereign yields visible in ORIGINAL G8 table.
   Reconstruct a relative-US spread only at the last actual SAME-DATE observation. */
function historicalSovereignTableRows(raw){
 const study=yieldStudySnapshot(raw,ratesAll(raw));
 const usd=new Map(dateHistory(raw?.USD,'history2').map(p=>[p.date,p.v]));
 return ['NZD','CHF'].map(ccy=>{
  const r=study.rows.find(x=>x.ccy===ccy);
  if(r?.status!=='HISTORICAL'||num(r.v2)===null||num(r.v10)===null)return null;
  const common=dateHistory(raw[ccy],'history2').filter(p=>p.date<=r.asof&&usd.has(p.date));
  const last=common.at(-1);
  if(!last)return null;
  return {ccy,asof:r.asof,v2:r.v2,v10:r.v10,slopeBp:r.slopeBp,
   usDate:last.date,usSpreadBp:(last.v-usd.get(last.date))*100,scenario:r.scenario};
 }).filter(Boolean);
}
function mountHistoricalSovereignTable(doc,raw){
 const tbody=doc.getElementById('rates-rows');
 if(!tbody||tbody.dataset.gmfqHistoryAdapter==='true')return;
 tbody.dataset.gmfqHistoryAdapter='true';
 const found=new Map(historicalSovereignTableRows(raw).map(x=>[x.ccy,x]));
 const css=doc.createElement('style');css.id='gmfq-native-history-style';
 css.textContent='#rates-rows tr[data-gmfq-historical-yield] td{vertical-align:middle}'+
  '#rates-rows .gmfq-history-date{display:block;color:#e8c77c;font:600 10px/1.35 Arial,sans-serif;margin-top:3px}'+
  '#rates-rows .gmfq-history-est{display:block;color:#acd2e6;font:10px/1.35 Arial,sans-serif;white-space:normal;margin-top:3px}'+
  '#rates-rows .gmfq-history-spread-date{display:block;color:#e5c98e;font:9px/1.35 Arial,sans-serif;white-space:normal}'+
  '#rates-rows .gmfq-history-badge{color:#e5c98e!important;border:1px solid #927a49!important;white-space:nowrap}'+
  '#gmfq-native-history-note{color:#b9cddd;padding:7px 12px;font:11px/1.55 Arial,sans-serif}'+
  '@media(max-width:600px){#rates-rows .gmfq-history-badge{font-size:9px}}';
 doc.head.appendChild(css);
 const draw=()=>{
  if(route()!=='tassi'||frame.contentDocument!==doc||!tbody.isConnected)return;
  const rows=[...tbody.querySelectorAll(':scope > tr')];
  if(rows.length!==8)return;
  for(const [ccy,name] of [['NZD','Nuova Zelanda'],['CHF','Svizzera']]){
   const row=rows.find(x=>x.cells?.[0]?.textContent.includes(name)),r=found.get(ccy);
   if(!row||row.cells.length!==7||!r||row.dataset.gmfqHistoricalYield===r.asof)continue;
   row.dataset.gmfqHistoricalYield=r.asof;row.dataset.gmfqHistoricalSpreadDate=r.usDate;
   row.dataset.gmfqProvenance='OFFICIAL_HISTORICAL_SAME_DAY_2Y_10Y';
   const pct=n=>fmt(n,3)+'%';
   row.cells[0].innerHTML='<strong>'+FLAG[ccy]+' '+htmlEscape(name)+'</strong>'+
    '<small class="gmfq-history-date">STORICO '+htmlEscape(r.asof)+'</small>';
   row.cells[1].innerHTML=pct(r.v2)+(r.scenario?
    '<small class="gmfq-history-est">β ≈'+pct(r.scenario.v2)+' · '+htmlEscape(r.scenario.date)+'</small>':'');
   row.cells[2].innerHTML=pct(r.v10)+(r.scenario?
    '<small class="gmfq-history-est">β ≈'+pct(r.scenario.v10)+' · '+htmlEscape(r.scenario.date)+'</small>':'');
   row.cells[3].textContent=(r.slopeBp>=0?'+':'')+fmt(r.slopeBp,1)+' bp';
   row.cells[4].innerHTML=(r.usSpreadBp>=0?'+':'')+fmt(r.usSpreadBp,1)+' bp'+
    '<small class="gmfq-history-spread-date">data comune '+htmlEscape(r.usDate)+'</small>';
   row.cells[4].title='Spread storico '+ccy+' − USA del '+r.usDate+
    '. Data diversa dal rendimento 2Y/10Y mostrato: NON spread corrente.';
   row.cells[5].textContent=r.asof;
   row.cells[6].innerHTML='<span class="desk-quality gmfq-history-badge">CERTIFICATO · STORICO</span>';
  }
  const panel=tbody.closest('.desk-panel');
  if(panel&&!panel.querySelector('#gmfq-native-history-note')){
   const note=doc.createElement('p');note.id='gmfq-native-history-note';
   note.textContent='NZD e CHF: rendimenti 2Y/10Y ufficiali ma storici, NON livelli correnti. “2Y vs US” usa l’ultima data comune verificata indicata nella cella, non la data del rendimento sopra. Eventuali stime β sono separate: nessun effetto su score, coppie o backtest.';
   panel.appendChild(note);
  }
 };
 const watcher=new doc.defaultView.MutationObserver(draw);
 watcher.observe(tbody,{childList:true,subtree:true});draw();
}
function renderYieldStudy(doc,rates,snb,webReview,secondary2y){
 if(route()!=='tassi'||frame.contentDocument!==doc||doc.getElementById('gmfq-yields-study'))return;
 const anchor=doc.getElementById('rates-rows')?.closest('.desk-panel');
 if(!anchor)return;
 const derived=ratesAll(rates),out=yieldStudySnapshot(rates,derived);
 const nzWeb=nzdWebReviewCandidate(rates,webReview);
 // Show history-rebasing provenance only when present in the independently
 // source-verified ECB candidate or a separately approved public transition.
 // A change in CHF model estimates is NOT an official CHF yield movement.
 const rebase=rates?.EUR?.historical_curve_rebase;
 const rebaseStatus=rebase?.schema==='GMFQ_EUR_2Y_10Y_HISTORY_REBASE_NOTICE_V1'&&
  rebase.source_authority==='European Central Bank'&&
  rebase.source_rebase_not_market_move===true&&
  rebase.chf_reference_beta_recalibration_not_official_chf_yield===true&&
  ['RESEARCH_CANDIDATE_NOT_PUBLISHED','PUBLISHED_AFTER_SOURCE_AND_BROWSER_QA'].includes(rebase.status)
  ?rebase.status:null;
 const rebaseIntro=rebaseStatus==='RESEARCH_CANDIDATE_NOT_PUBLISHED'
  ?'ANTEPRIMA RICERCA · ':'STORICO BCE RICALIBRATO · ';
 const rebaseNotice=rebaseStatus?
  '<div class="gmfq-yield-rebase" data-rebase-status="'+htmlEscape(rebaseStatus)+'">'+
  '<strong>'+rebaseIntro+'</strong>La stima CHF basata sui rendimenti EUR 2Y/10Y è stata '+
  'ricalcolata sullo storico BCE omogeneo. Una differenza rispetto alla versione precedente '+
  'è una <strong>revisione dello scenario β</strong>, non un movimento osservato oggi sui '+
  'titoli svizzeri. Affidabilità BASSA; tasso CHF ufficiale e data restano separati.</div>':'';

 const host=doc.createElement('section');
 host.id='gmfq-yields-study';host.className='desk-panel';
 host.dataset.coverage=String(out.covered);host.dataset.recent=String(out.recent);
 host.dataset.scenarioCount=String(out.scenarios);
 host.dataset.coreEffect='NONE';host.dataset.pairEffect='NONE';
 host.dataset.nzdWebReview=nzWeb?'RESEARCH_UNAPPROVED':'UNAVAILABLE';
 host.dataset.eurSourceRebase=rebaseStatus||'NONE';
 host.setAttribute('aria-label','Rendimenti G8 2 e 10 anni osservati e scenari separati');
 const css=doc.createElement('style');css.id='gmfq-yields-study-style';
 css.textContent=
  '#gmfq-yields-study{margin:0 0 13px;min-width:0}'+
  '#gmfq-yields-study .gmfq-yields-intro,#gmfq-yields-study .gmfq-yields-note{padding:0 15px;color:#a8becd;font:11px/1.6 Arial,sans-serif;margin:10px 0}'+
  '#gmfq-yields-study .gmfq-yields-count{color:#e6c98d;font:600 12px/1.6 Arial,sans-serif;padding:10px 15px 0}'+
  '#gmfq-yields-study .gmfq-yields-grid{padding:0 15px 13px}'+
  '#gmfq-yields-study .gmfq-yield-row{display:grid;grid-template-columns:minmax(90px,1.25fr) minmax(70px,1fr) minmax(70px,1fr);gap:4px 9px;align-items:center;padding:9px 2px;border-top:1px solid #294455;min-width:0}'+
  '#gmfq-yields-study .gmfq-yield-row strong{font:600 13px/1.5 Arial,sans-serif;color:#e9f0f5;font-variant-numeric:tabular-nums}'+
  '#gmfq-yields-study .gmfq-yield-row small{display:block;font:10px/1.4 Arial,sans-serif;color:#9ab4c6}'+
  '#gmfq-yields-study .gmfq-yield-row .gmfq-yield-meta,#gmfq-yields-study .gmfq-yield-row .gmfq-yield-scenario{grid-column:1/-1;color:#a9c2d2;font:10px/1.5 Arial,sans-serif;overflow-wrap:anywhere}'+
  '#gmfq-yields-study .gmfq-yield-row .gmfq-yield-scenario{color:#dfc78b}'+
  '#gmfq-yields-study .gmfq-yield-rebase{grid-column:1/-1;font:11px/1.55 Arial,sans-serif;color:#e6ca90;padding:9px 10px;border-left:2px solid #af9255;background:rgba(175,146,85,.075);overflow-wrap:anywhere}'+
  '#gmfq-yields-study .gmfq-yield-row .gmfq-yield-web-candidate{grid-column:1/-1;font:11px/1.6 Arial,sans-serif;color:#e8cb92;margin:3px 0;overflow-wrap:anywhere}'+
  '#gmfq-yields-study .gmfq-yield-web-candidate a{color:#ebd49f;text-decoration:underline}'+
  '#gmfq-yields-study .gmfq-yield-market{grid-column:1/-1;font:11px/1.6 Arial,sans-serif;color:#b7d8eb;border-left:2px solid #5380a5;padding:4px 8px;overflow-wrap:anywhere}'+
  '#gmfq-yields-study .gmfq-yield-market[data-quality="STALE"]{color:#d9c18b;border-color:#b19561}'+
  '#gmfq-yields-study .gmfq-yield-market a{color:inherit;text-decoration:underline}'+
  '#gmfq-yields-study .gmfq-yield-row[data-state="HISTORICAL"]>div:first-child small{color:#e0c486}'+
  '#gmfq-yields-study .gmfq-yield-head{color:#a9c1d0;font:600 11px/1.6 Arial,sans-serif}'+
  '@media(max-width:520px){#gmfq-yields-study .gmfq-yields-grid{padding:0 9px 10px}'+
  '#gmfq-yields-study .gmfq-yield-row{grid-template-columns:minmax(68px,1.05fr) repeat(2,minmax(65px,1fr));gap:3px 5px}'+
  '#gmfq-yields-study .gmfq-yield-row strong{font-size:12px}'+
  '#gmfq-yields-study .gmfq-yields-intro,#gmfq-yields-study .gmfq-yields-note{padding:0 9px}'+
  '#gmfq-yields-study .gmfq-yields-count{padding:8px 9px 0}}';
 doc.head.appendChild(css);
 const elements=out.rows.map(x=>{
  const market=secondary2YReading(secondary2y,rates,x.ccy);
  const percent=n=>num(n)===null?'—':fmt(n,3)+'%';
  const label=x.status==='RECENT'?'osservazione recente':
    x.status==='HISTORICAL'?'ultima osservazione storica':'non verificabile';
  return '<div class="gmfq-yield-row" data-ccy="'+x.ccy+'" data-state="'+x.status+
   '" data-asof="'+htmlEscape(x.asof||'')+'" data-scenario="'+(x.scenario?'true':'false')+'">'+
   '<div><strong>'+FLAG[x.ccy]+' '+x.ccy+'</strong><small>'+label+'</small></div>'+
   '<div><strong>'+percent(x.v2)+'</strong></div><div><strong>'+percent(x.v10)+'</strong></div>'+
   '<div class="gmfq-yield-meta">Fonte governativa · '+htmlEscape(x.asof||'n.d.')+
   (x.slopeBp!==null?' · 10Y−2Y '+(x.slopeBp>=0?'+':'')+fmt(x.slopeBp,1)+' bp (stessa data)':'')+'</div>'+
   (market?'<div class="gmfq-yield-market" data-quality="'+(market.stale?'STALE':'RECENT')+
     '" data-date="'+htmlEscape(market.date)+'" data-tier="SECONDARY_OBSERVED_NOT_OFFICIAL">'+
     '<b>2Y mercato · '+percent(market.value)+'</b> · '+htmlEscape(market.date)+
     (market.stale?' · STORICO, non aggiornato':' · recente')+
     ' · dispersione fonti '+percent(market.min)+'–'+percent(market.max)+
     ' ('+market.sourceCount+' quotazioni). <strong>NON ufficiale</strong>, non confrontare con il 10Y SNB/RBNZ e non usare per spread FX. '+
     market.sources.map(x=>'<a href="'+htmlEscape(x.url)+'" target="_blank" rel="noopener noreferrer">'+htmlEscape(x.name)+'</a>').join(' · ')+
     '</div>':'')+
   (x.ccy==='NZD'&&nzWeb?'<div class="gmfq-yield-web-candidate" data-nzd-web-review="RESEARCH_UNAPPROVED">'+
     'RBNZ B2 · '+htmlEscape(nzWeb.date)+(nzWeb.historical?' · dato storico':' · dato recente')+
     ' · 2Y '+percent(nzWeb.v2)+' · 10Y '+percent(nzWeb.v10)+
     ' · 10Y−2Y +'+fmt(nzWeb.slopeBp,1)+' bp. Doppia lettura HTML, '+
     '<strong>NON APPROVATO</strong> (XLSX e revisore mancanti). Solo studio, non motore né spread FX. '+
     '<a href="'+htmlEscape(nzWeb.source)+'" target="_blank" rel="noopener noreferrer">Fonte RBNZ ↗</a></div>':'')+
   (x.scenario?'<div class="gmfq-yield-scenario">Scenario β informativo '+FLAG[x.scenario.proxy]+
    ' '+x.scenario.proxy+' · '+x.scenario.date+' · 2Y ≈'+percent(x.scenario.v2)+
    ' ('+x.scenario.confidence2+') · 10Y ≈'+percent(x.scenario.v10)+
    ' ('+x.scenario.confidence10+'). Non è un nuovo spread osservato.</div>':'')+
   (x.ccy==='CHF'&&x.scenario?.proxy==='EUR'?rebaseNotice:'')+'</div>';
 }).join('');
 const chf=snb?.schema==='GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1'&&
  snb.status==='OFFICIAL_PUBLISHED_10Y_INFORMATIONAL'&&snb.currency==='CHF'&&
  snb.tenor==='10Y'&&snb.yield_type==='SWISS_CONFEDERATION_ZERO_COUPON_SPOT'&&
  snb.has_current_2y===false&&snb.eligible_for_curve_spreads===false&&
  snb.eligible_for_core_signals===false&&snb.eligible_for_backtests===false&&
  snb.ois_or_saron===false&&num(snb.value_percent)!==null&&
  snb.value_percent>-5&&snb.value_percent<25&&
  Number.isInteger(romeCalendarAge(snb.as_of))&&romeCalendarAge(snb.as_of)>=0&&
  romeCalendarAge(snb.as_of)<=4;
 host.innerHTML='<h2 class="desk-panel-title">Governativi G8 · livelli 2Y e 10Y</h2>'+
  '<div class="gmfq-yields-count">'+out.covered+'/8 coppie di rendimenti verificabili · '+out.recent+
  ' recenti · '+(out.covered-out.recent)+' storiche · '+out.scenarios+' scenari β separati</div>'+
  '<p class="gmfq-yields-intro">Tasso 2Y = breve periodo; 10Y = componente lunga. La pendenza confronta due rendimenti della stessa valuta e data, non strumenti monetari OIS.</p>'+
  '<div class="gmfq-yields-grid"><div class="gmfq-yield-row gmfq-yield-head" aria-hidden="true">'+
  '<div>Valuta</div><div>2Y</div><div>10Y</div></div>'+elements+'</div>'+
  (chf?'<p class="gmfq-yields-note" data-snb-10y="SEPARATE">🇨🇭 CHF: SNB Confederazione 10Y spot '+fmt(snb.value_percent,3)+'% · '+
     htmlEscape(snb.as_of)+'. Fonte e strumento separati dalla coppia 2Y/10Y storica: non calcolare spread misti.</p>':'')+
  '<p class="gmfq-yields-note">Stato e date non si trasferiscono tra paesi. Gli scenari β sono modelli illustrativi con R² diversi, non prezzi ufficiali, intervalli di confidenza o segnali. Prezzi e score delle 28 coppie restano invariati.</p>';
 anchor.insertAdjacentElement('beforebegin',host);
}

/* Rates research overlay: observed validated curves are distinct from unsynchronised futures quotes.
   Display-only: no policy path can be inferred from secondary contract observations. */
function marketResearchCurves(data){
 const terms=['3m','6m','12m'];
 // Only source-certified, CURRENT official rows may enter the chart.
 // Never hard-code today's four active currency codes: a fifth approved
 // source must appear without enabling any proxy or inferred policy path.
 return FX.flatMap(k=>{
  const x=data?.currencies?.[k];
  if(!officialPricingCurrent(x))return [];
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

function marketResearchGraded(ois,proxy){
 const make=window.GMFQ_OIS_RESEARCH_V1?.matrix;
 if(typeof make!=='function')return [];
 return make(ois,proxy,romeTodayIso()).filter(r=>
  FX.includes(r.ccy)&&['OFFICIAL','PROXY','MIXED','SCENARIO'].includes(r.tier)&&
  ['3m','6m','12m'].every(t=>num(r.points?.[t]?.value)!==null&&fresh(r.points[t].date,5)))
 .map(r=>({k:r.ccy,tier:r.tier,pts:['3m','6m','12m'].map(t=>r.points[t].value),
  dates:['3m','6m','12m'].map(t=>r.points[t].date),
  joined:new Set(['3m','6m','12m'].map(t=>r.points[t].date)).size===1}));
}
/* Do not join secondary futures with different quote dates or imply OIS policy deltas. */
function marketResearchGradedSvg(curves){
 if(!curves.length)return '<p style="padding:18px">Riferimenti 3M/6M/12M non disponibili con date verificabili.</p>';
 const values=curves.flatMap(c=>c.pts),lo=Math.floor((Math.min(...values)-.25)*2)/2,
  hi=Math.ceil((Math.max(...values)+.25)*2)/2,span=hi-lo||1;
 const xx=[94,350,616],yy=v=>25+170*(hi-v)/span;
 let svg='<g data-graded-axis="PERCENT">';
 for(let i=0;i<=4;i++){
  let v=lo+i*span/4,y=yy(v);
  svg+='<line x1="59" x2="682" y1="'+y+'" y2="'+y+
   '" stroke="#28495b"/><text x="50" y="'+(y+4)+'" font-size="12" fill="#a9c3d3" text-anchor="end">'+fmt(v,1)+'%</text>';
 }
 ['3M','6M','12M'].forEach((t,i)=>svg+='<text x="'+xx[i]+'" y="225" fill="#afc6d6" font-size="13" text-anchor="middle">'+t+'</text>');
 svg+='</g>';
 for(const c of curves){
  svg+='<g data-graded-ccy="'+c.k+'" data-quality="'+c.tier+'" data-joined="'+c.joined+'">';
  if(c.joined)svg+='<polyline fill="none" stroke="'+COLOR[c.k]+'" stroke-width="3"'+
    (c.tier==='OFFICIAL'?'':' stroke-dasharray="5 5"')+' points="'+
    c.pts.map((v,i)=>xx[i]+','+yy(v).toFixed(1)).join(' ')+'"/>';
  c.pts.forEach((v,i)=>svg+='<circle cx="'+xx[i]+'" cy="'+yy(v).toFixed(1)+
    '" r="5" fill="'+COLOR[c.k]+'"><title>'+c.k+' '+['3M','6M','12M'][i]+
    ' '+fmt(v,3)+'% · '+c.dates[i]+' · '+c.tier+'</title></circle>');
  svg+='</g>';
 }
 svg+='<text x="682" y="13" font-size="11" text-anchor="end" fill="#a8bdcb">Livello monetario · %</text>';
 return '<svg data-chart="G8_SOURCE_GRADED_LEVELS" data-currencies="'+curves.length+
  '" viewBox="0 0 720 240" role="img" aria-label="'+curves.length+
  ' valute G8, livelli 3M 6M 12M, fonte qualificata">'+svg+'</svg>';
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
 // A dossier documents an unresolved source-access decision, NOT an official
 // currency list. Reconcile pending G8 lanes with the audited registry and
 // hide a dossier only after the separately certified runtime is active.
 const ids=FX.filter(c=>['WITHHELD','GREEN_ESTIMATED'].includes(
   operational?.currencies?.[c]?.operational_status));
 const knownStatuses=FX.every(c=>['GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD']
   .includes(operational?.currencies?.[c]?.operational_status));
 const registryKeys=Object.keys(view?.currencies||{});
 const statusOk=knownStatuses&&view?.schema==='GMFQ_OIS_SOURCE_READINESS_VIEW_V1'&&
  view.status==='READ_ONLY_SOURCE_READINESS'&&fresh(view.as_of,3)&&
  view.prices_omitted===true&&view.no_automatic_promotions===true&&
  view.no_core_score_effect===true&&view.no_bias_effect===true&&
  view.no_sizing_effect===true&&view.no_backtest_effect===true&&
  registryKeys.length===ids.length&&registryKeys.every(k=>ids.includes(k))&&
  ids.every(k=>['WITHHELD','GREEN_ESTIMATED'].includes(view.currencies?.[k]?.status)&&
   view.currencies[k].status===operational?.currencies?.[k]?.operational_status&&
   view.currencies[k].usable_for_policy_pricing===false&&
   view.currencies[k].backtest_eligible_as_official===false&&
   typeof view.currencies[k].obstacle==='string'&&
   typeof view.currencies[k].activation_requirement==='string')&&
  view.blocked_currency_count===ids.filter(k=>view.currencies?.[k]?.status==='WITHHELD').length;
 const opening='<details class="gmfq-source-readiness" id="gmfq-source-readiness"><summary>Fonti da sbloccare · situazione e prossimi passi</summary>';
 if(!statusOk)return opening+'<p class="gmfq-research-note">Stato delle fonti da aggiornare: nessuna curva aggiuntiva viene certificata.</p></details>';
 const items=ids.map(k=>{
  const v=view.currencies[k],link=v.source_url;
  const validUrl=typeof link==='string'&&/^https:\/\/(www\.)?(cmegroup\.com|eurex\.com|ice\.com|nzfbf\.co\.nz)\//.test(link);
  const anchor=validUrl?'<a href="'+htmlEscape(link)+'" target="_blank" rel="noopener noreferrer">Fonte originale ↗</a>':'Fonte da verificare';
  const live=operational.currencies[k].operational_status;
  const state=live==='GREEN_OFFICIAL'?'CERTIFICATA · fonte operativa':
   live==='GREEN_ESTIMATED'?'SOLO INDICATIVA · non certificata':'WITHHELD · non certificata';
  return '<div class="gmfq-source-row" data-source-ccy="'+k+'"><div><b>'+FLAG[k]+' '+k+' · '+htmlEscape(state)+'</b>'+
   '<p>'+htmlEscape(v.obstacle)+'</p><small>Requisito per accesso ai dati ufficiali: '+htmlEscape(v.activation_requirement)+'</small></div>'+
   '<div class="gmfq-source-link">'+anchor+'</div></div>';
 }).join('');
 const chf=view.currencies.CHF?.government_rates;
 const swiss=chf?.has_new_verified_2y===false&&chf.cross_date_spread_allowed===false?
  '<p class="gmfq-research-note">🇨🇭 CHF governativi: l’ultima coppia 2Y/10Y omogenea nel feed è del '+
   htmlEscape(chf.last_paired_2y10y_as_of||'—')+
   '. Il 10Y SNB pubblicato separatamente non completa il 2Y e non permette uno spread aggiornato.</p>':'';
 return opening+'<p class="gmfq-research-note">'+(ids.length?ids.length+' dossier di accesso a fonti ufficiali ancora da sbloccare. ':'Nessuna fonte aggiuntiva da sbloccare. ')+'Il loro stato di accesso può essere precedente al runtime operativo: le quotazioni GREEN_ESTIMATED restano indicative, mai OIS ufficiali. Nessun dato indicativo è promosso a OIS o usato nei segnali. Revisione fonti: '+
  htmlEscape(view.source_reviewed_as_of)+'.</p>'+items+swiss+'</details>';
}

function mountMarketResearch(doc,ois,proxy,rates,snb10,sourceReadiness){
 if(route()!=='tassi'||frame.contentDocument!==doc)return;
 const table=doc.getElementById('ois-rows'),original=table?.closest('.desk-panel');
 if(!original||doc.getElementById('gmfq-pricing-research'))return;
 const style=doc.createElement('style');style.id='gmfq-pricing-research-style';
 style.textContent='#gmfq-pricing-research{margin-top:12px}#gmfq-pricing-research .gmfq-research-intro,#gmfq-pricing-research .gmfq-research-note{color:#a9c1d2;font-size:12px;line-height:1.55;margin:9px 0 14px}#gmfq-pricing-research h3{font-size:13px;color:#e5edf5;margin:0 0 10px}#gmfq-pricing-research .gmfq-research-plot{height:225px;max-width:100%;border:1px solid #284456;border-radius:7px;background:#0b2030;overflow:hidden}#gmfq-pricing-research svg{height:100%;width:100%;display:block}#gmfq-pricing-research .gmfq-research-tabs,#gmfq-pricing-research .gmfq-research-legend{display:flex;flex-wrap:wrap;gap:7px 13px;margin:9px 0}#gmfq-pricing-research button{cursor:pointer;background:#122c40;border:1px solid #34546b;padding:6px 12px;border-radius:5px;color:#c0d0e0;font:12px Arial,sans-serif}#gmfq-pricing-research button[aria-pressed=true]{background:#e2c87c;border-color:#e2c87c;color:#102132}#gmfq-pricing-research button:focus-visible{outline:2px solid #f7dfa0}#gmfq-pricing-research .gmfq-research-legend span{font-size:11px;color:#b4c9d8}#gmfq-pricing-research .gmfq-research-legend i{display:inline-block;width:13px;height:3px;margin-right:5px;vertical-align:middle}#gmfq-pricing-research .gmfq-research-separator{border-top:1px solid #294556;margin-top:18px;padding-top:16px}#gmfq-pricing-research .gmfq-pricing-core-status{margin:8px 0 7px;padding:8px 0 9px;border-bottom:1px solid #2c4759;color:#d8c895;font:600 12px/1.5 Arial,sans-serif;overflow-wrap:anywhere}#gmfq-pricing-research .gmfq-pricing-core-explanation{color:#aabfce;font:11px/1.6 Arial,sans-serif;margin:0 0 12px}#gmfq-pricing-research #gmfq-pricing-evidence-details{border-top:1px solid #2d4858;margin-top:15px;padding-top:10px;min-width:0}#gmfq-pricing-research #gmfq-pricing-evidence-details>summary{cursor:pointer;color:#e3cb93;font:600 12px/1.55 Arial,sans-serif;outline-offset:4px;padding:6px 1px;overflow-wrap:anywhere}#gmfq-pricing-research #gmfq-pricing-evidence-details:not([open])>:not(summary){display:none!important}#gmfq-pricing-research .gmfq-quote-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:9px}#gmfq-pricing-research .gmfq-quote-card{background:#0b2232;border:1px solid #294659;border-radius:6px;padding:11px}#gmfq-pricing-research .gmfq-snb-spot{border:1px solid #315267;background:#0d2637;border-radius:7px;padding:12px 14px;margin:10px 0 12px;color:#aec6d7;font-size:12px;line-height:1.65}#gmfq-pricing-research .gmfq-snb-spot strong{color:#e6f1f8;font-size:20px;font-variant-numeric:tabular-nums}#gmfq-pricing-research .gmfq-snb-spot a{color:#e8cb8b;text-decoration:underline}#gmfq-pricing-research .gmfq-quote-card b{display:block;color:#f0d091;font-size:12px;margin-bottom:8px}#gmfq-pricing-research .gmfq-quote{color:#b6c9d8;font-size:11px;line-height:1.7}#gmfq-pricing-research .gmfq-quote strong{color:#e5eff5}#gmfq-pricing-research .gmfq-source-readiness{border-top:1px solid #294556;margin-top:18px;padding-top:14px}#gmfq-pricing-research .gmfq-source-readiness summary{font-size:13px;font-weight:700;color:#e9d192;cursor:pointer;outline-offset:4px}#gmfq-pricing-research .gmfq-source-row{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid #203c4d}#gmfq-pricing-research .gmfq-source-row b{font-size:12px;color:#dbe9f3}#gmfq-pricing-research .gmfq-source-row p{font-size:12px;color:#adbfcd;margin:5px 0}#gmfq-pricing-research .gmfq-source-row small{display:block;color:#c4d3dd;line-height:1.45;font-size:11px}#gmfq-pricing-research .gmfq-source-link{flex:0 0 auto;font-size:11px}#gmfq-pricing-research .gmfq-source-link a{color:#e6c57f;text-decoration:underline}@media(max-width:600px){#gmfq-pricing-research .gmfq-source-row{display:block}#gmfq-pricing-research .gmfq-source-link{margin-top:7px}}@media(max-width:600px){#gmfq-pricing-research .gmfq-research-plot{height:190px}#gmfq-pricing-research .gmfq-quote-cards{grid-template-columns:1fr}}';
 doc.head.appendChild(style);
 const curves=marketResearchCurves(ois),graded=marketResearchGraded(ois,proxy),host=doc.createElement('section');
 const classes=['GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD'];
 const statusesComplete=ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
  FX.every(c=>classes.includes(ois.currencies?.[c]?.operational_status));
 const estimated=statusesComplete?FX.filter(c=>ois.currencies[c].operational_status==='GREEN_ESTIMATED'):[];
 const withheld=statusesComplete?FX.filter(c=>ois.currencies[c].operational_status==='WITHHELD'):[];
 const officialEligible=statusesComplete?FX.filter(c=>{
  const r=ois.currencies[c];
  return officialPricingCurrent(r);
 }):[];
 const curvesVerified=statusesComplete&&curves.length===officialEligible.length&&
  curves.every(c=>officialEligible.includes(c.k));
 host.id='gmfq-pricing-research';host.className='desk-panel';
 host.dataset.sourceStatus=curvesVerified?'READ_ONLY':'WITHHELD';
 host.dataset.verifiedCurves=curvesVerified?String(curves.length):'';
  host.dataset.g8Levels=String(graded.length);
 host.dataset.estimatedLanes=curvesVerified?String(estimated.length):'';
 host.dataset.withheldLanes=curvesVerified?String(withheld.length):'';
 const headline=curvesVerified?
   'Grafico G8 3M/6M/12M: '+graded.length+'/8 valute con riferimenti datati. Curve certificate: '+curves.length+'/8 · '+curves.map(c=>FLAG[c.k]+' '+c.k).join(', ')+'.':
   'Copertura OIS/futures non verificabile: nessuna conclusione sul pricing.';
 host.innerHTML='<h2 class="desk-panel-title">Market Pricing · curve comparate e affidabilità</h2>'+
  '<div class="desk-panel-body"><p class="gmfq-pricing-core-status">'+htmlEscape(headline)+'</p>'+
  '<p class="gmfq-pricing-core-explanation">GBP: OIS BoE; JPY, AUD e CAD: futures monetari. Certificazione della fonte ≠ OIS puro. '+
   (curvesVerified?'Il quadro completo G8 con fonti certificate, futures indicativi e scenari è riportato nella tabella principale sopra. '+(estimated.length+withheld.length)+' valute senza OIS/futures certificati: usare le stime con i rispettivi limiti. ':'Riconciliazione delle fonti incompleta. ')+
   'I rendimenti governativi 2Y/10Y sono un layer distinto e non dimostrano da soli il percorso dei tassi.</p>'+
  '<p class="gmfq-research-intro">Cosa sta prezzando il mercato su 3, 6 e 12 mesi? Il grafico mostra livelli monetari 3M, 6M e 12M in %, con qualità separata. Non sono Δ policy rate né probabilità per meeting.</p>'+
  '<div class="gmfq-research-tabs" role="group" aria-label="Filtra riferimenti monetari G8"></div>'+
  '<div class="gmfq-research-plot"></div><div class="gmfq-research-legend"></div>'+
  '<p class="gmfq-research-note">Le curve sintetizzano prezzi per scadenza, non un percorso certo della banca centrale. Linea piena: certificata; tratteggio: stima/scenario; punti isolati: date diverse, non collegate. Senza Δ policy, segnali FX o OIS sintetici. Strumenti, date e limiti delle fonti restano consultabili nell’analisi completa.</p>'+
  '<details id="gmfq-pricing-evidence-details"><summary>Apri analisi completa · fonti, proxy e casi incompleti</summary>'+
  marketResearchSecondary(ois)+'<div class="gmfq-research-separator"><h3>Fonti incomplete</h3>'+
  '<div class="gmfq-snb-spot" id="gmfq-chf-snb-10y-context" role="note"></div>'+
  '<p class="gmfq-research-note" id="gmfq-nzd-pricing-context"></p>'+
  '<p class="gmfq-research-note" id="gmfq-chf-rates-context"></p></div>'+marketSourceReadinessHtml(sourceReadiness,ois)+'</details></div>';
 original.insertAdjacentElement('afterend',host);
 const labels=[['ALL','Tutte'],...graded.map(c=>[c.k,FLAG[c.k]+' '+c.k])];
 const tabs=host.querySelector('.gmfq-research-tabs'),plot=host.querySelector('.gmfq-research-plot'),legend=host.querySelector('.gmfq-research-legend');
 let selected='ALL';
 for(const [key,value] of labels){
  const b=doc.createElement('button');b.type='button';b.dataset.pricingCcy=key;b.textContent=value;tabs.appendChild(b);
 }
 const draw=()=>{
  const shown=selected==='ALL'?graded:graded.filter(x=>x.k===selected);
   plot.innerHTML=marketResearchGradedSvg(shown);
   legend.innerHTML=shown.map(c=>'<span title="'+htmlEscape(c.dates.join(' / '))+'"><i style="background:'+COLOR[c.k]+'"></i>'+FLAG[c.k]+' '+c.k+' · '+c.tier+' · '+htmlEscape([...new Set(c.dates)].join(' / '))+'</span>').join('');
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
 const all=await Promise.allSettled([feed('OIS_OPERATIONAL_VIEW.json'),feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),feed('NATIVE_RATES_DATA.json'),feed('CHF_SNB_10Y_SPOT_CONTEXT.json'),feed('OIS_SOURCE_READINESS_VIEW.json'),feed('NZD_B2_GOVT_WEB_REVIEW_CONTEXT.json'),fetchSecondary2Y()]);
 const feeds=all.map(x=>x.status==='fulfilled'?x.value:null);
 renderYieldStudy(doc,feeds[2],feeds[3],feeds[5],feeds[6]);
 mountHistoricalSovereignTable(doc,feeds[2]);
  mountSovereignHistoryPlot(doc,feeds[2]);
 mountMarketResearch(doc,...feeds.slice(0,5));
}

/* Pair research journey, added next to (not replacing) the original 28-pair
   deep dive. Source as-of != today's ECB fixing. No derived trade signals. */
/* Research-only Macro/2Y/10Y/6M comparator.
   Structural Macro/Policy sides come ONLY from the 28-pair canonical model,
   independently dated sovereign yields ONLY from official native Rates.
   Never derive a curve/spread from mismatched or stale dates. */
/* The single verified historical-model gate across all Pair interpretations.
   D.json certification is checked by the caller through
   canonicalPairMacroBaseline(). This guard also rejects malformed, future or
   Price-inconsistent dates. A historical but certified model stays visible
   WITH its historic label; an unverified one cannot give a favored side. */
function pairModelEvidenceState(macroDay,priceDay){
 const age=romeCalendarAge(macroDay);
 const priceAge=romeCalendarAge(priceDay);
 const verified=age!==null&&age>=0&&priceAge!==null&&priceAge>=0&&
   macroDay<=priceDay;
 return {verified,current:verified&&age<=10,historical:verified&&age>10};
}
function pairMacroRatesComparison(code,pair,rates,ois,modelDay,macroDay,proxy){
 const a=code.slice(0,3),b=code.slice(3,6),s=pair?.decision_frame||{};
 const modelState=pairModelEvidenceState(macroDay,modelDay);
 const safeSide=(v)=>modelState.verified&&(v===a||v===b)?v:null;
 const macroSide=safeSide(s.macroSide),policySide=safeSide(s.policySide);
 // Reuse the exact futures date/price/provenance guard from Rates research.
 // This does NOT change the official 6M monetary-policy delta.
 let indicative6m={};
 if(ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
    typeof window.GMFQ_OIS_RESEARCH_V1?.indicativeSixMonth==='function'){
   try{
     indicative6m=window.GMFQ_OIS_RESEARCH_V1.indicativeSixMonth(
       ois,romeTodayIso())||{};
   }catch(e){console.warn('[GMFQ Pair indicative 6M unavailable]',String(e))}
 }
 let scenario6m={};
 if(ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
    typeof window.GMFQ_OIS_RESEARCH_V1?.scenarioSixMonth==='function'){
  try{scenario6m=window.GMFQ_OIS_RESEARCH_V1.scenarioSixMonth(ois,proxy,romeTodayIso())||{};}
  catch(e){console.warn('[GMFQ Pair NZD scenario unavailable]',String(e))}
 }
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
   const ok=officialPricingCurrent(o);
   const instrument=c==='GBP'?'OIS BoE':c==='JPY'?'futures TONA':
    c==='AUD'?'futures IB':c==='CAD'?'futures CORRA':'strumento non certificato';
   return {ok, date:o?.as_of||null,delta:ok?o.horizons['6m'].policy_delta_bp:null,instrument};
 };
 const leg=(c)=>{
  const r=sovereign(c),p=repricing(c);
  const ratesLine=r.certified?
   '2Y '+fmt(r.y2,2)+'% · 10Y '+fmt(r.y10,2)+'% · '+r.date:
   '2Y / 10Y WITHHELD · ultima data '+(r.date||'non verificata');
  const context=!p.ok?indicative6m[c]:null;
  const contextValid=context&&context.currency===c&&
   ['USD','EUR','CHF'].includes(c)&&['PROXY','MIXED'].includes(context.type)&&
   context.is_official_ois===false&&context.policy_delta_allowed===false&&
   context.pair_effect==='NONE'&&context.core_effect==='NONE'&&
   num(context.value)!==null&&fresh(context.quote_as_of,5);
  const sc=!p.ok&&c==='NZD'?scenario6m.NZD:null;
  const scValid=sc&&sc.currency==='NZD'&&sc.type==='SCENARIO'&&
   sc.is_official_ois===false&&sc.policy_delta_allowed===false&&
   sc.pair_effect==='NONE'&&sc.core_effect==='NONE'&&
   sc.backtest_eligible_as_official===false&&
   Array.isArray(sc.range)&&sc.range.length===2&&
   num(sc.value)!==null&&num(sc.range[0])!==null&&num(sc.range[1])!==null&&
   sc.range[0]<sc.value&&sc.value<sc.range[1]&&fresh(sc.quote_as_of,5);
  const fwd=p.ok?('6M '+(p.delta>0?'+':'')+fmt(p.delta,1)+' bp · '+p.instrument+
   ' · '+p.date):contextValid?
   '6M repricing policy non certificato · '+context.label+
     ' ≈ '+fmt(context.value,3)+'% · '+context.contract+
     ' · '+context.quote_as_of+' · NON ΔOIS, solo contesto':scValid?
   '6M scenario empirico ≈'+fmt(sc.value,2)+'% · fascia '+
   fmt(sc.range[0],2)+'–'+fmt(sc.range[1],2)+'% · Bank Bill 90gg con basis RBNZ · '+
   sc.quote_as_of+' · NON ΔOIS, solo contesto':
   '6M pricing WITHHELD · '+(p.date||'non verificato');
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
 const verdict=!modelState.verified?
  'Baseline Macro/Tassi non verificata: preferenza e convergenza strutturale WITHHELD. I rendimenti ufficiali restano osservazioni separate.':
  macroSide&&policySide&&macroSide===policySide?
  'Macro e Tassi/banche centrali favoriscono la stessa valuta nel modello.':
  macroSide&&policySide&&macroSide!==policySide?
   'Macro e Tassi/banche centrali favoriscono valute opposte: nessun allineamento completo.':
   macroSide||policySide?
    'Solo un pilastro distingue le valute: vantaggio strutturale parziale, non un ingresso.':
    'Nessun vantaggio convergente dimostrato dai due pilastri nel modello.';
 const watch=!modelState.verified?
  'Prima verificare la provenienza della baseline Macro/Tassi, senza inferire una tesi dai soli rendimenti.':
  modelState.historical?
   'Baseline strutturale storica, da rivalidare. '+(typeof s.watch==='string'?s.watch:'Nessuna condizione verificata.'):
   typeof s.watch==='string'?s.watch:'Non ci sono condizioni sufficienti per una lettura operativa.';
 const modelSideText=v=>modelState.verified?sideText(v):'WITHHELD · modello non verificato';
 const modelStamp=(macroDay&&modelState.verified?macroDay+' · '+(modelState.historical?'STORICA':'SNAPSHOT DATATO'):'non verificata');
 return '<section class="gmfq-compare" id="gmfq-pair-macro-rates" data-model-evidence="'+
   (modelState.verified?modelState.historical?'HISTORICAL':'CURRENT':'WITHHELD')+
   '" aria-label="Confronto Macro Rates delle due valute">'+
  '<h3>Macro e Rates · confronto '+FLAG[a]+' '+a+' / '+FLAG[b]+' '+b+'</h3>'+
  '<div class="gmfq-compare-score"><div><span>MACRO · baseline '+htmlEscape(modelStamp)+'</span>'+
    '<strong>'+htmlEscape(modelSideText(macroSide))+'</strong></div>'+
    '<div><span>TASSI / BANCHE CENTRALI · baseline '+htmlEscape(modelStamp)+'</span>'+
    '<strong>'+htmlEscape(modelSideText(policySide))+'</strong></div></div>'+
  '<p class="gmfq-compare-explain">'+htmlEscape(verdict)+'</p>'+
  '<div class="gmfq-compare-legs">'+leg(a)+leg(b)+'</div>'+
  '<p class="gmfq-compare-spread" data-same-date="'+(same?'true':'false')+'">'+htmlEscape(spreadMsg)+'</p>'+
  '<p class="gmfq-compare-note"><strong>Cosa controllare:</strong> '+htmlEscape(watch)+'</p>'+
  '<p class="gmfq-compare-disclaimer">I giudizi Macro e Tassi/CB sono quelli dello snapshot del motore, non vengono ricalcolati con i rendimenti mostrati. Il 6M descrive strumenti OIS/futures differenti: non sottrarre i loro delta e non trasformarli in previsioni di cambio.</p></section>';
}

/* What Changed = separate historical, measured yield change from the dated,
   qualitative canonical model diagnosis. An absent/mismatched interval is NOT
   a 1D, 1W or inferred live CB repricing. Read-only, no model reconstruction. */
function pairWhatChangedEvidence(code,pair,rates,modelDay,macroDay){
 const a=code.slice(0,3),b=code.slice(3,6),dynamic=pair?.relative_dynamics;
 // The model's qualitative Growth/Labour/Rates diagnosis comes from D.json
 // (macro baseline), NOT the newer ECB price overlay in the Pair export.
 // Caller passes only the verified D.json/Pair metadata matched baseline;
 // a missing/future/mismatched baseline must NEVER inherit the price date.
 const baselineAge=romeCalendarAge(macroDay);
 const baselineVerified=baselineAge!==null&&baselineAge>=0&&
  typeof modelDay==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(modelDay)&&
  macroDay<=modelDay;
 const baselineCurrent=baselineVerified&&baselineAge<=10;
 const modelValid=baselineVerified&&!!dynamic&&dynamic.a===a&&dynamic.b===b&&
  dynamic.A?.withheld===false&&dynamic.B?.withheld===false&&
  Array.isArray(dynamic.A.details)&&Array.isArray(dynamic.B.details);
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
    '<span>LETTURA MODELLO · BASELINE MACRO/TASSI '+htmlEscape(baselineVerified?macroDay:'NON VERIFICATA')+
    (baselineVerified?(baselineCurrent?' · SNAPSHOT DATATO':' · STORICA, DA RIVALIDARE'):' · WITHHELD')+'</span>'+
    modelLeg(c,key)+
    '<span>VARIAZIONE 2Y · DATI OSSERVATI</span><p class="gmfq-change-measured">'+
    htmlEscape(ob.text)+'</p></div>';
 };
 const phase=modelValid&&typeof pair?.transition?.state==='string'?
  htmlEscape(pair.transition.state):'Dinamica del motore non verificata';
 return '<section class="gmfq-what-changed" id="gmfq-pair-what-changed" data-macro-baseline-as-of="'+htmlEscape(baselineVerified?macroDay:'')+
  '" data-pair-price-as-of="'+htmlEscape(modelDay||'')+
  '" data-macro-baseline-state="'+(baselineCurrent?'DATED_SNAPSHOT':baselineVerified?'HISTORICAL':'WITHHELD')+
  '" aria-label="Cosa sta cambiando, modello contro fatti osservati">'+
  '<h3>Cosa sta cambiando · modello vs dati</h3>'+
  '<p>La lettura Crescita/Lavoro/Rates usa la baseline Macro/Tassi del '+htmlEscape(baselineVerified?macroDay:'periodo non verificato')+
  (baselineCurrent?' (snapshot datato).':baselineVerified?' (STORICA, da rivalidare).':' (WITHHELD).')+
  ' Il feed Prezzo/Pair del '+htmlEscape(modelDay||'periodo non verificato')+
  ' non aggiorna automaticamente quelle dinamiche. Il 2Y sotto è un movimento osservato separatamente.</p>'+
  '<div class="gmfq-change-legs">'+leg(a,'A')+leg(b,'B')+'</div>'+
  '<p class="gmfq-change-summary">Dinamica relativa del modello (baseline Macro/Tassi '+htmlEscape(baselineVerified?macroDay:'non verificata')+
  '; prezzo Pair '+htmlEscape(modelDay||'non verificato')+'): '+phase+
  '. È una diagnosi qualitativa '+(baselineCurrent?'dello snapshot datato':'STORICA, da rivalidare')+
  ', non un nuovo rilascio economico.</p>'+
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
 const modelState=pairModelEvidenceState(macroDay,modelDay);
 const fav=modelState.verified&&[a,b].includes(src.structuralFav)?src.structuralFav:null;
 const other=fav===a?b:fav===b?a:null;
 const audited=/data-reaction-status="(COERENTE|DIVERGENTE|NON_CONCLUSIVO|WITHHELD)"/.exec(reactionHtml||'')?.[1]||'WITHHELD';
 const windowEnd=/data-window-end="(\d{4}-\d{2}-\d{2})"/.exec(reactionHtml||'')?.[1]||null;
 const side=/data-reaction-fx-side="([A-Z]{3})"/.exec(reactionHtml||'')?.[1]||null;
 const measured=windowEnd&&fresh(windowEnd,5)&&['COERENTE','DIVERGENTE'].includes(audited)&&[a,b].includes(side);
 const observation=measured?('Ultima finestra confrontabile fino al '+windowEnd+': fixing FX favorevole a '+FLAG[side]+' '+side+'.'):
  'La finestra recente non dà una verifica direzionale confrontabile: non usare un segnale surrogato.';
 const partial=!!fav&&(![a,b].includes(frame.macroSide)||![a,b].includes(frame.policySide));
 const need=modelState.verified&&typeof frame.missing==='string'&&frame.missing?
  frame.missing:'Differenziazione Macro/Rates ancora da verificare.';
 const confirm=!modelState.verified?
  'La baseline Macro/Tassi non è verificata: prima certificare il modello, poi definire cosa potrebbe confermare una direzione.':
  fav?
  'Verificare nuovi fixing BCE nella direzione di '+FLAG[fav]+' '+fav+
   ', confrontati con i 2Y sulle stesse date. '+
   (partial?'Controllare se il pilastro Macro o Tassi/CB oggi non decisivo diventa più chiaro.':
    'Controllare che entrambi i pilastri strutturali restino dalla stessa parte.'):
  'Prima serve una preferenza Macro/Tassi/CB verificabile e non soltanto uno spread governativo elevato.';
 const weakens=!modelState.verified?
  'Senza una baseline verificata non esiste una preferenza strutturale certificata da indebolire o invalidare.':
  fav?
  'Nuovi fixing nella direzione di '+FLAG[other]+' '+other+
   ' e peggioramento dei driver strutturali renderebbero meno convincente la lettura favorevole a '+
   fav+'. Da soli non definiscono un livello di invalidazione.':
  'Se Macro e Tassi/CB restano non discriminanti, eventuali movimenti di prezzo non sono una conferma strutturale.';
 const blockers=[];
 if(!modelState.verified)blockers.push('Baseline Macro/Tassi non verificata: qualità, timing e posizionamento del setup WITHHELD.');
 else if(!fav)blockers.push('Il motore non individua una valuta favorita.');
 if(modelState.verified&&(src.price?.state==='BAD'||src.price?.state==='NEUTRAL'))
  blockers.push('Prezzo nel modello: '+src.price.text+'.');
 if(modelState.verified&&['ADVANCED','EXTENDED'].includes(src.extension?.state))
  blockers.push('Estensione del prezzo: '+(src.extension.text||'già avanzato')+'.');
 if(modelState.verified&&typeof src.timing?.text==='string')blockers.push('Timing: '+src.timing.text+'.');
 if(modelState.verified&&['HIGH','DIVERGENT'].includes(src.cot?.state)&&typeof src.cot.text==='string')
  blockers.push('Posizionamento: '+src.cot.text+'.');
 if(modelState.verified&&src.liquidity?.state==='BAD'&&typeof src.liquidity.text==='string')
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
 const modelState=pairModelEvidenceState(macroDay,modelDay);
 const favored=modelState.verified&&(meta.structuralFav===base||meta.structuralFav===quote)?meta.structuralFav:null;
 const status=/data-reaction-status="(COERENTE|DIVERGENTE|NON_CONCLUSIVO|WITHHELD)"/.exec(reactionHtml||'')?.[1]||'WITHHELD';
 const observedSide=/data-reaction-fx-side="([A-Z]{3})"/.exec(reactionHtml||'')?.[1]||null;
 const validSide=(observedSide===base||observedSide===quote)&&['COERENTE','DIVERGENTE'].includes(status);
 // Recent FX/2Y observations can be valid while the structural Macro thesis is stale.
 // Never upgrade/downgrade that historical thesis from a newer FX movement.
 const baselineCurrent=modelState.current;
 const state=baselineCurrent&&validSide&&favored?
   (observedSide===favored?'CONFERMA_DIREZIONE':'CONTRO_TESI'):'NON_DETERMINATO';
 const trend=!baselineCurrent?
  'La baseline Macro/Tassi del '+(macroDay||'periodo non verificato')+
   ' è NON CORRENTE: tesi da rivalidare. I movimenti recenti FX e 2Y restano osservazioni valide ma non confermano né invalidano la tesi storica. Una coerenza 2Y–FX non equivale a conferma della tesi. '+
   (!favored?'Il motore non identifica una valuta strutturalmente favorita. ':'')+
   (!validSide?'Nessuna conferma o invalidazione dal fixing in questa finestra: audit assente, incompleto o non conclusivo. ':''):
  state==='CONTRO_TESI'?
  'Il fixing recente ha favorito '+FLAG[observedSide]+' '+observedSide+
   ', contro la preferenza strutturale '+FLAG[favored]+' '+favored+
   '. Una coerenza 2Y–FX non equivale a conferma della tesi.':
  state==='CONFERMA_DIREZIONE'?
   'Il fixing recente ha favorito '+FLAG[favored]+' '+favored+
   ', nella direzione della tesi. È una conferma di direzione nel periodo, non un nuovo ingresso.':
  favored?'Nessuna conferma o invalidazione dal fixing in questa finestra: audit assente, incompleto o non conclusivo.':
   'Il motore non identifica una valuta strutturalmente favorita: il confronto Rates/FX non crea da solo una tesi.';
 const structural=!modelState.verified?'WITHHELD · baseline non verificata':
  favored?(baselineCurrent?'Favore ':'Preferenza storica · ')+FLAG[favored]+' '+favored:
  'Nessuna preferenza netta';
 const quality=modelState.verified&&typeof frame.quality==='string'&&frame.quality?frame.quality:'WITHHELD · modello non verificato';
 const setupQuality=modelState.verified&&typeof meta.quality==='string'&&meta.quality?meta.quality:'WITHHELD · modello non verificato';
 const setupTiming=modelState.verified&&typeof meta.timing?.text==='string'?meta.timing.text:'Timing non certificato';
 const watch=!baselineCurrent?
  'Prima rivalidare la baseline Macro/Tassi e il relativo giudizio sulle due valute. I fixing FX recenti, da soli, non aggiornano la tesi storica.':
  typeof frame.watch==='string'&&frame.watch?frame.watch:'Servono nuove evidenze Macro e Rates certificate.';
 const price=modelState.verified&&typeof frame.priceNote==='string'&&frame.priceNote?frame.priceNote:'Prezzo del modello non verificato';
 const label=status==='COERENTE'?'Coerente tra 2Y e FX':status==='DIVERGENTE'?'Divergente tra 2Y e FX':
  status==='NON_CONCLUSIVO'?'Non conclusivo':'Non valutabile';
 return '<section id="gmfq-pair-decision-bridge" class="gmfq-decision-bridge" data-bridge-status="'+state+
  '" data-baseline-status="'+(baselineCurrent?'CURRENT':'STALE_OR_UNVERIFIED')+'" aria-label="Tesi, setup e reazione recente">'+
  '<h3>Dalla tesi alla decisione · cosa conta davvero</h3>'+
  '<p>I fixing e i 2Y recenti non aggiornano la tesi Macro né rendono automaticamente operabile il setup.</p>'+
  '<div class="gmfq-decision-cols"><div><span>TESI STRUTTURALE · baseline '+htmlEscape(modelState.verified?macroDay:'non certificata')+'</span><strong>'+
  structural+'</strong><small>'+htmlEscape(quality)+'</small></div>'+
  '<div><span>OPERABILITÀ · SETUP DEL MODELLO'+(modelState.historical?' · STORICO':'')+'</span><strong>'+htmlEscape(setupQuality)+'</strong><small>'+
  htmlEscape(setupTiming)+'</small></div>'+
  '<div><span>REAZIONE OSSERVATA · RATES / FX</span><strong>'+htmlEscape(label)+'</strong><small>'+
  htmlEscape(trend)+'</small></div></div>'+
  '<div class="gmfq-decision-watch"><strong>'+
  (baselineCurrent?'Cosa monitorare secondo il modello':'Prima di considerare valida la tesi')+
  '</strong><p>'+htmlEscape(watch)+'</p></div>'+
  pairEvidenceChecklist(code,pair,modelDay,reactionHtml,macroDay)+
  '<p class="gmfq-decision-context">Lettura prezzo del modello ('+htmlEscape(modelDay)+'): '+htmlEscape(price)+'</p>'+
  '<p class="gmfq-decision-disclaimer">Non sono disponibili trigger numerici certificati di conferma, invalidazione o ingresso in questo feed. Nessun livello, stop, score o segnale viene creato da questa sezione.</p></section>';
}

/* Comparative editorial reading of ALL 28 existing canonical pairs.
   The 1–28 order is a transparent lexicographic checklist, not a model score,
   estimated return, actual entry signal or update to the historical thesis.
   The native sortable/filterable pair TABLE and click listeners are retained. */
function pairDeskOrdering(feedData,model){
 if(feedData?.schema!=='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'||
    feedData.status!=='CURRENT_CANONICAL_ENGINE'||feedData.pair_count!==28||
    !feedData.thesis_is_not_entry||feedData.entry_level_published!==false||
    feedData.price_audit?.status!=='PASS'||
    feedData.price_audit.as_of!==feedData.price_asof||
    !fresh(feedData.price_asof,5)||
    !canonicalPairMacroBaseline(feedData,model))return null;
 const book=feedData.pairs;
 const ids=Object.keys(book||{});
 if(ids.length!==28||!ids.every(x=>/^[A-Z]{6}$/.test(x)&&
    FX.includes(x.slice(0,3))&&FX.includes(x.slice(3))&&x.slice(0,3)!==x.slice(3)))return null;
 const dist={'DA CONFERMARE':0,'DA MONITORARE':0,'CON RISCHI':0,'NON VALUTABILE':0};
 const timingRank={ALIGNED:4,PARTIAL:3,MIXED:2,UNCERTAIN:1,ADVERSE:0};
 const sourceRows=[];
 for(const code of ids){
   const p=book[code],x=p?.setup||{},f=p?.decision_frame||{};
   const quality=x.quality,struct=f.quality;
   if(!Object.hasOwn(dist,quality)||!['CONTRASTO STRUTTURALE FORTE',
       'VANTAGGIO RELATIVO PARZIALE','PILASTRI DIVISI',
       'SEPARAZIONE RATES MATERIALE','NESSUN CONTRASTO'].includes(struct)||
      struct!==x.structural?.quality)return null;
   dist[quality]++;
   const fav=x.structuralFav;
   const eligible=quality!=='NON VALUTABILE';
   if(eligible&&(![code.slice(0,3),code.slice(3)].includes(fav)||
     !['GOOD','BAD','NEUTRAL'].includes(x.price?.state)||
     !['ADVANCED','EXTENDED','NORMAL'].includes(x.extension?.state)||
     !Object.hasOwn(timingRank,x.timing?.state)||
     !['GOOD','NEUTRAL','BAD'].includes(x.liquidity?.state)||
     !['HIGH','MEDIUM','DIVERGENT','CONTEXT'].includes(x.cot?.state)||
     !['DINAMICA RELATIVA ALLINEATA','DIVERGENZA RELATIVA DA MONITORARE',
       'NESSUNA DIVERGENZA RELATIVA CHIARA'].includes(p.transition?.state)))
      return null;
   if(!eligible&&(fav!==null||!['PILASTRI DIVISI',
      'SEPARAZIONE RATES MATERIALE','NESSUN CONTRASTO'].includes(struct)))
      return null;
   const structure=struct==='CONTRASTO STRUTTURALE FORTE'?3:
      struct==='VANTAGGIO RELATIVO PARZIALE'?2:0;
   const price={GOOD:2,NEUTRAL:1,BAD:0}[x.price?.state]??0;
   const timing=timingRank[x.timing?.state]??-1;
   const extension=x.extension?.state==='NORMAL'?1:0;
   const transition=p.transition?.state==='DINAMICA RELATIVA ALLINEATA'?2:
     p.transition?.state==='NESSUNA DIVERGENZA RELATIVA CHIARA'?1:0;
   const liquidity={GOOD:2,NEUTRAL:1,BAD:0}[x.liquidity?.state]??0;
   const cot={MEDIUM:3,CONTEXT:2,HIGH:1,DIVERGENT:0}[x.cot?.state]??0;
   const reasons=[];
   if(!eligible)reasons.push(struct==='PILASTRI DIVISI'?'Macro e Tassi/CB in conflitto':
     struct==='SEPARAZIONE RATES MATERIALE'?'Solo spread 2Y; tesi assente':
     'Nessuna preferenza Macro/Tassi');
   else {
     if(x.price?.state==='BAD')reasons.push('Prezzo contro la tesi');
     else if(x.price?.state==='NEUTRAL')reasons.push('Prezzo non conferma');
     if(x.timing?.state==='ADVERSE')reasons.push('Timing contrario');
     if(['ADVANCED','EXTENDED'].includes(x.extension?.state))reasons.push('Prezzo già avanzato');
     if(p.transition?.state==='DIVERGENZA RELATIVA DA MONITORARE')
       reasons.push('Dinamica relativa divergente');
     if(x.timing?.state==='UNCERTAIN')reasons.push('Timing incerto');
     if(x.timing?.state==='MIXED')reasons.push('Timing misto');
     if(x.timing?.state==='PARTIAL')reasons.push('Timing solo parziale');
     if(x.cot?.state==='HIGH')reasons.push('COT affollato/estremo');
     if(x.cot?.state==='DIVERGENT')reasons.push('COT contrario');
     if(x.liquidity?.state==='BAD')reasons.push('Liquidità sfavorevole');
     if(struct==='VANTAGGIO RELATIVO PARZIALE')
       reasons.push('Tesi sorretta da un solo pilastro');
   }
   if(!reasons.length)reasons.push('Servono trigger e rapporto rischio/rendimento esterni al modello');
   // One source-derived first research check; no automatic triggers or scores.
   const checks={
     'Macro e Tassi/CB in conflitto':'Rivedere se Macro e Tassi/CB convergono sulla stessa valuta',
     'Solo spread 2Y; tesi assente':'Cercare una tesi Macro/Tassi; lo spread 2Y non basta',
     'Nessuna preferenza Macro/Tassi':'Attendere un contrasto strutturale verificabile',
     'Prezzo contro la tesi':'Verificare se il prezzo smette di opporsi alla tesi',
     'Prezzo non conferma':'Cercare conferma del prezzo nella direzione favorita',
     'Timing contrario':'Controllare se la dinamica relativa smette di essere contraria',
     'Prezzo già avanzato':'Controllare consolidamento o retest, senza inseguire',
     'Dinamica relativa divergente':'Verificare se la divergenza relativa rientra',
     'Timing incerto':'Attendere dinamica relativa più leggibile',
     'Timing misto':'Controllare se il timing diventa coerente',
     'Timing solo parziale':'Verificare un miglioramento del timing relativo',
     'COT affollato/estremo':'Controllare se il crowding COT si riduce',
     'COT contrario':'Controllare se il posizionamento COT smette di opporsi',
     'Liquidità sfavorevole':'Verificare se il contesto di liquidità migliora',
     'Tesi sorretta da un solo pilastro':'Cercare conferma dal pilastro Macro o Tassi/CB mancante',
     'Servono trigger e rapporto rischio/rendimento esterni al modello':'Definire trigger e rischio/rendimento separatamente'
   };
   const firstCheck=checks[reasons[0]];
   if(!firstCheck)return null;
   sourceRows.push({code,quality,fav:eligible?fav:null,firstCheck,
     thesis:structure===3?'Tesi forte':structure===2?'Tesi parziale':'Senza tesi',
     priceReading:!eligible?'Prezzo non valutabile':
       x.price.state==='GOOD'?'Prezzo conferma':
       x.price.state==='NEUTRAL'?'Prezzo neutro':'Prezzo contrario',
     timingReading:!eligible?'Timing non valutabile':
       x.timing.state==='ALIGNED'?'Timing allineato':
       x.timing.state==='PARTIAL'?'Timing parziale':
       x.timing.state==='ADVERSE'?'Timing contrario':
       x.timing.state==='MIXED'?'Timing misto':'Timing incerto',
     why:reasons.slice(0,2).join(' · '),
     thesisKey:[Number(eligible),structure,transition,price,timing,extension,liquidity,cot],
     setupKey:[Number(eligible),price,extension,timing,structure,transition,liquidity,cot]});
 }
 // Source quality buckets with zero members may be legitimately omitted.
 // Normalize ONLY absent zero-count buckets; contradictory, unknown or
 // non-integer counts still fail closed before displaying a 1-28 ranking.
 const published=feedData.quality_distribution;
 if(!published||typeof published!=='object'||Array.isArray(published)||
    Object.entries(published).some(([key,value])=>
      !Object.hasOwn(dist,key)||!Number.isInteger(value)||value<0)||
    Object.keys(dist).some(key=>dist[key]!==
      (Object.hasOwn(published,key)?published[key]:0))||
    Object.values(dist).reduce((a,b)=>a+b,0)!==28)return null;
 const compare=(key)=>(a,b)=>{
   for(let i=0;i<a[key].length;i++){
     const d=b[key][i]-a[key][i];
     if(d)return d;
   }
   return a.code.localeCompare(b.code);
 };
 return {
   setup:sourceRows.slice().sort(compare('setupKey')),
   thesis:sourceRows.slice().sort(compare('thesisKey')),
   count:28,priceAsOf:feedData.price_asof,macroAsOf:feedData.macro_baseline_asof,
   source:'PAIR_SETUP_OPERATIONAL_VIEW',baselineHistorical:!fresh(feedData.macro_baseline_asof,10)
 };
}

/* The first eight are a research watchlist, not a diversified portfolio.
   Currency recurrence and quality counts use the SAME canonical 28-pair
   records and current editorial ordering; no statistical risk is inferred. */
function pairDeskFocusOverlap(ranked,mode){
 const rows=ranked?.[mode]?.slice(0,8);
 if(!Array.isArray(rows)||rows.length!==8||!['setup','thesis'].includes(mode)||
    rows.some(r=>!r||typeof r.code!=='string')||
    new Set(rows.map(r=>r.code)).size!==8)return null;
 const count=Object.fromEntries(FX.map(c=>[c,0])),
       favCount=Object.fromEntries(FX.map(c=>[c,0]));
 let withRisks=0;
 for(const r of rows){
   if(!/^[A-Z]{6}$/.test(r.code||'')||
      !['DA CONFERMARE','DA MONITORARE','CON RISCHI','NON VALUTABILE'].includes(r.quality))return null;
   const a=r.code.slice(0,3),b=r.code.slice(3);
   if(!FX.includes(a)||!FX.includes(b)||a===b)return null;
   count[a]++;count[b]++;
   if(r.fav!==null){
     if(![a,b].includes(r.fav))return null;
     favCount[r.fav]++;
   }
   if(r.quality==='CON RISCHI')withRisks++;
 }
 const sorted=Object.entries(count).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));
 const max=sorted[0]?.[1];
 if(!Number.isInteger(max)||max<1)return null;
 const repeated=sorted.filter(x=>x[1]===max).map(x=>x[0]);
 return {total:8,withRisks,max,repeated,frequencies:count,favored:favCount};
}
async function mountPairRankedList(doc){
 if(route()!=='coppie'||frame.contentDocument!==doc||doc.getElementById('gmfq-pair-rank'))return;
 const tbody=doc.getElementById('pair-index'),table=tbody?.closest('table');
 const holder=table?.closest('.desk-panel');
 if(!holder)return;
 const panel=doc.createElement('section');panel.id='gmfq-pair-rank';
 panel.className='desk-panel';panel.dataset.status='LOADING';panel.dataset.sortMode='setup';
 panel.setAttribute('aria-label','Ordine comparativo delle 28 coppie G8');
 panel.innerHTML='<h2 class="desk-panel-title">28 coppie · ordine di lettura</h2>'+
  '<p class="gmfq-rank-explain">Confronto delle evidenze del modello in verifica…</p>';
 holder.insertAdjacentElement('beforebegin',panel);
 const [setupRes,modelRes]=await Promise.allSettled([feed('PAIR_SETUP_OPERATIONAL_VIEW.json'),feed('D.json')]);
 if(route()!=='coppie'||frame.contentDocument!==doc||!panel.isConnected)return;
 const data=setupRes.status==='fulfilled'?setupRes.value:null,
       model=modelRes.status==='fulfilled'?modelRes.value:null,
       ranked=pairDeskOrdering(data,model);
 if(!ranked){
   panel.dataset.status='WITHHELD';
   panel.innerHTML='<h2 class="desk-panel-title">Ordine delle 28 coppie · non verificabile</h2>'+
    '<p class="gmfq-rank-explain">Feed o baseline Macro/Tassi non riconciliati: non ordino arbitrariamente le coppie. Rimane consultabile la tabella originale.</p>';
   return;
 }
 const st=doc.createElement('style');st.id='gmfq-pair-rank-style';
 st.textContent='#gmfq-pair-rank{margin:0 0 13px;padding:13px 16px;min-width:0;background:linear-gradient(135deg,#0b2030,#081b2b)}'+
 '#gmfq-pair-rank .gmfq-rank-switch{display:flex;gap:7px;flex-wrap:wrap;margin:9px 0}'+
 '#gmfq-pair-rank .gmfq-rank-switch button{border:1px solid #466073;border-radius:5px;background:#10293a;color:#c8d9e6;cursor:pointer;font:600 12px/1.45 Arial,sans-serif;padding:7px 12px}'+
 '#gmfq-pair-rank .gmfq-rank-switch button[aria-pressed="true"]{border-color:#d5bc7e;color:#f1d9a4;background:#283547}'+
 '#gmfq-pair-rank .gmfq-rank-switch button:focus-visible{outline:2px solid #dec787;outline-offset:2px}'+
 '#gmfq-pair-rank .gmfq-rank-explain{color:#c0d1de;font:12px/1.55 Arial,sans-serif;margin:5px 0;overflow-wrap:anywhere}'+
 '#gmfq-pair-rank .gmfq-rank-method{color:#9db6c8;font:11px/1.55 Arial,sans-serif;margin:7px 0 2px}'+
 '#gmfq-pair-rank .gmfq-rank-lead{color:#e5c98d;font:600 12px/1.55 Arial,sans-serif;margin:6px 0 4px}'+
 '#gmfq-pair-rank .gmfq-rank-overlap{color:#b7ccd9;font:11px/1.55 Arial,sans-serif;margin:4px 0 8px;overflow-wrap:anywhere}'+
 '#gmfq-pair-rank .gmfq-rank-source{font:10px/1.5 Arial,sans-serif;color:#91abbb}'+
 '#gmfq-pair-rank .gmfq-rank-view{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin:5px 0 8px}'+
 '#gmfq-pair-rank .gmfq-rank-view button{cursor:pointer;border:1px solid #496274;background:transparent;border-radius:4px;padding:5px 9px;color:#c9d9e5;font:600 11px/1.5 Arial,sans-serif}'+
 '#gmfq-pair-rank .gmfq-rank-view button[aria-pressed="true"]{color:#e7cd93;border-color:#c2a76c;background:#243647}'+
 '#gmfq-pair-rank .gmfq-rank-view button:focus-visible{outline:2px solid #e2c98f;outline-offset:2px}'+
 '#gmfq-pair-rank .gmfq-rank-visibility{font:11px/1.45 Arial,sans-serif;color:#9fbacb}'+
 '#gmfq-pair-rank .gmfq-reading-switch{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:2px 0 6px}'+
 '#gmfq-pair-rank .gmfq-reading-switch button{cursor:pointer;border:1px solid #496274;background:transparent;border-radius:4px;padding:5px 9px;color:#c9d9e5;font:600 11px/1.5 Arial,sans-serif}'+
 '#gmfq-pair-rank .gmfq-reading-switch button[aria-pressed="true"]{color:#e7cd93;border-color:#c2a76c;background:#243647}'+
 '#gmfq-pair-rank .gmfq-reading-switch button:focus-visible{outline:2px solid #e2c98f;outline-offset:2px}'+
 '#gmfq-pair-rank .gmfq-reading-switch span{font:11px/1.5 Arial,sans-serif;color:#9fb6c6}'+
 '#pair-index[data-research-reading="compact"] .gmfq-row-lenses,#pair-index[data-research-reading="compact"] .gmfq-row-next{display:none!important}'+
 '#gmfq-pair-rank .gmfq-rank-method-detail{margin:6px 0}'+
 '#gmfq-pair-rank .gmfq-rank-method-detail summary{cursor:pointer;color:#a8c1d0;font:11px/1.5 Arial,sans-serif;padding:4px 0;outline-offset:3px}'+
 '#gmfq-pair-rank .gmfq-rank-method-detail summary:focus-visible{outline:2px solid #e2c98f}'+
 '#pair-index tr.gmfq-research-hidden{display:none!important}'+
 '#pair-index .gmfq-row-rank{display:inline-block;min-width:22px;color:#dfc891;font:600 12px/1.5 Arial,sans-serif;margin-right:7px;font-variant-numeric:tabular-nums}'+
 '#pair-index .gmfq-row-lenses{display:block;margin-top:3px;color:#e3d19f;font:10px/1.45 Arial,sans-serif;max-width:300px;overflow-wrap:anywhere}'+
 '#pair-index .gmfq-row-why{display:block;margin-top:3px;color:#a8bfcd;font:10px/1.45 Arial,sans-serif;max-width:300px;overflow-wrap:anywhere}'+
 '#pair-index .gmfq-row-next{display:block;margin-top:4px;color:#d1dbc7;font:10px/1.5 Arial,sans-serif;max-width:330px;overflow-wrap:anywhere}'+
 '#pair-index tr[data-research-rank] td:nth-child(4){min-width:170px}'+
 '@media(max-width:600px){#gmfq-pair-rank{padding:12px}#gmfq-pair-rank .gmfq-rank-switch button{font-size:11px}#pair-index .gmfq-row-why{max-width:190px}}';
 doc.head.appendChild(st);
 panel.dataset.status='READ_ONLY';panel.dataset.count='28';
 panel.dataset.macroAsOf=ranked.macroAsOf;panel.dataset.priceAsOf=ranked.priceAsOf;
 panel.dataset.hasTradeRanking='false';
 panel.innerHTML='<h2 class="desk-panel-title">28 coppie · dalla più coerente alla meno coerente</h2>'+
  '<p class="gmfq-rank-explain"><strong>Prima lettura:</strong> verdetto e ostacolo principale. Apri «Verifiche» per tesi, prezzo, timing e primo controllo; nessun ingresso implicito.</p>'+
  '<div class="gmfq-rank-switch" role="group" aria-label="Criterio di ordinamento delle coppie">'+
  '<button type="button" data-rank-mode="setup" aria-pressed="true">Condizioni del setup</button>'+
  '<button type="button" data-rank-mode="thesis" aria-pressed="false">Forza della tesi</button></div>'+
  '<div class="gmfq-rank-view" role="group" aria-label="Quante coppie mostrare">'+
   '<button type="button" data-pair-view="focus" aria-pressed="true">Prime 8</button>'+
   '<button type="button" data-pair-view="all" aria-pressed="false">Tutte le 28</button>'+
   '<span class="gmfq-rank-visibility" role="status" aria-live="polite">Prime 8 · altre coppie disponibili</span></div>'+
  '<div class="gmfq-reading-switch" role="group" aria-label="Livello di approfondimento delle righe">'+
   '<button type="button" data-pair-reading="compact" aria-pressed="true">Sintesi</button>'+
   '<button type="button" data-pair-reading="details" aria-pressed="false">Verifiche</button>'+
   '<span>Il giudizio del modello non cambia</span></div>'+
  '<p class="gmfq-rank-lead" aria-live="polite"></p>'+
  '<p class="gmfq-rank-overlap" aria-live="polite" data-source="PAIR_SETUP_OPERATIONAL_VIEW"></p>'+
  '<details class="gmfq-rank-method-detail"><summary>Metodo e limiti del ranking</summary>'+
   '<p class="gmfq-rank-method">Ordine editoriale, NON probabilità, score quantitativo o segnale. Setup: presenza della tesi → prezzo → estensione → timing → coerenza Macro/Tassi → dinamica → liquidità/COT. Tesi: coerenza Macro/Tassi → dinamica → altre conferme. Le 11 senza preferenza strutturale sono in fondo.</p></details>'+
  '<p class="gmfq-rank-source">Fonte '+htmlEscape(ranked.source)+' · prezzo del modello '+htmlEscape(ranked.priceAsOf)+
  ' · baseline Macro/Tassi '+htmlEscape(ranked.macroAsOf)+(ranked.baselineHistorical?' (STORICA, NON AGGIORNATA)':'')+
  '. La prima coppia non è necessariamente un trade eseguibile.</p>';
 const lead=panel.querySelector('.gmfq-rank-lead'),overlap=panel.querySelector('.gmfq-rank-overlap'),head=table.tHead?.querySelectorAll('th');
 if(head?.[3])head[3].textContent='Valutazione e principale cautela';
 let mode='setup',view='focus',reading='compact';
 panel.dataset.viewMode=view;panel.dataset.displayLimit='8';panel.dataset.readingMode=reading;
 tbody.dataset.researchReading=reading;
 const visibilityLabel=panel.querySelector('.gmfq-rank-visibility');
 const apply=()=>{
   if(!panel.isConnected||frame.contentDocument!==doc||route()!=='coppie')return;
   const order=ranked[mode],indexed=new Map(order.map((r,i)=>[r.code,{...r,rank:i+1}]));
   const existing=[...tbody.querySelectorAll(':scope > tr')];
   const pairs=existing.filter(x=>x.querySelector('button.pair-open[data-pair]'));
   if(!pairs.length)return; // Native filters can show zero rows.
   const codes=pairs.map(tr=>tr.querySelector('button.pair-open').dataset.pair);
   if(new Set(codes).size!==codes.length||codes.some(x=>!indexed.has(x)))return;
   const search=doc.getElementById('pair-search')?.value?.trim()||'',
         cross=!!doc.getElementById('pair-cross')?.checked;
   const unfiltered=!search&&!cross;
   // Search matches and deep-linked selection remain visible beyond the first eight.
   let showing=0;
   for(const row of pairs){
     const code=row.querySelector('button.pair-open').dataset.pair,r=indexed.get(code);
     const selectedRow=row.classList.contains('pair-current');
     const visible=view==='all'||!unfiltered||r.rank<=8||selectedRow;
     row.classList.toggle('gmfq-research-hidden',!visible);
     row.dataset.researchVisible=String(visible);
     if(visible)showing++;
     row.dataset.researchRank=String(r.rank);
     row.dataset.researchMode=mode;
     const first=row.cells[0],verdict=row.cells[3];
     let label=first.querySelector('.gmfq-row-rank');
     if(!label){label=doc.createElement('span');label.className='gmfq-row-rank';first.insertBefore(label,first.firstChild)}
     label.textContent=String(r.rank).padStart(2,'0');
     let lenses=verdict.querySelector('.gmfq-row-lenses');
     if(!lenses){lenses=doc.createElement('small');lenses.className='gmfq-row-lenses';verdict.appendChild(lenses)}
     lenses.textContent=r.thesis+' · '+r.priceReading+' · '+r.timingReading;
     lenses.dataset.source='PAIR_SETUP_OPERATIONAL_VIEW';
     let why=verdict.querySelector('.gmfq-row-why');
     if(!why){why=doc.createElement('small');why.className='gmfq-row-why';verdict.appendChild(why)}
     why.textContent=(r.fav?'Favore '+r.fav+' · ':'Nessuna direzione · ')+r.why;
     let check=verdict.querySelector('.gmfq-row-next');
     if(!check){check=doc.createElement('small');check.className='gmfq-row-next';verdict.appendChild(check)}
     check.textContent='Primo controllo · '+r.firstCheck;
     check.dataset.source='PAIR_SETUP_OPERATIONAL_VIEW';
   }
   const sorted=pairs.slice().sort((a,b)=>indexed.get(a.querySelector('button.pair-open').dataset.pair).rank-
     indexed.get(b.querySelector('button.pair-open').dataset.pair).rank);
   if(sorted.some((tr,i)=>tr!==pairs[i]))tbody.append(...sorted);
   panel.dataset.visibleCount=String(showing);
   const nativeCount=doc.getElementById('pair-visible');
   if(nativeCount&&unfiltered)nativeCount.textContent=showing+'/28 coppie in evidenza · '+(28-showing)+' ulteriori disponibili';
   if(visibilityLabel)visibilityLabel.textContent=view==='all'?
     'Tutte le '+pairs.length+' coppie attualmente filtrate, ordine conservato':
     unfiltered?String(showing)+' coppie in evidenza · altre '+(pairs.length-showing)+
       ' apribili · coppia selezionata sempre visibile':
       String(showing)+' risultati del filtro · la ricerca include tutte le 28 coppie';
 };
 const headline=()=>{
   const first=ranked[mode][0];
   lead.textContent=(mode==='setup'?'Priorità di verifica del setup':'Solidità della tesi storica')+
     ' · primo nell’ordine: '+FLAG[first.code.slice(0,3)]+' '+FLAG[first.code.slice(3)]+' '+first.code+
     ' · '+first.thesis+' · '+first.why+'. Non è un ingresso.';
   const focus=pairDeskFocusOverlap(ranked,mode);
   if(!focus){
     overlap.textContent='Sovrapposizione delle prime 8 non verificabile.';
     overlap.dataset.status='WITHHELD';
     return;
   }
   const c=focus.repeated;
   const names=c.map(x=>FLAG[x]+' '+x).join(' / ');
   const fav=c.map(x=>focus.favored[x]).join(' / ');
   overlap.dataset.status='OBSERVED';
   overlap.dataset.topCount=String(focus.total);
   overlap.dataset.withRisks=String(focus.withRisks);
   overlap.dataset.mostRepeated=c.join(',');
   overlap.dataset.frequency=String(focus.max);
   overlap.dataset.favoredCount=fav;
   overlap.textContent='Prime 8 · '+focus.withRisks+'/8 CON RISCHI · '+
     (c.length===1?'Valuta più ricorrente: ':'Valute più ricorrenti: ')+
     names+' in '+focus.max+'/8 coppie (valuta favorita dal modello storico in '+fav+'/8). '+
     'Sovrapposizione valutaria, non correlazione né rischio portafoglio stimati.';
 };
 panel.addEventListener('click',e=>{
   const b=e.target.closest('button[data-rank-mode],button[data-pair-view],button[data-pair-reading]');
   if(!b||!panel.contains(b))return;
   if(b.hasAttribute('data-pair-reading')){
     if(!['compact','details'].includes(b.dataset.pairReading))return;
     reading=b.dataset.pairReading;panel.dataset.readingMode=reading;
     tbody.dataset.researchReading=reading;
     panel.querySelectorAll('button[data-pair-reading]').forEach(x=>
       x.setAttribute('aria-pressed',String(x.dataset.pairReading===reading)));
     return;
   }
   if(b.hasAttribute('data-pair-view')){
     if(!['focus','all'].includes(b.dataset.pairView))return;
     view=b.dataset.pairView;panel.dataset.viewMode=view;
     panel.querySelectorAll('button[data-pair-view]').forEach(x=>
       x.setAttribute('aria-pressed',String(x.dataset.pairView===view)));
     apply();return;
   }
   if(!['setup','thesis'].includes(b.dataset.rankMode))return;
   mode=b.dataset.rankMode;panel.dataset.sortMode=mode;
   panel.querySelectorAll('button[data-rank-mode]').forEach(x=>
     x.setAttribute('aria-pressed',String(x.dataset.rankMode===mode)));
   headline();apply();
 });
 const obs=new MutationObserver(()=>apply());
 obs.observe(tbody,{childList:true}); // Native text search & selecting a pair both re-render the same tbody.
 headline();apply();
}
async function mountPairResearch(doc){
 if(route()!=='coppie'||frame.contentDocument!==doc)return;
 const host=doc.getElementById('pair-detail');
 if(!host)return;
 const inputs=await Promise.allSettled([
  feed('PAIR_SETUP_OPERATIONAL_VIEW.json'),feed('ECB_G8_PRICE_HISTORY.json'),
  feed('NATIVE_RATES_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json'),
  feed('D.json'),feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json')]);
 if(frame.contentDocument!==doc||route()!=='coppie')return;
 const [setup,fx,rates,ois,model,proxy]=inputs.map(x=>x.status==='fulfilled'?x.value:null);
 const ok=setup?.schema==='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'&&
  setup.status==='CURRENT_CANONICAL_ENGINE'&&setup.pair_count===28&&
  Object.keys(setup.pairs||{}).length===28&&setup.price_audit?.status==='PASS'&&
  setup.price_audit.as_of===setup.price_asof&&setup.thesis_is_not_entry===true&&
  setup.entry_level_published===false&&fresh(setup.price_asof,5);
 const fxOk=valuteFxSourceStatus(fx).status==='OFFICIAL_FIXING_RECENT';
 const macroVerified=canonicalPairMacroBaseline(setup,model)!==null;
 if(!ok||!host||doc.getElementById('gmfq-pair-research-path'))return;
 const style=doc.createElement('style');style.id='gmfq-pair-path-style';
 style.textContent='#gmfq-pair-research-path{margin-top:12px}#gmfq-pair-research-path .gmfq-path-body{padding:13px 17px 16px}#gmfq-pair-research-path p{color:#b8cad7;font-size:12px;line-height:1.55;margin:7px 0 12px}#gmfq-pair-research-path .gmfq-path-evidence{color:#e0c788;font-size:11px;line-height:1.5}#gmfq-pair-research-path .gmfq-path-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}#gmfq-pair-research-path .gmfq-path-leg{border:1px solid #294457;border-radius:6px;background:#0a2232;padding:12px 13px;min-width:0}#gmfq-pair-research-path .gmfq-path-leg strong{color:#ebf2f7;font-size:14px;display:block}#gmfq-pair-research-path .gmfq-path-leg small{display:block;color:#9db6c8;font-size:11px;margin:5px 0 9px;line-height:1.4}#gmfq-pair-research-path .gmfq-path-links{display:flex;flex-wrap:wrap;gap:6px}#gmfq-pair-research-path button{border:1px solid #3a596d;background:#122d40;border-radius:5px;padding:6px 9px;color:#e6edf4;font:11px Arial,sans-serif;cursor:pointer}#gmfq-pair-research-path button:hover{border-color:#e3c57c;color:#f1d894}#gmfq-pair-research-path button:focus-visible{outline:2px solid #e3c57c;outline-offset:2px}#gmfq-pair-research-path .gmfq-path-warning{color:#dfc894;border-top:1px solid #2a4759;padding-top:10px}@media(max-width:600px){#gmfq-pair-research-path .gmfq-path-legs{grid-template-columns:1fr}#gmfq-pair-research-path .gmfq-path-body{padding:11px}}';
 style.textContent+='.gmfq-compare{border-top:1px solid #2b4757;margin-top:14px;padding-top:13px}.gmfq-compare h3{margin:0 0 11px;font:600 14px/1.3 Arial,sans-serif;color:#e5eff6}.gmfq-compare-score{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.gmfq-compare-score>div{border-left:2px solid #997e4d;padding:7px 10px;background:#0e2534;min-width:0}.gmfq-compare-score span{display:block;font:10px/1.4 Arial,sans-serif;color:#a6bac7}.gmfq-compare-score strong{display:block;font:600 12px/1.5 Arial,sans-serif;color:#e5edf3;margin-top:4px}.gmfq-compare-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.gmfq-compare-leg{min-width:0;padding:10px 12px;border-radius:5px;background:#0a1f2d;border:1px solid #274453}.gmfq-compare-leg strong{display:block;color:#e5eefa;font:600 12px Arial,sans-serif;margin-bottom:5px}.gmfq-compare-leg small{display:block;color:#b2c6d4;font:11px/1.5 Arial,sans-serif;margin:5px 0;overflow-wrap:anywhere}.gmfq-compare p{font:12px/1.55 Arial,sans-serif;margin:10px 0 0}.gmfq-compare .gmfq-compare-spread{color:#e1c990}.gmfq-compare .gmfq-compare-note{color:#cadbe5}.gmfq-compare .gmfq-compare-disclaimer{font-size:10px;color:#9ab4c5}@media(max-width:600px){.gmfq-compare-score,.gmfq-compare-legs{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-what-changed{border-top:1px solid #284354;margin-top:16px;padding-top:14px}.gmfq-what-changed h3{margin:0;color:#e9f1f7;font:600 14px/1.4 Arial,sans-serif}.gmfq-what-changed>p{font:12px/1.55 Arial,sans-serif;color:#abc3d2;margin:7px 0 11px}.gmfq-change-legs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.gmfq-change-leg{border-left:2px solid #58718a;padding:9px 11px;background:#0d2332;min-width:0}.gmfq-change-leg strong{display:block;font:600 13px Arial,sans-serif;color:#e8f0f6;margin-bottom:8px}.gmfq-change-leg span{display:block;font:10px/1.4 Arial,sans-serif;color:#a0b6c5;letter-spacing:.02em}.gmfq-change-leg p{font:12px/1.5 Arial,sans-serif;color:#d2e0e9;margin:4px 0 11px;overflow-wrap:anywhere}.gmfq-change-leg .gmfq-change-measured{color:#e1c78a;margin-bottom:0}.gmfq-what-changed .gmfq-change-summary{color:#c5d7e2}.gmfq-what-changed .gmfq-change-warning{color:#93abba;font-size:10px}@media(max-width:600px){.gmfq-change-legs{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-reaction{border-top:1px solid #294557;margin-top:15px;padding-top:14px}.gmfq-reaction h3{font:600 14px/1.4 Arial,sans-serif;margin:0 0 9px;color:#e6eff5}.gmfq-reaction p{color:#b4c8d5;font:12px/1.55 Arial,sans-serif;margin:7px 0 11px}.gmfq-reaction .gmfq-reaction-window{font:11px/1.5 Arial,sans-serif;color:#dec98f;padding:5px 0}.gmfq-reaction-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:9px 0}.gmfq-reaction-metrics>div{border:1px solid #294554;border-radius:5px;padding:11px 12px;min-width:0;background:#0b2434}.gmfq-reaction-metrics span{display:block;color:#a4bbc9;font:10px/1.45 Arial,sans-serif}.gmfq-reaction-metrics strong{display:block;color:#edf2f7;font:600 21px/1.4 Arial,sans-serif;font-variant-numeric:tabular-nums;margin:3px 0}.gmfq-reaction-metrics small{display:block;color:#b4c7d5;font:11px/1.45 Arial,sans-serif;overflow-wrap:anywhere}.gmfq-reaction .gmfq-reaction-verdict{border-left:2px solid #a08b58;padding:8px 11px;background:#102638;color:#cbdce7}.gmfq-reaction-verdict strong{color:#e6d59c}.gmfq-reaction-verdict[data-reaction-verdict="COERENTE"]{border-color:#3ac998}.gmfq-reaction-verdict[data-reaction-verdict="DIVERGENTE"]{border-color:#e36a79}.gmfq-reaction .gmfq-reaction-note{color:#a9bdcb}.gmfq-reaction .gmfq-reaction-warning{color:#94abbc;font-size:10px}@media(max-width:600px){.gmfq-reaction-metrics{grid-template-columns:1fr}}';
 style.textContent+='.gmfq-decision-bridge{border-top:1px solid #294456;margin-top:14px;padding-top:13px}.gmfq-decision-bridge h3{font:600 14px/1.4 Arial,sans-serif;margin:0 0 9px;color:#ebf2f6}.gmfq-decision-bridge>p{color:#a8bfcd;font:12px/1.55 Arial,sans-serif;margin:7px 0 10px}.gmfq-decision-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:11px}.gmfq-decision-cols>div{border-left:2px solid #577a90;background:#0b2231;padding:9px 11px;min-width:0}.gmfq-decision-cols>div:nth-child(2){border-color:#ae935d}.gmfq-decision-cols>div:nth-child(3){border-color:#699cba}.gmfq-decision-cols span{display:block;color:#9db3c3;font:10px/1.4 Arial,sans-serif}.gmfq-decision-cols strong{display:block;color:#e9f1f6;font:600 12px/1.5 Arial,sans-serif;margin:4px 0}.gmfq-decision-cols small{display:block;color:#b7cad6;font:11px/1.5 Arial,sans-serif;overflow-wrap:anywhere}.gmfq-decision-watch{padding:10px 0 0;margin-top:10px;border-top:1px solid #264254}.gmfq-decision-watch strong{color:#e5d199;font:600 12px/1.4 Arial,sans-serif}.gmfq-decision-watch p{color:#bcd0dc;font:12px/1.55 Arial,sans-serif;margin:4px 0 0}.gmfq-decision-bridge .gmfq-decision-context{color:#b1c4d1}.gmfq-decision-bridge .gmfq-decision-disclaimer{font-size:10px;color:#93aabb}@media(max-width:700px){.gmfq-decision-cols{grid-template-columns:1fr}}';
 style.textContent+='#gmfq-pair-research-path .gmfq-first-intro{margin:3px 0 8px;font-size:12px}'+
  '#gmfq-pair-full-research{border-top:1px solid #2b4857;margin:14px 0 12px;padding-top:12px;min-width:0}'+
  '#gmfq-pair-full-research>summary{font:600 12px/1.5 Arial,sans-serif;color:#e3ca8b;cursor:pointer;outline-offset:4px;list-style-position:inside;padding:6px 3px;overflow-wrap:anywhere}'+
  '#gmfq-pair-full-research>summary:hover{color:#f3dfae}'+
  '#gmfq-pair-full-research:not([open])>:not(summary){display:none!important}'+
  '#gmfq-pair-full-research[open]>summary{border-bottom:1px solid #294454;margin-bottom:10px}'+
  '#gmfq-pair-research-path>.gmfq-path-body>.gmfq-path-links{margin-top:12px}';
 style.textContent+='.gmfq-evidence-checklist{border-top:1px solid #294252;margin-top:13px;padding-top:11px}.gmfq-evidence-checklist h4{font:600 13px/1.45 Arial,sans-serif;color:#e8eef5;margin:0 0 6px}.gmfq-evidence-checklist .gmfq-evidence-intro{color:#aebfcd;font:11px/1.5 Arial,sans-serif;margin:0 0 9px}.gmfq-evidence-rows{display:grid;grid-template-columns:1fr;gap:0}.gmfq-evidence-row{padding:8px 0;border-top:1px solid #243f4e}.gmfq-evidence-row b{color:#e3ce95;font:600 11px/1.4 Arial,sans-serif}.gmfq-evidence-row:nth-child(2) b{color:#d7a3ac}.gmfq-evidence-row p{color:#c0d2dc;font:12px/1.5 Arial,sans-serif;margin:4px 0;overflow-wrap:anywhere}.gmfq-evidence-checklist .gmfq-evidence-provenance{color:#d0dfeb;font:11px/1.55 Arial,sans-serif;margin:9px 0 4px}.gmfq-evidence-checklist .gmfq-evidence-caution{color:#91a9b8;font:10px/1.55 Arial,sans-serif;margin:7px 0}';
 style.textContent+="/* Pair first reading · research-ledger hierarchy. No template changes.\n   Three provenance labels instead of a long undifferentiated metadata line;\n   lighter columns retain all evidence, disclosure and responsive behavior. */\n #gmfq-pair-research-path .gmfq-path-evidence{display:flex;flex-wrap:wrap;gap:5px 17px;\n   align-items:baseline;padding:9px 0 11px;border-bottom:1px solid #294454;\n   color:#b4cad8;font:11px/1.55 Arial,sans-serif}\n #gmfq-pair-research-path .gmfq-path-evidence span{min-width:0;overflow-wrap:anywhere}\n #gmfq-pair-research-path .gmfq-path-evidence b{font-weight:600;color:#c9d9e3}\n #gmfq-pair-research-path .gmfq-path-evidence[data-macro-state=\"HISTORICAL\"] [data-source=\"macro\"],\n #gmfq-pair-research-path .gmfq-path-evidence[data-macro-state=\"UNVERIFIED\"] [data-source=\"macro\"]{color:#e3c885}\n #gmfq-pair-research-path .gmfq-decision-bridge{border-top:0;margin-top:11px;padding-top:0}\n #gmfq-pair-research-path .gmfq-decision-bridge h3{font-size:15px}\n #gmfq-pair-research-path .gmfq-decision-cols{gap:0;border-top:1px solid #2b4656;\n   border-bottom:1px solid #2b4656}\n #gmfq-pair-research-path .gmfq-decision-cols>div{border-left:0;\n   border-right:1px solid #2b4656;background:transparent;padding:13px 15px 13px 12px}\n #gmfq-pair-research-path .gmfq-decision-cols>div:last-child{border-right:0}\n #gmfq-pair-research-path .gmfq-decision-cols strong{font-size:14px;line-height:1.45}\n #gmfq-pair-research-path .gmfq-decision-cols small{font-size:11px}\n @media(max-width:700px){\n   #gmfq-pair-research-path .gmfq-path-evidence{gap:3px 10px}\n   #gmfq-pair-research-path .gmfq-path-evidence span{width:100%}\n   #gmfq-pair-research-path .gmfq-decision-cols>div{border-right:0;\n     border-bottom:1px solid #2b4656;padding:12px 4px}\n   #gmfq-pair-research-path .gmfq-decision-cols>div:last-child{border-bottom:0}\n }";
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
  const oisDay=o?.as_of,oisState=officialPricingCurrent(o);
  const rateText='2Y/10Y '+(rateState?'ufficiali':'non correnti o incompleti')+
   ' · '+(rateDay||'n.d.');
  const indicative=(!oisState&&
    typeof window.GMFQ_OIS_RESEARCH_V1?.indicativeSixMonth==='function')?
    window.GMFQ_OIS_RESEARCH_V1.indicativeSixMonth(
      ois,romeTodayIso())[c]:null;
  const contextHint=indicative&&indicative.is_official_ois===false&&
    indicative.policy_delta_allowed===false&&indicative.pair_effect==='NONE'&&
    num(indicative.value)!==null?
    ' · futures 6M ≈ '+fmt(indicative.value,3)+'% · '+indicative.quote_as_of+
    ' (contesto, non Δ policy)':'';
  const oisText='pricing '+(oisState?'certificato':'non certificato')+
   ' · '+(oisDay||'n.d.')+contextHint;
  return '<article class="gmfq-path-leg"><strong>'+FLAG[c]+' '+c+' · '+BANK[c]+'</strong>'+
   '<small>'+htmlEscape(rateText)+'; '+htmlEscape(oisText)+'</small>'+
   '<div class="gmfq-path-links">'+Object.entries(labels).map(([r,n])=>
    '<button type="button" data-gmfq-study-route="'+r+'" data-gmfq-study-currency="'+c+
    '" aria-label="Apri '+htmlEscape(n)+' '+c+'">'+htmlEscape(n)+'</button>').join('')+
   '</div></article>';
 };
 let analysisExpanded=false;
 panel.addEventListener('toggle',event=>{
  if(event.target?.id==='gmfq-pair-full-research')analysisExpanded=event.target.open;
 },true);
 const refresh=()=>{
  if(frame.contentDocument!==doc||route()!=='coppie')return;
  if(doc.documentElement.dataset.pairState!=='READY')return;
  const marker=host.querySelector('.desk-kicker')?.textContent||'';
  const match=marker.match(/PAIR DEEP DIVE\s*[·:]\s*([A-Z]{6})/);
  const code=match?.[1];if(!code||!pairIds.has(code))return;
  if(panel.dataset.pair===code)return;
  panel.dataset.pair=code;
  const [a,b]=[code.slice(0,3),code.slice(3,6)];
  const fxDay=fxOk?fx.last_as_of:null;
  const differs=fxDay&&fxDay!==setup.price_asof;
  const macroDay=macroVerified?setup.macro_baseline_asof:null;
  const macroWarning=!macroVerified?
    'Integrità baseline Macro/Tassi NON VERIFICABILE tra D.json e motore: non usare la tesi come aggiornata. ':
    !fresh(macroDay,10)?
    'Baseline Macro/Tassi del motore ('+macroDay+') non corrente: la preferenza strutturale è storica e va rivalidata. ':'';
  const sourceMsg=differs?'Il fixing BCE è più recente dello snapshot della tesi. Il movimento dal '+
    setup.price_asof+' al '+fxDay+' non aggiorna automaticamente il giudizio del motore.':
    'La data del fixing e quella del motore coincidono, oppure il fixing più recente non è verificato.';
  // All diagnostics remain verbatim and source-derived; only reading order and
  // disclosure state change. The canonical model and 28 pair states are untouched.
  const comparison=pairMacroRatesComparison(code,setup.pairs[code],rates,ois,setup.price_asof,macroDay,proxy);
  const changes=pairWhatChangedEvidence(code,setup.pairs[code],rates,setup.price_asof,macroDay);
  const reaction=pairMarketReactionAudit(code,rates,fxOk?fx:null);
  const decision=pairThesisReactionBridge(code,setup.pairs[code],setup.price_asof,reaction,macroDay);
  panel.innerHTML='<h2 class="desk-panel-title">Percorso di ricerca · '+FLAG[a]+' '+a+' / '+FLAG[b]+' '+b+'</h2>'+
   '<div class="gmfq-path-body">'+
   '<p class="gmfq-first-intro">Sintesi di ricerca: prima la tesi, poi il setup e la reazione osservata. Il dettaglio sopra resta la lettura canonica della tesi.</p>'+
   '<div class="gmfq-path-evidence" data-macro-state="'+
   (!macroDay?'UNVERIFIED':fresh(macroDay,10)?'DATED':'HISTORICAL')+
   '" aria-label="Date e provenienza delle evidenze">'+
   '<span data-source="macro"><b>Baseline Macro/Tassi:</b> '+htmlEscape(macroDay||'non verificata')+
   (macroDay?(fresh(macroDay,10)?' · DATATA':' · STORICA'):' · WITHHELD')+'</span>'+
   '<span data-source="price"><b>Prezzo del modello:</b> '+htmlEscape(setup.price_asof)+'</span>'+
   '<span data-source="fixing"><b>Fixing BCE:</b> '+htmlEscape(fxDay||'non verificato')+'</span></div>'+
   decision+
   '<details id="gmfq-pair-full-research" class="gmfq-pair-full-research"'+(analysisExpanded?' open':'')+'>'+
   '<summary>Apri analisi completa · Macro/Rates, variazioni 2Y, audit prezzo e fonti</summary>'+
   comparison+changes+reaction+
   '<div class="gmfq-path-legs">'+leg(a)+leg(b)+'</div>'+
   '<p class="gmfq-path-warning">'+htmlEscape(macroWarning+sourceMsg)+' I futures indicativi non sono curve OIS e non determinano da soli un trade.</p>'+
   '</details>'+
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
/* Macro provenance lens: the 24 historical scores are NOT refreshed by more
   recent, individually dated Inflation/Labour thermometers. Read-only. */
function macroSeriesPeriod(raw){
 if(typeof raw!=='string'||!/^(20\d{2})-(0[1-9]|1[0-2])(?:-([0-2]\d|3[01]))?$/.test(raw))return null;
 const normalized=raw.length===7?raw+'-01':raw,day=new Date(normalized+'T00:00:00Z');
 if(!Number.isFinite(day.getTime())||day.toISOString().slice(0,10)!==normalized)return null;
 const today=romeTodayIso(),nowMonth=today.slice(0,7);
 if(raw.length===7){if(raw>nowMonth)return null}
 else if(normalized>today)return null;
 return raw;
}
function macroThermometerObservation(src){
 if(!src||typeof src!=='object'||!macroSeriesPeriod(src.as_of)||
    !src.validation||!['source','history','latest','transformation'].every(k=>src.validation[k]===true)||
    !src.source||!src.series_id||!src.label||
    num(src.latest_value)===null)return null;
 return {period:src.as_of,label:src.label,source:src.source,series:src.series_id,
   value:src.latest_value};
}
/* G8 Macro observed levels: research-only; independently dated data, no new scores. */
function macroStudyOverview(therm){
 const rows=FX.map(ccy=>{
  const record=therm?.currencies?.[ccy];
  const get=(key)=>{
   const raw=record?.[key],obs=macroThermometerObservation(raw);
   const validTransforms=key==='inflation'?
    ['reported_yoy_rate','yoy_pct_from_index','derived_yoy_from_index']:['level'];
   if(record?.status!=='ACTIVE'||!obs||!validTransforms.includes(raw.transformation)||
      !['M','Q'].includes(raw.frequency)||!Array.isArray(raw.history)||raw.history.length<24||
      num(raw.history.at(-1))===null||
      Math.abs(raw.history.at(-1)-obs.value)>0.00001||
      obs.value < -5||obs.value > 40)return null;
   return {value:obs.value,period:obs.period,frequency:raw.frequency};
  };
  return {ccy,inflation:get('inflation'),labour:get('labour')};
 });
 const count=rows.reduce((n,r)=>n+Number(!!r.inflation)+Number(!!r.labour),0);
 const cell=x=>x?'<strong>'+fmt(x.value,2)+'%</strong><small>'+htmlEscape(x.period)+
  ' · '+(x.frequency==='Q'?'trimestrale':'mensile')+'</small>':
  '<strong>—</strong><small>non verificabile</small>';
 const html='<div class="gmfq-macro-g8-table" role="table" aria-label="G8 inflazione e disoccupazione, livelli e periodi">'+
  '<div class="gmfq-macro-g8-row gmfq-macro-g8-head" role="row"><span>Valuta</span><span>Inflazione YoY</span><span>Disoccupazione</span></div>'+
  rows.map(r=>'<div class="gmfq-macro-g8-row" role="row" data-g8-ccy="'+r.ccy+
   '" data-inflation-status="'+(r.inflation?'OBSERVED':'MISSING')+
   '" data-labour-status="'+(r.labour?'OBSERVED':'MISSING')+'"><div><strong>'+
   FLAG[r.ccy]+' '+r.ccy+'</strong></div><div>'+cell(r.inflation)+
   '</div><div>'+cell(r.labour)+'</div></div>').join('')+'</div>';
 return {rows,count,html};
}
function macroBaselineValid(model,therm){
 return canonicalMacroBaselineAsOf(model)!==null&&
  therm?.schema_version==='GMFQ_MACRO_HEATMAP_V1'&&therm.status==='ACTIVE'&&
  therm.freshness_rule==='Use per-series as_of only; no single currency as_of is authoritative when inflation and unemployment release dates differ.'&&
  FX.every(c=>therm.currencies?.[c]?.status==='ACTIVE');
}
async function mountMacroSourceLens(doc){
 if(route()!=='macro'||frame.contentDocument!==doc)return;
 const hero=doc.querySelector('.desk-hero'),main=doc.querySelector('.desk-main');
 if(!hero||!main||doc.getElementById('gmfq-macro-source-lens'))return;
 const panel=doc.createElement('section');
 panel.id='gmfq-macro-source-lens';panel.className='desk-panel';
 panel.dataset.auditStatus='LOADING';
 panel.setAttribute('aria-label','Provenienza e data delle evidenze Macro');
 panel.innerHTML='<h2 class="desk-panel-title">Macro · origine delle evidenze</h2>'+
  '<p class="gmfq-macro-provenance-fallback">Controllo delle date dei dati...</p>';
 hero.insertAdjacentElement('afterend',panel);
 const inputs=await Promise.allSettled([feed('D.json'),feed('MACRO_THERMOMETER_DATA.json')]);
 if(route()!=='macro'||frame.contentDocument!==doc)return;
 const model=inputs[0].status==='fulfilled'?inputs[0].value:null;
 const thermometer=inputs[1].status==='fulfilled'?inputs[1].value:null;
 const fail=()=>{
  panel.dataset.auditStatus='WITHHELD';
  panel.innerHTML='<h2 class="desk-panel-title">Macro · origine delle evidenze</h2>'+
   '<p class="gmfq-macro-provenance-fallback">Date o dati del modello e dei termometri non verificabili. Non è possibile dichiarare aggiornati gli score né ricostruire nuove valutazioni.</p>';
 };
 if(!macroBaselineValid(model,thermometer)){fail();return}
 const style=doc.createElement('style');style.id='gmfq-macro-source-lens-style';
 style.textContent=
  '#gmfq-macro-source-lens{margin:0 0 14px;min-width:0}'+
  '#gmfq-macro-source-lens .gmfq-macro-body{padding:12px 16px 14px;min-width:0}'+
  '#gmfq-macro-source-lens .gmfq-macro-takeaway{color:#e4edf4;font:600 13px/1.55 Arial,sans-serif;margin:0 0 10px;overflow-wrap:anywhere}'+
 '#gmfq-macro-source-lens .gmfq-macro-state{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#e2c383;font:600 11px/1.5 Arial,sans-serif;border-top:1px solid #2c485a;padding-top:9px}'+
  '#gmfq-macro-source-lens .gmfq-macro-intro{color:#c0cfdb;font:12px/1.6 Arial,sans-serif;margin:7px 0 10px}'+
  '#gmfq-macro-source-lens .gmfq-macro-choice{display:flex;align-items:center;gap:9px;flex-wrap:wrap;color:#a9bfce;font:11px Arial,sans-serif;margin:0 0 9px}'+
  '#gmfq-macro-source-lens .gmfq-macro-choice select{background:#122c3b;border:1px solid #3a5367;border-radius:5px;color:#e7edf3;font:12px Arial,sans-serif;padding:7px;max-width:100%}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-table{border:1px solid #2c485a;border-radius:6px;overflow:hidden;margin:10px 0}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row{display:grid;grid-template-columns:minmax(62px,.65fr) repeat(2,minmax(0,1fr));border-bottom:1px solid #294455}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row:last-child{border-bottom:0}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row>div,#gmfq-macro-source-lens .gmfq-macro-g8-row>span{min-width:0;padding:7px 9px;overflow-wrap:anywhere}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row strong{display:block;color:#e6edf4;font:600 12px/1.45 Arial,sans-serif;font-variant-numeric:tabular-nums}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row small{display:block;color:#a2b9c8;font:10px/1.4 Arial,sans-serif}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-head{background:#122c3d;color:#b9cede;font:600 11px/1.4 Arial,sans-serif}'+
  '@media(max-width:600px){#gmfq-macro-source-lens .gmfq-macro-g8-row{grid-template-columns:minmax(52px,.6fr) repeat(2,minmax(0,1fr))}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row>div,#gmfq-macro-source-lens .gmfq-macro-g8-row>span{padding:7px 4px}'+
  '#gmfq-macro-source-lens .gmfq-macro-g8-row strong{font-size:11px}#gmfq-macro-source-lens .gmfq-macro-g8-row small{font-size:9px}}'+
  '#gmfq-macro-source-lens .gmfq-macro-reading{color:#e4cf9a;font:600 12px/1.6 Arial,sans-serif;margin:8px 0 5px;overflow-wrap:anywhere}'+
  '#gmfq-macro-source-lens .gmfq-macro-dynamics{display:flex;gap:5px 16px;flex-wrap:wrap;margin:7px 0 5px;border-top:1px solid #2a4557;padding-top:8px}'+
  '#gmfq-macro-source-lens .gmfq-macro-dynamic{font:11px/1.55 Arial,sans-serif;color:#ccdae4;min-width:0;overflow-wrap:anywhere}'+
  '#gmfq-macro-source-lens .gmfq-macro-dynamic strong{color:#e6edf3;font-weight:600}'+
  '#gmfq-macro-source-lens .gmfq-macro-dynamic b{color:#dec58e;font-weight:600}'+
  '#gmfq-macro-source-lens .gmfq-macro-dynamics-note{font:10px/1.5 Arial,sans-serif;color:#9eb7c8;margin:4px 0 2px}'+
  '@media(max-width:650px){#gmfq-macro-source-lens .gmfq-macro-dynamics{display:block}#gmfq-macro-source-lens .gmfq-macro-dynamic{display:block;margin-bottom:3px}}'+
  '#gmfq-macro-source-lens #gmfq-macro-observation-details{border-top:1px solid #304b5a;padding-top:8px;margin-top:10px}'+
  '#gmfq-macro-source-lens #gmfq-macro-observation-details>summary{cursor:pointer;color:#dec58d;font:600 12px/1.5 Arial,sans-serif;padding:4px 0;outline-offset:4px}'+
  '#gmfq-macro-source-lens #gmfq-macro-observation-details:not([open])>:not(summary){display:none!important}'+
  '#gmfq-macro-source-lens .gmfq-macro-measures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}'+
  '#gmfq-macro-source-lens .gmfq-macro-observation{min-width:0;border-top:1px solid #2c485a;padding:9px 0 0}'+
  '#gmfq-macro-source-lens .gmfq-macro-observation strong{display:block;color:#e3edf4;font:600 12px/1.5 Arial,sans-serif}'+
  '#gmfq-macro-source-lens .gmfq-macro-observation p{color:#a8bdcb;font:11px/1.5 Arial,sans-serif;margin:4px 0;overflow-wrap:anywhere}'+
  '#gmfq-macro-source-lens .gmfq-macro-guard{color:#91a9bb;font:10px/1.6 Arial,sans-serif;margin:9px 0 0}'+
  '#gmfq-macro-source-lens .gmfq-macro-provenance-fallback{padding:10px 16px;color:#d8c48d;font:12px/1.55 Arial,sans-serif}'+
  '@media(max-width:650px){#gmfq-macro-source-lens .gmfq-macro-body{padding:11px 12px}'+
  '#gmfq-macro-source-lens .gmfq-macro-measures{grid-template-columns:1fr}'+
  '#gmfq-macro-source-lens .gmfq-macro-observation{padding-top:7px}}';
 doc.head.appendChild(style);
 const baselineDate=model.asOf;
 const baselineFresh=fresh(baselineDate,10);
 const currentQuery=new URLSearchParams(location.hash.split('?')[1]||'').get('ccy');
 const options=FX.map(c=>'<option value="'+c+'">'+FLAG[c]+' '+c+'</option>').join('');
 const overview=macroStudyOverview(thermometer);
 panel.dataset.observedStudyCount=String(overview.count);
 panel.dataset.auditStatus='READ_ONLY';
 panel.dataset.baselineAsOf=baselineDate;
 panel.innerHTML='<h2 class="desk-panel-title">Macro · modello storico vs osservazioni</h2>'+
  '<div class="gmfq-macro-body"><p class="gmfq-macro-takeaway">Gli score sono uno snapshot del modello: i periodi di Inflazione e Lavoro non aggiornano i 24 score, i cicli economici o i bias FX.</p>'+
   '<div class="gmfq-macro-state">'+
  '24 score Growth/Labour/Inflation · baseline '+htmlEscape(baselineDate)+
  (baselineFresh?' · snapshot datato':' · NON CORRENTE, da rivalidare')+'</div>'+
  '<p class="gmfq-macro-intro">G8: livelli osservati nelle serie disponibili, con date e frequenze indipendenti. Non sono nuove pubblicazioni sincronizzate, revisioni point-in-time certificate o nuovi score Growth.</p>'+
  '<div id="gmfq-macro-g8-study" data-core-effect="NONE" data-bias-effect="NONE" data-observation-count="'+overview.count+'">'+overview.html+'</div>'+
  '<p class="gmfq-macro-intro">Seleziona la valuta per direzione, accelerazione e fonti delle osservazioni.</p>'+
  '<label class="gmfq-macro-choice" for="gmfq-macro-provenance-currency">Valuta <select id="gmfq-macro-provenance-currency" aria-label="Valuta delle osservazioni Macro">'+options+'</select></label>'+
  '<p class="gmfq-macro-reading" id="gmfq-macro-reading" aria-live="polite">Periodi in verifica…</p>'+
  '<div id="gmfq-macro-dynamics" class="gmfq-macro-dynamics" aria-label="Direzione e accelerazione delle osservazioni validate"></div>'+
  '<p class="gmfq-macro-dynamics-note">Direzione e accelerazione si riferiscono alla singola serie osservata e al suo periodo, non alla forza della valuta. Nessun aggiornamento dei 24 score.</p>'+
  '<details id="gmfq-macro-observation-details"><summary>Apri osservazioni e fonti · Inflazione e Lavoro</summary>'+
  '<div id="gmfq-macro-source-details" class="gmfq-macro-measures" aria-live="polite"></div>'+
  '<p class="gmfq-macro-guard">Le date dei termometri sono periodi di riferimento, non necessariamente date di pubblicazione o prove point-in-time. Eventuali etichette legacy «CORRENTE COMPLETO» non certificano la freschezza degli score al giorno di oggi. Crescita: nessun nuovo score certificato.</p></details></div>';
 const select=panel.querySelector('select'),details=panel.querySelector('#gmfq-macro-source-details'),
  reading=panel.querySelector('#gmfq-macro-reading'),
  dynamics=panel.querySelector('#gmfq-macro-dynamics');
 const measure=(label,obs)=>{
  if(!obs)return '<div class="gmfq-macro-observation"><strong>'+label+' · dato WITHHELD</strong>'+
    '<p>Osservazione non verificabile nel termometro, nessun livello ricostruito.</p></div>';
  return '<div class="gmfq-macro-observation"><strong>'+htmlEscape(label)+
   ' · '+htmlEscape(obs.label)+'</strong><p>Valore dataset: '+fmt(obs.value,2)+
   ' · periodo '+htmlEscape(obs.period)+'</p><p>Fonte '+htmlEscape(obs.source)+
   ' · serie '+htmlEscape(obs.series)+'</p></div>';
 };
 function show(ccy){
  if(!FX.includes(ccy))return;
  select.value=ccy;
  panel.dataset.selectedCurrency=ccy;
  const t=thermometer.currencies[ccy];
  const inflation=macroThermometerObservation(t.inflation),labour=macroThermometerObservation(t.labour);
  reading.textContent=FLAG[ccy]+' '+ccy+' · Inflazione: '+(inflation?fmt(inflation.value,2)+'% · '+inflation.period:'non verificabile')+
   ' · Disoccupazione: '+(labour?fmt(labour.value,2)+'% · '+labour.period:'non verificabile');
  // Display only the dynamics of an already validated observation. Unknown
  // direction/acceleration terms are WITHHELD, not inferred.
  const direction={SALE:'sale',SCENDE:'scende',STABILE:'stabile'},
    speed={ACCELERA:'accelera',RALLENTA:'rallenta',STABILE:'stabile'};
  const dynamic=(title,obs,raw)=>{
    const dir=obs&&direction[raw?.direction],acc=obs&&speed[raw?.acceleration];
    if(!dir||!acc)return '<span class="gmfq-macro-dynamic" data-macro-metric="'+title+
      '" data-dynamic-status="WITHHELD"><strong>'+title+'</strong> · dinamica non verificabile</span>';
    return '<span class="gmfq-macro-dynamic" data-macro-metric="'+title+
      '" data-dynamic-status="OBSERVED" data-direction="'+raw.direction+
      '" data-acceleration="'+raw.acceleration+'" data-as-of="'+htmlEscape(obs.period)+'">'+
      '<strong>'+title+'</strong> · <b>'+dir+'</b> · ritmo '+acc+
      ' · periodo '+htmlEscape(obs.period)+'</span>';
  };
  dynamics.innerHTML=dynamic('Inflazione',inflation,t.inflation)+
    dynamic('Lavoro',labour,t.labour);
  details.innerHTML=measure('Inflazione',inflation)+measure('Lavoro',labour);
 }
 show(FX.includes(currentQuery)?currentQuery:'USD');
 select.addEventListener('change',()=>{
  const c=select.value;if(!FX.includes(c))return;
  show(c);
  const native=doc.querySelector('button[data-ccy="'+c+'"]');
  if(native)native.click();
  history.replaceState(history.state,'','#/macro?ccy='+c);
 });
 // Keep the provenance with the native G8 country selection.
 doc.addEventListener('click',event=>{
  if(panel.contains(event.target))return;
  const native=event.target.closest('button[data-ccy]');
  if(native&&FX.includes(native.dataset.ccy))show(native.dataset.ccy);
 });
}

/* Read-only Screener diagnosis of canonical NON VALUTABILE decisions.
   No score, pair ranking, official rates, OIS or trading judgment is recalculated. */
function screenerBlockerReason(code,record){
 const src=record?.setup,frame=record?.decision_frame;
 if(!/^[A-Z]{6}$/.test(code)||!src||!frame||
    src.quality!=='NON VALUTABILE'||src.structuralFav!==null)return null;
 const sides=[code.slice(0,3),code.slice(3,6)];
 const macro=frame.macroSide,policy=frame.policySide,gap=frame.structural?.ratesGap;
 if(frame.quality==='PILASTRI DIVISI'&&sides.includes(macro)&&
    sides.includes(policy)&&macro!==policy)
   return {category:'CONFLICT',
    explanation:'Macro: '+(FLAG[macro]||'')+' '+macro+
    ' · Tassi/CB: '+(FLAG[policy]||'')+' '+policy};
 if(frame.quality==='SEPARAZIONE RATES MATERIALE'&&
    macro===null&&policy===null&&gap?.material===true&&
    sides.includes(gap.side)&&num(gap.bp)!==null)
   return {category:'RATES_ONLY',
    explanation:'Spread 2Y ≈ '+fmt(Math.abs(gap.bp),0)+' pb verso '+gap.side+
    ' · livello, non bias'};
 if(frame.quality==='NESSUN CONTRASTO'&&macro===null&&policy===null)
   return {category:'INSUFFICIENT',
    explanation:'Macro e Tassi/CB non distinguono chiaramente le valute'};
 return null; // fail closed on unknown or inconsistent model semantics
}
async function mountScreenerBlockers(doc){
 if(route()!=='screener'||frame.contentDocument!==doc)return;
 const main=doc.querySelector('.desk-main'),hero=doc.querySelector('.desk-hero');
 if(!main||!hero||doc.getElementById('gmfq-screener-blockers'))return;
 const panel=doc.createElement('section');
 panel.id='gmfq-screener-blockers';panel.className='desk-panel';
 panel.dataset.diagnosisStatus='LOADING';
 panel.setAttribute('aria-label','Motivi dei setup FX non valutabili');
 panel.innerHTML='<h2 class="desk-panel-title">Perché alcune coppie non sono valutabili</h2>'+
  '<p class="gmfq-blocker-message">Verifica dei giudizi canonici…</p>';
 hero.insertAdjacentElement('afterend',panel);
 let setup=null;
 try{setup=await feed('PAIR_SETUP_OPERATIONAL_VIEW.json')}
 catch(e){console.warn('[GMFQ Screener diagnoses unavailable]',String(e))}
 if(route()!=='screener'||frame.contentDocument!==doc)return;
 const records=setup?.pairs;
 const valid=setup?.schema==='GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1'&&
  setup?.status==='CURRENT_CANONICAL_ENGINE'&&setup.pair_count===28&&
  records&&Object.keys(records).length===28&&
  /^\d{4}-\d{2}-\d{2}$/.test(setup.macro_baseline_asof||'')&&
  setup.thesis_is_not_entry===true&&setup.entry_level_published===false;
 const unknown=()=>{
  panel.dataset.diagnosisStatus='WITHHELD';
  panel.innerHTML='<h2 class="desk-panel-title">Motivi dei setup non valutabili</h2>'+
   '<p class="gmfq-blocker-message">Classificazione non verificabile dal feed canonico. Nessun giudizio ricostruito.</p>';
 };
 if(!valid){unknown();return}
 const rows=Object.entries(records).filter(([,r])=>r?.setup?.quality==='NON VALUTABILE');
 if(rows.length!==setup.quality_distribution?.['NON VALUTABILE']){unknown();return}
 // Reconcile all 28 source judgments before presenting any "what to review".
 // Review-only states are not trade candidates and are never re-ranked here.
 const categoriesKnown=['DA CONFERMARE','DA MONITORARE','CON RISCHI','NON VALUTABILE'];
 const counts=Object.fromEntries(categoriesKnown.map(q=>[q,0]));
 for(const record of Object.values(records)){
   const quality=record?.setup?.quality;
   if(!categoriesKnown.includes(quality)){unknown();return}
   counts[quality]++;
 }
 const distribution=setup.quality_distribution;
 if(!distribution||typeof distribution!=='object'||Array.isArray(distribution)||
    Object.entries(distribution).some(([k,v])=>
      !categoriesKnown.includes(k)||!Number.isInteger(v)||v<0)||
    categoriesKnown.some(k=>counts[k]!==
      (Object.hasOwn(distribution,k)?distribution[k]:0))||
    categoriesKnown.reduce((v,k)=>v+counts[k],0)!==28){unknown();return}
 const reviewPairs=Object.entries(records)
   .filter(([,record])=>['DA CONFERMARE','DA MONITORARE'].includes(record.setup.quality))
   .map(([code,record])=>({code,quality:record.setup.quality}))
   .sort((a,b)=>a.code.localeCompare(b.code));
 const groups={CONFLICT:[],RATES_ONLY:[],INSUFFICIENT:[]};
 for(const [code,record] of rows){
  const explanation=screenerBlockerReason(code,record);
  if(!explanation||!groups[explanation.category]){unknown();return}
  groups[explanation.category].push({code,...explanation});
 }
 const style=doc.createElement('style');
 style.id='gmfq-screener-blockers-css';
 style.textContent=
 '#gmfq-screener-blockers{margin:0 0 14px;min-width:0}'+
 '#gmfq-screener-blockers .gmfq-blocker-priority{margin:0;padding:11px 16px 3px;font:600 13px/1.55 Arial,sans-serif;color:#e5edf3;overflow-wrap:anywhere}'+
 '#gmfq-screener-blockers .gmfq-blocker-intro{margin:0;padding:2px 16px 8px;font:11px/1.6 Arial,sans-serif;color:#bfd0dd}'+
 '#gmfq-screener-blockers .gmfq-blocker-overview{display:flex;gap:6px 17px;flex-wrap:wrap;margin:0;padding:6px 16px;color:#d9e3eb;font:600 12px/1.55 Arial,sans-serif}'+
 '#gmfq-screener-blockers .gmfq-screener-quality{display:flex;flex-wrap:wrap;gap:4px 16px;margin:3px 16px 7px;padding:8px 0;border-top:1px solid #294657;border-bottom:1px solid #294657;font:11px/1.5 Arial,sans-serif;color:#a9c5d2}'+
 '#gmfq-screener-blockers .gmfq-screener-quality span{min-width:0}'+
 '#gmfq-screener-blockers .gmfq-screener-quality b{color:#e2edf4;font-weight:600;font-variant-numeric:tabular-nums}'+
 '#gmfq-screener-blockers .gmfq-screener-review{padding:4px 16px 10px;min-width:0}'+
 '#gmfq-screener-blockers .gmfq-screener-review-title{font:600 11px/1.45 Arial,sans-serif;color:#e0ca95;margin:0 0 5px}'+
 '#gmfq-screener-blockers .gmfq-screener-review-line{display:flex;gap:6px 15px;flex-wrap:wrap;align-items:baseline}'+
 '#gmfq-screener-blockers .gmfq-review-pair{font:600 11px/1.5 Arial,sans-serif;color:#e4edf4;cursor:pointer;white-space:normal;text-align:left;background:transparent;border:0;border-bottom:1px dotted #607a89;padding:2px 0;outline-offset:3px}'+
 '#gmfq-screener-blockers .gmfq-review-pair small{font:10px/1.45 Arial,sans-serif;color:#a8bac8;margin-left:4px}'+
 '#gmfq-screener-blockers .gmfq-review-pair:hover,#gmfq-screener-blockers .gmfq-review-pair:focus-visible{color:#e4c887;outline:2px solid #dfc58c;outline-offset:3px}'+
 '#gmfq-screener-blockers .gmfq-screener-review-note{font:10px/1.5 Arial,sans-serif;color:#9cb4c3;margin:6px 0 0}'+
 '#gmfq-screener-blockers .gmfq-blocker-overview span{min-width:0;overflow-wrap:anywhere}'+
 '#gmfq-screener-blockers #gmfq-blocker-details{margin:7px 0 0;border-top:1px solid #324b59;padding:10px 0 0;min-width:0}'+
 '#gmfq-screener-blockers #gmfq-blocker-details>summary{cursor:pointer;color:#e0c78c;font:600 12px/1.5 Arial,sans-serif;padding:5px 16px;outline-offset:4px}'+
 '#gmfq-screener-blockers #gmfq-blocker-details:not([open])>:not(summary){display:none!important}'+
 
 '#gmfq-screener-blockers .gmfq-blocker-date{display:flex;flex-wrap:wrap;gap:4px 17px;border-top:1px solid #2c4656;margin:6px 16px 0;padding:9px 0 10px;color:#d7bf87;font:11px/1.5 Arial,sans-serif}'+
 '#gmfq-screener-blockers .gmfq-blocker-date span{min-width:0;overflow-wrap:anywhere}'+
 '#gmfq-screener-blockers .gmfq-blocker-brief{padding:0 16px 7px;color:#9eb4c4;font:11px/1.5 Arial,sans-serif}'+
 
 '#gmfq-screener-blockers .gmfq-blocker-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:5px 16px 13px}'+
 '#gmfq-screener-blockers .gmfq-blocker-group{min-width:0;border-top:1px solid #3a5363;padding-top:9px}'+
 '#gmfq-screener-blockers .gmfq-blocker-group h3{font:600 12px/1.5 Arial,sans-serif;color:#e4edf2;margin:0 0 4px}'+
 '#gmfq-screener-blockers .gmfq-blocker-group p{color:#9eb6c5;font:11px/1.5 Arial,sans-serif;margin:0 0 7px}'+
 '#gmfq-screener-blockers .gmfq-blocker-pair{display:flex;align-items:flex-start;gap:8px;width:100%;text-align:left;background:transparent;border:0;border-top:1px solid #243d4b;color:#bfcfdb;padding:9px 1px;cursor:pointer}'+
 '#gmfq-screener-blockers .gmfq-blocker-pair:hover,#gmfq-screener-blockers .gmfq-blocker-pair:focus-visible{background:#193448;outline-offset:2px}'+
 '#gmfq-screener-blockers .gmfq-blocker-code{color:#eef2f6;font:600 12px/1.4 Arial,sans-serif;min-width:79px}'+
 '#gmfq-screener-blockers .gmfq-blocker-explain{flex:1;min-width:0;font:11px/1.45 Arial,sans-serif;overflow-wrap:anywhere}'+
 '#gmfq-screener-blockers .gmfq-blocker-link{color:#d9c38d}'+
 '#gmfq-screener-blockers .gmfq-blocker-note{margin:0;border-top:1px solid #29404f;padding:10px 16px;color:#91aabc;font:10px/1.55 Arial,sans-serif}'+
 '#gmfq-screener-blockers .gmfq-blocker-message{padding:10px 16px;font:12px/1.55 Arial,sans-serif;color:#d2c396}'+
 '@media(max-width:950px){#gmfq-screener-blockers .gmfq-blocker-grid{grid-template-columns:1fr}}'+
 '@media(max-width:600px){#gmfq-screener-blockers .gmfq-blocker-priority{padding:10px 12px 3px;font-size:12px}'+
 '#gmfq-screener-blockers .gmfq-blocker-intro{padding:2px 12px 7px}'+
 '#gmfq-screener-blockers .gmfq-blocker-date{margin:6px 12px 0;padding:8px 0 9px;gap:4px}'+
 '#gmfq-screener-blockers .gmfq-blocker-date span{width:100%}'+
 '#gmfq-screener-blockers .gmfq-blocker-grid{padding:5px 12px 10px}'+
 '#gmfq-screener-blockers .gmfq-blocker-overview{padding:7px 12px;gap:5px 12px}'+
 '#gmfq-screener-blockers .gmfq-screener-quality{margin:3px 12px 7px;gap:3px 12px}'+
 '#gmfq-screener-blockers .gmfq-screener-review{padding:4px 12px 10px}'+
 '#gmfq-screener-blockers .gmfq-screener-review-line{gap:4px 12px}'+
 '#gmfq-screener-blockers .gmfq-blocker-brief{padding:0 12px 7px}'+
 '#gmfq-screener-blockers #gmfq-blocker-details>summary{padding:5px 12px}'+
 
 '#gmfq-screener-blockers .gmfq-blocker-note{padding:9px 12px}}';
 doc.head.appendChild(style);
 const categories=[
  ['CONFLICT','Pilastri in conflitto','Macro e Tassi/CB favoriscono valute opposte'],
  ['RATES_ONLY','Differenziale 2Y, tesi non validata','Il livello dei rendimenti non basta per assegnare un bias'],
  ['INSUFFICIENT','Differenziazione insufficiente','Nessun vantaggio strutturale robusto']
 ];
 const card=([id,title,note])=>'<section class="gmfq-blocker-group" data-reason="'+id+'">'+
  '<h3>'+title+' · '+groups[id].length+'</h3><p>'+note+'</p>'+
  groups[id].map(x=>'<button type="button" class="gmfq-blocker-pair" data-pair="'+x.code+
   '" aria-label="Apri analisi '+x.code+'"><span class="gmfq-blocker-code">'+
   FLAG[x.code.slice(0,3)]+' '+FLAG[x.code.slice(3,6)]+' '+x.code+
   '</span><span class="gmfq-blocker-explain">'+htmlEscape(x.explanation)+
   '</span><span class="gmfq-blocker-link">↗</span></button>').join('')+'</section>';
 const baselineFresh=fresh(setup.macro_baseline_asof,10);
 panel.dataset.diagnosisStatus='READ_ONLY';
 panel.dataset.macroBaselineAsOf=setup.macro_baseline_asof;
 panel.dataset.modelPriceAsOf=setup.price_asof||'';
 panel.dataset.reviewCount=String(reviewPairs.length);
 panel.dataset.qualityCoverage=String(categoriesKnown.reduce((v,k)=>v+counts[k],0));
 panel.innerHTML='<h2 class="desk-panel-title">Screener G8 · 28 coppie · lettura del motore</h2>'+
  '<p class="gmfq-blocker-priority">Le coppie senza una tesi coerente restano NON VALUTABILI: Macro e Tassi/CB non bastano a renderle operative.</p>'+
   '<p class="gmfq-blocker-intro">Classificazione del motore canonico, non graduatoria di opportunità di trade.</p>'+
  '<div class="gmfq-screener-quality" aria-label="Distribuzione esatta dei 28 setup FX">'+
   '<span data-quality="DA CONFERMARE"><b>'+counts['DA CONFERMARE']+'</b> da confermare</span>'+
   '<span data-quality="DA MONITORARE"><b>'+counts['DA MONITORARE']+'</b> da monitorare</span>'+
   '<span data-quality="CON RISCHI"><b>'+counts['CON RISCHI']+'</b> con rischi</span>'+
   '<span data-quality="NON VALUTABILE"><b>'+counts['NON VALUTABILE']+'</b> non valutabili</span></div>'+
  '<div class="gmfq-screener-review" data-ranking="NONE" data-trade-signals="NONE">'+
   '<p class="gmfq-screener-review-title">Stati da verificare nel motore · '+reviewPairs.length+' coppie</p>'+
   '<div class="gmfq-screener-review-line">'+reviewPairs.map(x=>
     '<button type="button" class="gmfq-review-pair" data-pair="'+x.code+
     '" data-quality="'+x.quality+'" aria-label="Apri analisi '+x.code+
     ', stato '+x.quality+'">'+
     FLAG[x.code.slice(0,3)]+' '+FLAG[x.code.slice(3,6)]+' '+x.code+
     ' <small>'+x.quality.toLowerCase()+' ↗</small></button>').join('')+'</div>'+
   '<p class="gmfq-screener-review-note">Solo stati da rivalutare, non proposte di ingresso. La baseline Macro resta storica: '+
   htmlEscape(setup.macro_baseline_asof)+'. Nessun ordine di attrattività, segnale o timing.</p></div>'+
  '<p class="gmfq-blocker-intro">Restano NON VALUTABILI '+rows.length+' coppie: principali motivi sotto.</p>'+
  '<div class="gmfq-blocker-overview" aria-label="Cause delle coppie non valutabili">'+
  '<span>Macro vs Tassi/CB: '+groups.CONFLICT.length+'</span>'+
  '<span>Differenziale 2Y senza tesi: '+groups.RATES_ONLY.length+'</span>'+
  '<span>Vantaggio insufficiente: '+groups.INSUFFICIENT.length+'</span></div>'+
  '<div class="gmfq-blocker-date" aria-label="Provenienza e date del modello">'+
  '<span data-source="macro">Baseline Macro/Tassi: '+htmlEscape(setup.macro_baseline_asof)+
  (baselineFresh?' · data entro il limite di freschezza':' · NON CORRENTE, tesi da rivalidare')+'</span>'+
  '<span data-source="price">Prezzi del motore: '+htmlEscape(setup.price_asof||'non verificati')+'</span></div>'+
  '<p class="gmfq-blocker-brief">Motivazioni individuali e accesso alle Pair Deep Dive nel dettaglio espandibile.</p>'+
  '<details id="gmfq-blocker-details"><summary>Apri le '+rows.length+' coppie e le motivazioni complete</summary>'+
  '<div class="gmfq-blocker-grid">'+categories.map(card).join('')+'</div>'+
  '<p class="gmfq-blocker-note">Lettura descrittiva e storica, non graduatoria di trade. Lo spread 2Y è solo contesto di livello: non crea da solo una preferenza FX. Nessuna promozione di fonte, ricalcolo di score, modifica dei 28 setup o segnale operativo.</p></details>';
 panel.addEventListener('click',event=>{
  const button=event.target.closest('button.gmfq-blocker-pair[data-pair],button.gmfq-review-pair[data-pair]');
  if(button&&panel.contains(button)&&records[button.dataset.pair])
   go('#/coppie?pair='+button.dataset.pair);
 });
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


/* Valute source compass: one quiet, read-only disclosure line above the native
   currency study. Never recompute G8 strength, price ranks or ICE DXY. */
function valuteFxSourceStatus(fx){
 const currencies=fx?.currencies||[];
 const row=fx?.rows?.at(-1);
 const day=fx?.last_as_of;
 const ok=fx?.schema==='GMFQ_ECB_G8_PRICE_HISTORY_V1'&&
   fx.status==='CURRENT_OFFICIAL_HISTORY'&&fx.pair_count===28&&
   Array.isArray(fx.rows)&&fx.rows.length>1&&
   currencies.length===8&&FX.every(c=>currencies.includes(c)&&num(row?.[c])!==null&&row[c]>0)&&
   row?.Date===day&&/^\d{4}-\d{2}-\d{2}$/.test(day||'')&&
   row.EUR===1&&fresh(day,4);
 return ok?{status:'OFFICIAL_FIXING_RECENT',asof:day}:
   {status:'WITHHELD',asof:null};
}

/* Relative performance of the eight currencies, using only two official ECB
   fixing observations per horizon. This is observed FX momentum, NOT the frozen
   Macro model, a COT/rates composite, an estimate of expected return or a signal. */
function valuteRelativeFixingRanks(fx,lookback){
 if(![5,20].includes(lookback)||
    valuteFxSourceStatus(fx).status!=='OFFICIAL_FIXING_RECENT'||
    !Array.isArray(fx.rows)||fx.row_count!==fx.rows.length||
    fx.rows.length<=lookback)return null;
 const older=fx.rows.at(-lookback-1),recent=fx.rows.at(-1);
 if(!older||!recent||!/^20\d{2}-\d{2}-\d{2}$/.test(older.Date||'')||
    recent.Date!==fx.last_as_of||older.Date>=recent.Date)return null;
 const changes=[];
 for(const c of FX){
   const start=num(older[c]),finish=num(recent[c]);
   if(start===null||finish===null||start<=0||finish<=0)return null;
   // ECB fixing: currency units per 1 EUR. Invert to express currency value.
   changes.push({ccy:c,logChange:-Math.log(finish/start)});
 }
 const basket=changes.reduce((total,x)=>total+x.logChange,0)/changes.length;
 const items=changes.map(x=>({ccy:x.ccy,
   percent:(Math.exp(x.logChange-basket)-1)*100})).sort((a,b)=>
     b.percent-a.percent||a.ccy.localeCompare(b.ccy));
 if(items.length!==8||new Set(items.map(x=>x.ccy)).size!==8||
    items.some(x=>!Number.isFinite(x.percent)))return null;
 return {items,from:older.Date,asof:recent.Date,lookback,
   source:'ECB_G8_PRICE_HISTORY',basis:'EQUAL_WEIGHT_G8'};
}
/* Comparing overlapping ECB fixing horizons does not establish a
   momentum turning point, macro change or a trade recommendation. */
function valuteHorizonFirstRead(fx,days){
 if(![5,20].includes(days))return null;
 const primary=valuteRelativeFixingRanks(fx,days),
       otherDays=days===5?20:5,
       comparison=valuteRelativeFixingRanks(fx,otherDays);
 if(!primary||!comparison||primary.asof!==comparison.asof||
    primary.items.length!==8||comparison.items.length!==8)return null;
 const leader=primary.items[0];
 if(!leader)return null;
 const otherIndex=comparison.items.findIndex(x=>x.ccy===leader.ccy);
 if(otherIndex<0||otherIndex>=8)return null;
 const other=comparison.items[otherIndex];
 if(!Number.isFinite(leader.percent)||!Number.isFinite(other.percent))return null;
 return {ccy:leader.ccy,percent:leader.percent,days,
   otherDays,otherRank:otherIndex+1,otherPercent:other.percent,
   asof:primary.asof,source:'ECB_G8_PRICE_HISTORY'};
}
function mountValuteRelativeRanking(doc,strip,fx){
 const initial=valuteRelativeFixingRanks(fx,5);
 if(!initial||!strip.isConnected)return; // The provenance notice already explains WITHHELD.
 const rank=doc.createElement('section');rank.id='gmfq-vsc-momentum';
 rank.setAttribute('aria-label','Valute G8 ordinate per momentum osservato');
 rank.dataset.source='ECB_G8_PRICE_HISTORY';
 rank.dataset.tradeSignals='NONE';
 const css=doc.createElement('style');css.id='gmfq-vsc-momentum-style';
 css.textContent=
 '#gmfq-vsc-momentum{margin:0 0 13px;padding:10px 12px 11px;border-bottom:1px solid #304c60;color:#d4e2eb;min-width:0}'+
 '#gmfq-vsc-momentum .gmfq-vsm-top{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}'+
 '#gmfq-vsc-momentum h2{font:600 14px/1.45 Arial,sans-serif;margin:0;color:#e6eef6}'+
 '#gmfq-vsc-momentum .gmfq-vsm-switch{display:flex;gap:6px;flex-wrap:wrap}'+
 '#gmfq-vsc-momentum .gmfq-vsm-switch button{font:600 11px/1.4 Arial,sans-serif;padding:5px 9px;border:1px solid #4b6576;background:#142d3e;color:#c5d6e3;border-radius:5px;cursor:pointer}'+
 '#gmfq-vsc-momentum .gmfq-vsm-switch button[aria-pressed="true"]{border-color:#d3bb83;background:#2d3a45;color:#f2d79e}'+
 '#gmfq-vsc-momentum button:focus-visible{outline:2px solid #e6cf9c;outline-offset:2px}'+
 '#gmfq-vsc-momentum .gmfq-vsm-period{font:11px/1.5 Arial,sans-serif;color:#aabfce;margin:7px 0 6px}'+
 '#gmfq-vsc-momentum .gmfq-vsm-reading{font:600 12px/1.5 Arial,sans-serif;color:#dce9f0;padding:7px 9px;margin:0 0 9px;border-left:2px solid #c9b480;background:#102739;overflow-wrap:anywhere}'+
 '#gmfq-vsc-momentum ol{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 18px;list-style:none;margin:0;padding:0}'+
 '#gmfq-vsc-momentum li{min-width:0;border-top:1px solid #2a4353}'+
 '#gmfq-vsc-momentum li button{display:flex;gap:9px;align-items:center;text-align:left;width:100%;min-width:0;border:0;background:transparent;color:#dce7ee;cursor:pointer;padding:7px 1px;font:600 12px/1.45 Arial,sans-serif}'+
 '#gmfq-vsc-momentum .gmfq-vsm-position{min-width:21px;color:#bda877;font-variant-numeric:tabular-nums}'+
 '#gmfq-vsc-momentum .gmfq-vsm-name{flex:1;min-width:0}'+
 '#gmfq-vsc-momentum .gmfq-vsm-move{font-variant-numeric:tabular-nums;white-space:nowrap;color:#c7dce9}'+
 '#gmfq-vsc-momentum .gmfq-vsm-caution{font:10px/1.5 Arial,sans-serif;color:#90adbf;margin:8px 0 0}'+
 '@media(max-width:600px){#gmfq-vsc-momentum{padding:9px 8px}#gmfq-vsc-momentum ol{grid-template-columns:minmax(0,1fr)}}';
 doc.head.appendChild(css);
 rank.innerHTML='<div class="gmfq-vsm-top"><h2>Momentum FX · dalla più forte alla più debole</h2>'+
 '<div class="gmfq-vsm-switch" role="group" aria-label="Orizzonte del ranking FX">'+
 '<button type="button" data-vsm-days="5" aria-pressed="true">5 sedute</button>'+
 '<button type="button" data-vsm-days="20" aria-pressed="false">20 sedute</button></div></div>'+
 '<p class="gmfq-vsm-period" aria-live="polite"></p>'+
 '<p class="gmfq-vsm-reading" aria-live="polite" data-source="ECB_G8_PRICE_HISTORY"></p>'+
 '<ol aria-label="Classifica osservata delle otto valute G8"></ol>'+
 '<p class="gmfq-vsm-caution">Movimento percentuale contro un paniere G8 equiponderato costruito dai fixing BCE; non è forza Macro/Tassi, DXY ICE, aspettativa di rendimento o graduatoria di trade.</p>';
 strip.insertAdjacentElement('afterend',rank);
 const paint=days=>{
   const data=valuteRelativeFixingRanks(fx,days),list=rank.querySelector('ol');
   if(!data){rank.dataset.status='WITHHELD';list.textContent='Orizzonte non verificabile';return}
   rank.dataset.status='OBSERVED';rank.dataset.horizon=String(days);
   rank.dataset.asof=data.asof;rank.dataset.from=data.from;
   rank.querySelector('.gmfq-vsm-period').textContent=
      days+' sedute BCE · '+data.from+' → '+data.asof+' · forza relativa al paniere, non variazione EUR/USD';
   const read=valuteHorizonFirstRead(fx,days),
         note=rank.querySelector('.gmfq-vsm-reading');
   if(!read){
     note.textContent='Confronto con l’altro orizzonte non verificabile: restano valide soltanto le '+days+' sedute mostrate.';
     rank.dataset.comparisonStatus='WITHHELD';
     delete rank.dataset.comparisonOtherRank;
     delete rank.dataset.comparisonCurrency;
   }else{
     rank.dataset.comparisonStatus='OBSERVED';
     rank.dataset.comparisonOtherRank=String(read.otherRank);
     rank.dataset.comparisonCurrency=read.ccy;
     note.textContent='Lettura rapida · '+FLAG[read.ccy]+' '+read.ccy+
       ' guida sulle '+days+' sedute ('+(read.percent>=0?'+':'')+fmt(read.percent,2)+'% rispetto al G8); '+
       (read.otherRank===1?'è prima anche sulle ':'è '+read.otherRank+'ª sulle ')+read.otherDays+
       ' sedute ('+(read.otherPercent>=0?'+':'')+fmt(read.otherPercent,2)+'%). '+
       'Le due finestre si sovrappongono: non prova una svolta.';
   }
   list.innerHTML=data.items.map((x,i)=>
     '<li data-vsm-ccy="'+x.ccy+'" data-vsm-rank="'+(i+1)+'">'+
     '<button type="button" data-vsm-open="'+x.ccy+'" aria-label="Apri analisi '+x.ccy+'">'+
     '<span class="gmfq-vsm-position">'+String(i+1).padStart(2,'0')+'</span>'+
     '<span class="gmfq-vsm-name">'+FLAG[x.ccy]+' '+x.ccy+'</span>'+
     '<span class="gmfq-vsm-move">'+(x.percent>=0?'+':'')+fmt(x.percent,2)+'%</span>'+
     '</button></li>').join('');
   rank.querySelectorAll('[data-vsm-days]').forEach(x=>
      x.setAttribute('aria-pressed',String(Number(x.dataset.vsmDays)===days)));
 };
 rank.addEventListener('click',e=>{
   const days=e.target.closest('button[data-vsm-days]');
   if(days){paint(Number(days.dataset.vsmDays));return}
   const open=e.target.closest('button[data-vsm-open]');
   if(open&&FX.includes(open.dataset.vsmOpen))go('#/valute?ccy='+open.dataset.vsmOpen);
 });
 paint(5);
}

async function mountValuteSourceCompass(doc){
 if(route()!=='valute'||frame.contentDocument!==doc)return;
 const hero=doc.querySelector('.desk-hero'),main=doc.querySelector('.desk-main');
 if(!hero||!main||doc.getElementById('gmfq-valute-source-compass'))return;
 const strip=doc.createElement('section');
 strip.id='gmfq-valute-source-compass';strip.setAttribute('aria-label','Provenienza dei dati valutari');
 strip.dataset.sourceStatus='LOADING';
 strip.innerHTML='<p class="gmfq-vsc-status">Verifica fonti FX…</p>';
 hero.insertAdjacentElement('afterend',strip);
 const inputs=await Promise.allSettled([
   feed('ECB_G8_PRICE_HISTORY.json'),feed('DXY_SYNTHETIC_ECB.json'),feed('D.json')
 ]);
 if(route()!=='valute'||frame.contentDocument!==doc)return;
 const fx=inputs[0].status==='fulfilled'?inputs[0].value:null;
 const dxy=inputs[1].status==='fulfilled'?inputs[1].value:null;
 const model=inputs[2].status==='fulfilled'?inputs[2].value:null;
 const prices=valuteFxSourceStatus(fx),synthetic=validDxy(dxy);
 const baseline=canonicalMacroBaselineAsOf(model);
 const css=doc.createElement('style');css.id='gmfq-valute-source-compass-style';
 css.textContent=
  '#gmfq-valute-source-compass{margin:0 0 13px;border-top:1px solid #355065;border-bottom:1px solid #294558;padding:9px 12px;color:#bcd0dc;min-width:0}'+
  '#gmfq-valute-source-compass .gmfq-vsc-priority{font:600 13px/1.55 Arial,sans-serif;color:#e4edf3;margin:0 0 7px;overflow-wrap:anywhere}'+
 '#gmfq-valute-source-compass .gmfq-vsc-status{font:11px/1.55 Arial,sans-serif;margin:0;overflow-wrap:anywhere}'+
 '#gmfq-valute-source-compass .gmfq-vsc-ledger{display:flex;flex-wrap:wrap;gap:4px 16px;border-top:1px solid #2b4555;padding-top:9px;margin-top:7px}'+
 '#gmfq-valute-source-compass .gmfq-vsc-ledger span{min-width:0;overflow-wrap:anywhere}'+
  '#gmfq-valute-source-compass strong{color:#e6ecf2;font-weight:600}'+
  '#gmfq-valute-source-compass .gmfq-vsc-details{font:11px/1.6 Arial,sans-serif;color:#9eb7c8;margin-top:5px}'+
  '#gmfq-valute-source-compass .gmfq-vsc-details:not([open])>:not(summary){display:none!important}'+
  '#gmfq-valute-source-compass .gmfq-vsc-details[open]>summary{border-bottom:1px solid #284455;padding-bottom:7px}'+
  '#gmfq-valute-source-compass .gmfq-vsc-details summary{cursor:pointer;color:#d9c18b;outline-offset:3px}'+
  '#gmfq-valute-source-compass .gmfq-vsc-details p{margin:7px 0 0}'+
  '@media(max-width:600px){#gmfq-valute-source-compass{padding:9px 8px}'+
  '#gmfq-valute-source-compass .gmfq-vsc-status{font-size:11px}'+
 '#gmfq-valute-source-compass .gmfq-vsc-ledger span{width:100%}}';
 doc.head.appendChild(css);
 const fxText=prices.status==='OFFICIAL_FIXING_RECENT'?
  'FX BCE '+prices.asof:'FX BCE non corrente o non verificabile';
 const dxyText=synthetic?'DXY sintetico BCE '+dxy.as_of:'DXY sintetico non corrente';
 const modelText=baseline?
  'Macro baseline '+baseline+(!fresh(baseline,10)?' (storica)':' (snapshot)'):
  'Macro baseline non verificabile';
 const macroCurrent=baseline!==null&&fresh(baseline,10);
 const readingState=prices.status!=='OFFICIAL_FIXING_RECENT'?'FX_WITHHELD':
   baseline===null?'MACRO_WITHHELD':!macroCurrent?'MACRO_HISTORICAL':
   !synthetic?'DXY_WITHHELD':'SEPARATE_SOURCES';
 const priorityText=readingState==='FX_WITHHELD'?
   'Prima verifica: fixing BCE FX non corrente o incompleto. Nessuna lettura di forza basata su prezzi recenti può essere certificata.':
   readingState==='MACRO_WITHHELD'?
   'Prima verifica: prezzi BCE recenti, ma baseline Macro non verificabile. Non interpretare gli score come aggiornati.':
   readingState==='MACRO_HISTORICAL'?
   'Prezzo BCE '+prices.asof+' recente; tesi Macro ancora alla baseline '+baseline+'. I nuovi fixing non aggiornano lo score.':
   readingState==='DXY_WITHHELD'?
   'Prezzi BCE e Macro con date distinte; il DXY sintetico non è corrente. Nessuna equivalenza con l’indice ICE.':
   'Prezzi BCE, DXY sintetico e score Macro: fonti diverse anche se tutte recenti. Non sono una lettura intraday unica.';
 strip.dataset.sourceStatus=prices.status;
 strip.dataset.readingState=readingState;
 strip.dataset.fxAsOf=prices.asof||'';
 strip.dataset.dxyStatus=synthetic?'SYNTHETIC_ECB':'WITHHELD';
 strip.dataset.macroAsOf=baseline||'';
 strip.innerHTML='<p class="gmfq-vsc-priority">'+htmlEscape(priorityText)+'</p>'+
  '<details class="gmfq-vsc-details"><summary>Apri date, tre fonti e metodo</summary>'+
  '<div class="gmfq-vsc-status gmfq-vsc-ledger" aria-label="Date e provenienza delle letture valutarie">'+
  '<span data-source="fixing"><strong>Fixing:</strong> '+htmlEscape(fxText)+'</span>'+
  '<span data-source="dxy"><strong>Indice sintetico:</strong> '+htmlEscape(dxyText)+'</span>'+
  '<span data-source="macro"><strong>Modello:</strong> '+htmlEscape(modelText)+'</span></div>'+
  '<p>I fixing BCE sono riferimenti ufficiali giornalieri rispetto all’euro, non prezzi intraday né un giudizio Macro/Tassi. Il ranking momentum G8 qui sotto è calcolato separatamente da queste osservazioni. Il DXY sintetico è una stima informativa ricostruita da fixing BCE, non il DXY ICE ufficiale. Gli score Macro e i giudizi strutturali appartengono alla baseline storica e non vengono aggiornati da queste osservazioni.</p>'+
  '<p>Qualsiasi dato assente o datato resta dichiarato: nessun prezzo, bias, COT, policy path o segnale viene ricostruito automaticamente.</p></details>';
 mountValuteRelativeRanking(doc,strip,fx);
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
 const gap=romeCalendarAge(gold.proxy_as_of);
 return gap!==null&&gap>=0;
}
function crossGoldAge(iso){
 return romeCalendarAge(iso);
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
  '#gmfq-cross-gold-v10 .gmfq-gold-spot{padding:12px 2px 12px 16px;border-left:1px solid #294454;background:transparent;min-width:0}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-spot strong{display:block;font:600 13px/1.4 Arial,sans-serif;color:#d5e3ee;margin-bottom:7px}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-fine{padding:0 17px 13px;color:#8fa8b9;font:10px/1.55 Arial,sans-serif}'+
  '@media(max-width:700px){#gmfq-cross-gold-v10 .gmfq-gold-body{grid-template-columns:1fr;padding:12px;gap:10px}'+
  '#gmfq-cross-gold-v10 .gmfq-gold-quote{font-size:25px}#gmfq-cross-gold-v10 .gmfq-gold-spot{border-left:0;border-top:1px solid #294454;padding:12px 2px 0}#gmfq-cross-gold-v10 .gmfq-gold-fine{padding:0 12px 12px}}';
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
 const age=valid?crossGoldAge(gold.proxy_as_of):null;
 const current=valid&&age!==null&&age>=0&&age<=3;
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
  '<details class="gmfq-gold-line"><summary>Perché lo spot non è disponibile</summary><p>Nessuna quotazione spot ufficiale certificata in questo feed. Le tre osservazioni Gold legacy non hanno provenienza verificata e non sono usate in questo confronto.</p></details>'+
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
/* Cross-Asset research coverage: count actual dated observable instruments,
   not missing LBMA/Brent spots as if they were zero, and never imply synchronized
   or homogeneous market closes. */
function crossStudyCoverage(rows){
 const codes=['GOLD','VIX','WTI','BRENT'];
 const allowed=['OFFICIAL_RECENT','OFFICIAL_HISTORICAL','SECONDARY_RECENT','SECONDARY_HISTORICAL'];
 const checked=codes.map(code=>{
  const x=rows?.[code],valid=allowed.includes(x?.state)&&num(x?.value)!==null&&
   x.value>0&&Number.isInteger(romeCalendarAge(x.asof))&&romeCalendarAge(x.asof)>=0;
  return {code,state:valid?x.state:'UNAVAILABLE'};
 });
 return {total:4,covered:checked.filter(x=>x.state!=='UNAVAILABLE').length,
  official:checked.filter(x=>x.state.startsWith('OFFICIAL_')).length,
  secondary:checked.filter(x=>x.state.startsWith('SECONDARY_')).length,
  historical:checked.filter(x=>x.state.endsWith('_HISTORICAL')).length,
  checked};
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
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-intro{padding:12px 16px 5px;margin:0;font:600 13px/1.55 Arial,sans-serif;color:#e3edf4;overflow-wrap:anywhere}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-coverage{padding:0 16px;margin:7px 0 5px;font:600 12px/1.55 Arial,sans-serif;color:#e3cb94;overflow-wrap:anywhere}'+
  '@media(max-width:600px){#gmfq-cross-risk-v10 .gmfq-cross-coverage{padding:0 12px;font-size:11px}}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-evidence{display:flex;flex-wrap:wrap;gap:4px 15px;padding:6px 16px 12px;color:#aac0cd;font:11px/1.55 Arial,sans-serif;min-width:0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-evidence span{min-width:0;overflow-wrap:anywhere}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-evidence .gmfq-risk-sync{flex-basis:100%;color:#91a9b9;font-size:10px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;padding:0 16px;min-width:0;border-top:1px solid #294454;border-bottom:1px solid #294454}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-card{min-width:0;padding:13px 16px 13px 12px;background:transparent;border:0;border-right:1px solid #294454;border-radius:0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-card:last-child{border-right:0}'+
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
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-note summary{cursor:pointer;color:#d8c58e;font-weight:600;outline-offset:3px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-note p{margin:7px 0 0}'+
  '@media(max-width:820px){#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{grid-template-columns:1fr}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-intro{padding:11px 12px 4px;font-size:12px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-evidence{padding:7px 12px 11px;gap:3px 8px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-evidence span{width:100%}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-grid{padding:0 12px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-card{border-right:0;border-bottom:1px solid #294454;padding:12px 2px}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-card:last-child{border-bottom:0}'+
  '#gmfq-cross-risk-v10 .gmfq-cross-risk-note{padding:12px}}';
 doc.head.appendChild(style);
 const kicker=doc.querySelector('.desk-hero .desk-kicker');
 if(kicker)kicker.textContent='CROSS-ASSET · RESEARCH DESK';
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
 const gold=res?.lanes?.['GOLD.market_proxy'];
 const goldOk=validCrossGold(res,gold),goldAge=goldOk?crossGoldAge(gold.proxy_as_of):null;
 const goldRow={state:!goldOk?'UNAVAILABLE':goldAge<=3?'SECONDARY_RECENT':'SECONDARY_HISTORICAL',
   value:goldOk?gold.value:null,asof:goldOk?gold.proxy_as_of:null};
 const coverage=crossStudyCoverage({GOLD:goldRow,VIX:v,WTI:w,BRENT:b});
 const states=[v.state,w.state,b.state];
 const global=states.every(x=>x==='WITHHELD')?'WITHHELD':
   states.some(x=>x==='WITHHELD'||x.endsWith('HISTORICAL'))?'PARTIAL':'AVAILABLE';
 panel.dataset.sourceStatus=global;
 panel.dataset.studyReferences=String(coverage.covered);
 panel.dataset.studyOfficial=String(coverage.official);
 panel.dataset.studySecondary=String(coverage.secondary);
 panel.dataset.studyEffect='NONE';
 panel.innerHTML='<h2 class="desk-panel-title">Volatilità e petrolio · stato delle fonti</h2>'+
  '<p class="gmfq-cross-risk-intro">VIX misura volatilità implicita, WTI è spot EIA, Brent è futures: strumenti diversi, non un unico segnale risk-on/risk-off.</p>'+
  '<p class="gmfq-cross-coverage" data-study-coverage="'+coverage.covered+'">'+coverage.covered+'/4 riferimenti numerici per lo studio · '+
  coverage.official+' ufficiali (VIX/WTI) · '+coverage.secondary+' futures indicativi (Gold/Brent)'+
  (coverage.historical?' · '+coverage.historical+' osservazioni storiche':' · riferimenti recenti')+
  '. Non equivalenti a quotazioni sincronizzate.</p>'+
  '<div class="gmfq-cross-risk-evidence" aria-label="Date e provenienza VIX WTI Brent">'+
  '<span data-source="vix">VIX Cboe '+htmlEscape(v.asof)+' · '+(v.state==='OFFICIAL_RECENT'?'ultimo dato recente':'dato storico/non verificato')+'</span>'+
  '<span data-source="wti">WTI EIA '+htmlEscape(w.asof)+' · '+(w.state==='OFFICIAL_RECENT'?'ultimo dato recente':'non corrente/non verificato')+'</span>'+
  '<span data-source="brent">Brent futures BZ=F '+htmlEscape(b.asof)+' · '+(b.state==='SECONDARY_RECENT'?'indicativo recente':'non corrente/non verificato')+'</span>'+
  '<span class="gmfq-risk-sync">Non sono quotazioni intraday sincronizzate.</span></div>'+
  '<div class="gmfq-cross-risk-grid">'+
   crossRiskCard('VIX',v,'Volatilità implicita S&P 500','Cboe · storico ufficiale VIX',false)+
   crossRiskCard('WTI',w,'Spot Cushing · RWTC','U.S. Energy Information Administration',false)+
   crossRiskCard('BRENT',b,'Futures BZ=F · non spot','Yahoo Finance · futures secondario',true)+
  '</div>'+
  '<details class="gmfq-cross-risk-note"><summary>Come leggere VIX, WTI e Brent</summary><p><strong>Limiti delle fonti:</strong> il VIX misura volatilità implicita, non da solo la direzione del mercato. WTI e Brent non sono la stessa serie né lo stesso strumento: domanda, offerta, scadenza dei futures e differenze di rilevazione contano. <strong>Brent spot ufficiale: WITHHELD.</strong> Nessun confronto di spread fra spot e futures; nessun giudizio di risk-on/risk-off, segnale o sizing automatico.</p></details>';
 doc.defaultView.GMFQ_CROSS_RISK={status:global,
   vix:{status:v.state,as_of:v.asof},wti:{status:w.state,as_of:w.asof},
   brent:{status:b.state,as_of:b.asof},core_effect:'NONE',
   official_brent:'WITHHELD'};
}

const mountedDocuments=new WeakSet();
/* Central Banks/COT: additive first-reading strip. Preserve the approved
   policy/CFTC charts, 8-row tables, selection controls and all raw feeds. */
function researchFirstStrip(doc,id,title,summary,details,state){
 const hero=doc.querySelector('.desk-hero');
 if(!hero||doc.getElementById(id))return null;
 const style=doc.createElement('style');style.id=id+'-style';
 style.textContent=
  '#'+id+'{margin:0 0 12px;min-width:0;border-top:1px solid #385469;border-bottom:1px solid #284454;padding:11px 15px;color:#c0d0dc}'+
  '#'+id+' .gmfq-first-title{font:600 10px/1.55 Arial,sans-serif;letter-spacing:.08em;color:#d8c48d;margin-bottom:3px}'+
  '#'+id+' .gmfq-first-priority{font:600 13px/1.5 Arial,sans-serif;color:#e5edf3;margin:3px 0 9px;overflow-wrap:anywhere}'+
  '#'+id+' .gmfq-first-claim{font:600 11px/1.55 Arial,sans-serif;color:#c5d5df;border-top:1px solid #294454;padding-top:9px;overflow-wrap:anywhere}'+
  '#'+id+' .gmfq-first-explainer{font:11px/1.65 Arial,sans-serif;color:#a9becd;margin:5px 0 0;overflow-wrap:anywhere}'+
  '#'+id+' details{border-top:1px solid #274455;margin-top:9px;padding-top:6px}'+
  '#'+id+' details summary{cursor:pointer;color:#e1c992;font:600 11px/1.55 Arial,sans-serif;outline-offset:4px}'+
  '#'+id+' details:not([open])>:not(summary){display:none!important}'+
  '#'+id+' details p{font:11px/1.65 Arial,sans-serif;color:#afc0ce;margin:7px 0 0;overflow-wrap:anywhere}'+
  '@media(max-width:600px){#'+id+'{padding:10px 11px}#'+id+' .gmfq-first-priority{font-size:12px}#'+id+' .gmfq-first-claim{font-size:11px}}';
 doc.head.appendChild(style);
 const rail=doc.createElement('section');rail.id=id;rail.dataset.readingStatus=state;
 rail.setAttribute('aria-label',title);
 rail.innerHTML='<div class="gmfq-first-title">'+htmlEscape(title)+'</div>'+
  '<p class="gmfq-first-priority">'+htmlEscape(details.takeaway||summary)+'</p>'+
  '<div class="gmfq-first-claim" aria-label="Evidenze quantitative e date">'+htmlEscape(summary)+'</div>'+
  '<p class="gmfq-first-explainer">'+htmlEscape(details.intro)+'</p>'+
  '<details><summary>Apri provenienza e limiti di questa lettura</summary>'+
  '<p>'+htmlEscape(details.sources)+'</p><p>'+htmlEscape(details.guard)+'</p></details>';
 hero.insertAdjacentElement('afterend',rail);
 return rail;
}
async function mountCentralBankFirstReading(doc){
 if(route()!=='banche'||frame.contentDocument!==doc)return;
 const hero=doc.querySelector('.desk-hero'),table=doc.getElementById('cb-table');
 if(!hero||!table||doc.getElementById('gmfq-cb-reading-first'))return;
 const inputs=await Promise.allSettled([feed('NATIVE_CB_DATA.json'),feed('OIS_OPERATIONAL_VIEW.json')]);
 if(route()!=='banche'||frame.contentDocument!==doc)return;
 const cb=inputs[0].status==='fulfilled'?inputs[0].value:null;
 const ois=inputs[1].status==='fulfilled'?inputs[1].value:null;
 const validCalendarDay=d=>typeof d==='string'&&/^20\d{2}-\d{2}-\d{2}$/.test(d)&&
  Number.isFinite(Date.parse(d+'T00:00:00Z'))&&
  new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d;
 const core=cb&&Object.keys(cb).length===8&&FX.every(c=>{
  const x=cb[c];return x&&num(x.rate)!==null&&macroSeriesPeriod(x.last_date)===x.last_date&&
    validCalendarDay(x.next_meeting)&&x.bank&&x.action;
 });
 const acceptable=['GREEN_OFFICIAL','GREEN_ESTIMATED','WITHHELD'];
 const operational=ois?.schema==='GMFQ_OIS_OPERATIONAL_VIEW_V1'&&
  FX.every(c=>acceptable.includes(ois.currencies?.[c]?.operational_status));
 const certified=operational?marketResearchCurves(ois):[];
 const expectedOfficial=operational?FX.filter(c=>ois.currencies[c].operational_status==='GREEN_OFFICIAL'):[];
 const reconciled=core&&operational&&certified.length===expectedOfficial.length&&
  expectedOfficial.every(c=>certified.some(v=>v.k===c));
 const estimated=operational?FX.filter(c=>ois.currencies[c].operational_status==='GREEN_ESTIMATED'):[];
 const withheld=operational?FX.filter(c=>ois.currencies[c].operational_status==='WITHHELD'):[];
 const dates=core?FX.map(c=>cb[c].last_date).sort():[];
 const rail=researchFirstStrip(doc,'gmfq-cb-reading-first','BANCHE CENTRALI · DOVE INIZIARE',
  reconciled?
   'Decisioni archiviate '+dates[0]+' → '+dates.at(-1)+' · Pricing 6M certificato '+certified.length+'/8':
   'Decisioni o pricing non riconciliabili · lettura sospesa',
  {takeaway:reconciled?
    'Le ultime decisioni sono snapshot storici; il pricing è un layer separato e non indica nuove decisioni di politica monetaria.':
    'La sintesi resta sospesa finché decisioni e copertura del pricing non sono riconciliate.',
   intro:reconciled?
    'GBP: OIS BoE; JPY, AUD, CAD: futures monetari. '+estimated.length+' valute stimate; '+
    withheld.length+' senza curva certificata. Repricing ≠ probabilità di meeting.':
    'Dati o copertura insufficienti: non è possibile dichiarare un quadro aggiornato delle banche centrali.',
   sources:'Policy rate e decisioni: NATIVE_CB_DATA, date individuali dell’ultima decisione; prezzi: OIS_OPERATIONAL_VIEW, as-of separato per valuta. I dati del policy book non rappresentano dichiarazioni appena rilasciate.',
   guard:'Le curve certificate possono riferirsi a strumenti differenti; futures monetari non sono OIS puri. Snapshot policy storico, nessun nuovo giudizio hawkish/dovish, probabilità implicita o segnale FX inferiti.'},
  reconciled?'READ_ONLY':'WITHHELD');
 if(!rail)return;
 rail.dataset.policyEarliest=dates[0]||'';rail.dataset.policyLatest=dates.at(-1)||'';
 rail.dataset.certified=reconciled?String(certified.length):'';
 rail.dataset.estimated=reconciled?String(estimated.length):'';
 rail.dataset.withheld=reconciled?String(withheld.length):'';
 if(!reconciled)return;
 // Historical bank-decision snapshots supply meeting dates, NOT live release
 // confirmation. Keep same-day/past meetings out of "upcoming" summaries.
 const today=romeTodayIso();
 // Source-age disclosure is non-operative and does not replace any CB quote.
 const fedAudit=fedPricingFreshnessAudit(cb.USD,ois.currencies.USD,today);
 const fedNote=doc.createElement('p');fedNote.id='gmfq-fed-pricing-freshness';
 fedNote.dataset.pricingState=fedAudit.state;
 fedNote.dataset.quoteAsOf=fedAudit.quote_date||'';
 fedNote.dataset.preDecision=String(fedAudit.pre_decision);
 fedNote.style.cssText='border-top:1px solid #294657;padding-top:8px;margin:10px 0 3px;color:#d2c59e;font:11px/1.6 Arial,sans-serif;overflow-wrap:anywhere';
 fedNote.textContent=fedAudit.text;
 // An ordinary outbound reference lets the user consult the licensed source
 // on its own website. NO CME data extraction, iframe or price/probability API.
 const fedWatch=doc.createElement('a');
 fedWatch.href='https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool';
 fedWatch.target='_blank';fedWatch.rel='noopener noreferrer';
 fedWatch.textContent='Consulta FedWatch ufficiale CME (sito esterno)';
 fedWatch.setAttribute('aria-label','Apri FedWatch sul sito ufficiale CME');
 fedWatch.style.cssText='color:#e5c986;text-decoration:underline;display:inline-block;margin-left:5px';
 fedNote.appendChild(doc.createTextNode(' '));
 fedNote.appendChild(fedWatch);
 rail.querySelector('.gmfq-first-explainer')?.insertAdjacentElement('afterend',fedNote);
 const meetings=FX.map(ccy=>{
   const policy=cb[ccy],pricing=ois.currencies[ccy];
   const status=pricing.operational_status;
   return {ccy,bank:String(policy.bank),date:policy.next_meeting,last:policy.last_date,
     rateText:String(policy.rate_text||fmt(policy.rate,2)+'%'),
     tier:status==='GREEN_OFFICIAL'?'CERTIFIED':status==='GREEN_ESTIMATED'?'ESTIMATED':'WITHHELD',
     proxy:status==='WITHHELD'&&Boolean(pricing.market_direction_proxy||pricing.secondary_quote_context)};
 }).sort((a,b)=>a.date.localeCompare(b.date)||FX.indexOf(a.ccy)-FX.indexOf(b.ccy));
 const future=meetings.filter(x=>x.date>today);
 const focusDates=[...new Set(future.map(x=>x.date))].slice(0,3);
 rail.dataset.meetingSnapshotAsOf=dates.at(-1)||'';
 rail.dataset.meetingDateGroups=String(focusDates.length);
 rail.dataset.meetingUpcomingCount=String(future.length);
 const st=doc.createElement('style');st.id='gmfq-cb-meeting-focus-style';
 st.textContent='#gmfq-cb-reading-first .gmfq-cb-meeting-focus{margin:9px 0 0;padding:8px 0 0;border-top:1px solid #294657}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-kicker{font:600 10px/1.5 Arial,sans-serif;color:#e1c38d;margin:0 0 4px}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-dates{list-style:none;margin:0;padding:0;display:flex;gap:5px 17px;flex-wrap:wrap}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-dates li{font:11px/1.55 Arial,sans-serif;color:#e1e9f0;min-width:0}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-dates time{font-weight:600;color:#d8c28a;margin-right:3px}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-foot{font:10px/1.55 Arial,sans-serif;color:#a8bfcd;margin:5px 0 0}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-all{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 13px;list-style:none;margin:8px 0 0;padding:0}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-all li{font:10px/1.6 Arial,sans-serif;color:#bbcfdd;overflow-wrap:anywhere}'+
  '#gmfq-cb-reading-first .gmfq-cb-meeting-all strong{font-weight:600;color:#e8d09b}'+
  '@media(max-width:600px){#gmfq-cb-reading-first .gmfq-cb-meeting-dates{display:block}#gmfq-cb-reading-first .gmfq-cb-meeting-all{grid-template-columns:1fr}}';
 doc.head.appendChild(st);
 const node=doc.createElement('div');node.className='gmfq-cb-meeting-focus';
 node.dataset.source='NATIVE_CB_DATA';node.dataset.calendarStatus='HISTORICAL_SNAPSHOT';
 node.dataset.asOf=dates.at(-1)||'';
 node.innerHTML='<p class="gmfq-cb-meeting-kicker">AGENDA DALLO SNAPSHOT CB · 3 PROSSIME DATE</p>'+
 (focusDates.length?'<ul class="gmfq-cb-meeting-dates">'+focusDates.map(date=>
   '<li data-meeting-day="'+date+'"><time datetime="'+date+'">'+date.slice(8,10)+'/'+date.slice(5,7)+'</time> '+
   future.filter(x=>x.date===date).map(x=>
     '<span data-meeting-ccy="'+x.ccy+'">'+FLAG[x.ccy]+' '+htmlEscape(x.bank)+'</span>').join(' · ')+
   '</li>').join('')+'</ul>':
   '<p class="gmfq-cb-meeting-foot">Nessuna futura riunione nello snapshot: calendario da riconfermare.</p>')+
 '<p class="gmfq-cb-meeting-foot">Ultima decisione nello snapshot '+htmlEscape(dates.at(-1))+
 '. Date archiviate, da riconfermare alla fonte: non sono annunci né meeting confermati in tempo reale.</p>';
 rail.querySelector('.gmfq-first-explainer')?.insertAdjacentElement('afterend',node);
 // Original provenance details stays FIRST to preserve existing keyboard tests.
 const detail=doc.createElement('details');detail.className='gmfq-cb-meeting-details';
 detail.dataset.count='8';detail.dataset.source='NATIVE_CB_DATA';
 detail.innerHTML='<summary>Apri tutte le 8 banche, tassi e qualità del pricing</summary>'+
 '<ul class="gmfq-cb-meeting-all">'+meetings.map(x=>
  '<li data-meeting-ccy="'+x.ccy+'" data-meeting-date="'+x.date+
  '" data-meeting-tier="'+x.tier+'" data-policy-asof="'+x.last+'">'+
  FLAG[x.ccy]+' <strong>'+x.ccy+' · '+htmlEscape(x.bank)+'</strong> · '+htmlEscape(x.date)+
  ' · tasso '+htmlEscape(x.rateText)+' · '+
  (x.tier==='CERTIFIED'?'6M: fonte certificata':
   x.tier==='ESTIMATED'?'6M: futures indicativi':
   '6M: WITHHELD'+(x.proxy?' (proxy/contesto separato)':''))+
  (x.date<=today?' · DATA PASSATA NELLO SNAPSHOT':'')+'</li>').join('')+
 '</ul><p>Tassi policy: ultima decisione nello snapshot storico, NON valore aggiornato da questo pannello. Pricing: fonti certificate, futures indicativi e WITHHELD sono categorie distinte. Non attribuire probabilità di rialzo/taglio a una riunione.</p>';
 rail.appendChild(detail);
}
function cotQuantitativeAudit(chart,story){
 if(!chart||!story||Object.keys(chart).length!==8||
    !FX.every(c=>Object.hasOwn(chart,c)&&Object.hasOwn(story,c)))return null;
 const series={},dates=new Set(),previousDates=new Set(),mismatched=[];
 for(const c of FX){
  const t=chart[c],st=story[c];
  if(!t||!st||!['dates','net','long','short','netoi','percentile'].every(k=>Array.isArray(t[k])&&t[k].length===104)||
     t.dates.some((date,i)=>macroSeriesPeriod(date)!==date||(i>0&&date<=t.dates[i-1])))return null;
  const n=103,net=num(t.net[n]),long=num(t.long[n]),short=num(t.short[n]),
   prevNet=num(t.net[n-1]),prevLong=num(t.long[n-1]),prevShort=num(t.short[n-1]),
   ratio=num(t.netoi[n]),percent=num(t.percentile[n]),date=t.dates[n],previousDate=t.dates[n-1];
  // Weekly delta is net contracts in the SAME market, not normalized FX price.
  // Reject a shifted/partial prior week rather than calculate an invented move.
  if([net,long,short,ratio,percent,prevNet,prevLong,prevShort].some(v=>v===null)||
     ![net,long,short,prevNet,prevLong,prevShort].every(Number.isInteger)||
     long<0||short<0||long-short!==net||
     prevLong<0||prevShort<0||prevLong-prevShort!==prevNet||
     Math.abs(ratio)>100||percent<0||percent>100||!['WITHHELD'].includes(st.price)||
     macroSeriesPeriod(previousDate)!==previousDate||
     Date.parse(date+'T00:00:00Z')-Date.parse(previousDate+'T00:00:00Z')!==7*86400000)return null;
  const rounded=Math.round(percent),q=rounded>=80?'EXTREME LONG':rounded<=20?'EXTREME SHORT':'NEUTRALE';
  if(st.signal!==q)mismatched.push(c);
  dates.add(date);previousDates.add(previousDate);
  series[c]={net,prevNet,deltaNet:net-prevNet,ratio,rounded,q,date,previousDate};
 }
 if(dates.size!==1||previousDates.size!==1)return null;
 const extremes=FX.filter(c=>series[c].q!=='NEUTRALE');
 const crowding=FX.filter(c=>Math.abs(series[c].ratio)>=30);
 // Prioritize by absolute Net/OI, *not* by FX view or rounded percentile.
 // A crowded non-extreme percentile (e.g., NZD) remains clearly distinct.
 const crowdingFocus=crowding.slice().sort((a,b)=>Math.abs(series[b].ratio)-Math.abs(series[a].ratio)||
   FX.indexOf(a)-FX.indexOf(b)).slice(0,3).map(c=>({
     ccy:c,netoi:series[c].ratio,percentile:series[c].rounded,
     netSign:series[c].net>0?'NET_LONG':series[c].net<0?'NET_SHORT':'NET_FLAT',
     percentileClass:series[c].q,
     net:series[c].net,prevNet:series[c].prevNet,deltaNet:series[c].deltaNet
   }));
 const extremeSnapshots=extremes.map(ccy=>{
   const x=series[ccy];
   return {ccy,net:x.net,deltaNet:x.deltaNet,netoi:x.ratio,
     percentile:x.rounded,percentileClass:x.q,
     netSign:x.net>0?'NET_LONG':x.net<0?'NET_SHORT':'NET_FLAT',
     rankOpposesNet:(x.q==='EXTREME LONG'&&x.net<0)||(x.q==='EXTREME SHORT'&&x.net>0)};
 });
 const weeklyPositions=FX.map(ccy=>({
   ccy,net:series[ccy].net,prevNet:series[ccy].prevNet,
   deltaNet:series[ccy].deltaNet,netSign:series[ccy].net>0?'NET_LONG':
     series[ccy].net<0?'NET_SHORT':'NET_FLAT'
 }));
 return {asof:series.USD.date,priorAsOf:series.USD.previousDate,
   weeklyPositions,extremes,crowding,mismatched,crowdingFocus,extremeSnapshots,
   extremeLong:extremes.filter(c=>series[c].q==='EXTREME LONG'),
   extremeShort:extremes.filter(c=>series[c].q==='EXTREME SHORT')};
}
/* ECB fixing is a DATE-SEPARATED FX observation, NEVER a CFTC-price confirmation.
   Tuesday CFTC positions are NOT necessarily Friday publication-time positions. */
function cotBcePriceContext(cftcDay, fx){
 const iso=d=>/^\d{4}-\d{2}-\d{2}$/.test(d||'')&&
   Number.isFinite(Date.parse(d+'T00:00:00Z'))&&
   new Date(Date.parse(d+'T00:00:00Z')).toISOString().slice(0,10)===d;
 if(!iso(cftcDay)||fx?.base!=='EUR'||fx?.status!=='CURRENT_OFFICIAL_HISTORY'||
    fx?.pair_count!==28||!Array.isArray(fx?.rows)||fx.row_count!==fx.rows.length||
    !iso(fx.last_as_of)||fx.last_as_of<=cftcDay||
    fx.rows.at(-1)?.Date!==fx.last_as_of)return null;
 const gap=(Date.parse(fx.last_as_of+'T00:00:00Z')-
   Date.parse(cftcDay+'T00:00:00Z'))/86400000;
 if(gap<=0||gap>7)return null; // Never extrapolate a stale CFTC report.
 const start=fx.rows.filter(r=>r.Date===cftcDay);
 if(start.length!==1)return null;
 const a=start[0],b=fx.rows.at(-1),ccys=['EUR',...FX.filter(x=>x!=='EUR')];
 if(![a,b].every(r=>ccys.every(c=>num(r?.[c])!==null&&r[c]>0&&r[c]<100000)&&r.EUR===1))return null;
 const lines=FX.map(ccy=>{
   // ECB EUR-base: USD per CCY = EURUSD / EURCCY.
   // USD is displayed in EUR per USD to preserve currency-oriented moves.
   const side=ccy==='USD'?'USD/EUR':ccy+'/USD';
   const measure=r=>ccy==='USD'?1/r.USD:ccy==='EUR'?r.USD:r.USD/r[ccy];
   const p0=measure(a),p1=measure(b),pct=100*(p1/p0-1);
   if(!Number.isFinite(pct)||Math.abs(pct)>80)return null;
   return {ccy,side,pct};
 });
 if(lines.includes(null))return null;
 return {cftc_day:cftcDay,fx_start_day:cftcDay,fx_end_day:fx.last_as_of,
   days:gap,lines,source:'ECB euro foreign exchange reference rates',
   is_position_price_confirmation:false,not_intraday:true,causal_claim:false};
}
async function mountCotFirstReading(doc){
 if(route()!=='cot'||frame.contentDocument!==doc)return;
 const hero=doc.querySelector('.desk-hero'),table=doc.getElementById('cot-table');
 if(!hero||!table||doc.getElementById('gmfq-cot-reading-first'))return;
 const inputs=await Promise.allSettled([feed('V250_COT_CHART_DATA.json'),feed('V247_COT_STORIES.json'),feed('ECB_G8_PRICE_HISTORY.json')]);
 if(route()!=='cot'||frame.contentDocument!==doc)return;
 const result=cotQuantitativeAudit(inputs[0].status==='fulfilled'?inputs[0].value:null,
   inputs[1].status==='fulfilled'?inputs[1].value:null);
 const rail=researchFirstStrip(doc,'gmfq-cot-reading-first','COT · COSA CONTA',
  result?
   'CFTC '+result.asof+' · Estremi percentile 104W: '+result.extremes.length+'/8 · Crowding |Net/OI| ≥30%: '+result.crowding.length+'/8':
   'COT non riconciliabile · nessun estremo certificato',
  {takeaway:result?
   (result.mismatched.length?
     'Dati COT e narrativa divergono per '+result.mismatched.join(', ')+'. La discrepanza non viene corretta automaticamente.':
     'Gli estremi COT descrivono il positioning relativo, non confermano la direzione del cambio né un setup di ingresso.'):
   'La lettura resta sospesa: le serie CFTC non sono riconciliabili.',
   intro:result?
   'Classificazione dopo arrotondamento: '+result.extremeLong.length+' EXTREME LONG, '+result.extremeShort.length+
   ' EXTREME SHORT. Prezzo FX: WITHHELD (nessuna conferma ricostruita).'+
   (result.mismatched.length?' ⚠ Testo narrativo incoerente: '+result.mismatched.join(', ')+'.':''):
   'Serie o racconti CFTC non riconciliabili: non sono pubblicate nuove classificazioni.',
   sources:'CFTC Legacy Non-Commercial Futures Only: V250_COT_CHART_DATA (104 osservazioni per valuta) e V247_COT_STORIES. Ultima data di posizione martedì CFTC, non quotazione di mercato corrente.',
   guard:'Un percentile estremo indica il rango nella finestra storica, NON la direzione assoluta del Net. Uno short netto può coesistere con EXTREME LONG. Le etichette narrative divergenti sono segnalate, non corrette silenziosamente; nessun segnale operativo dal solo COT.'},
  result?(result.mismatched.length?'SOURCE_DIVERGENCE':'READ_ONLY'):'WITHHELD');
 if(!rail)return;
 rail.dataset.cftcAsOf=result?.asof||'';
 rail.dataset.extremes=result?String(result.extremes.length):'';
 rail.dataset.crowding=result?String(result.crowding.length):'';
 rail.dataset.conflicts=result?result.mismatched.join(','):'';
 // A relative historical percentile is not the absolute signed Net. This
 // source-verified case deserves one explanatory line, not a second dashboard.
 // Any narrative-vs-source mismatch disables this authoritative interpretation.
 if(result&&!result.mismatched.length&&result.extremeSnapshots.length){
   const st=doc.createElement('style');st.id='gmfq-cot-percentile-style';
   st.textContent='#gmfq-cot-reading-first .gmfq-cot-percentile{border-top:1px solid #284455;margin:9px 0 0;padding:8px 0 0}'+
     '#gmfq-cot-reading-first .gmfq-cot-rank-note{font:11px/1.55 Arial,sans-serif;color:#d3dfe8;margin:0 0 6px;overflow-wrap:anywhere}'+
     '#gmfq-cot-reading-first .gmfq-cot-rank-note strong{color:#e4cb8a;font-weight:600}'+
     '#gmfq-cot-reading-first .gmfq-cot-percentile-details{margin:4px 0 0;border-top:0;padding-top:0}'+
     '#gmfq-cot-reading-first .gmfq-cot-percentile-details>summary{font:600 10px/1.5 Arial,sans-serif;color:#ddc58b;cursor:pointer;outline-offset:3px}'+
     '#gmfq-cot-reading-first .gmfq-cot-percentile-list{padding:0;margin:7px 0 0;list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3px 17px}'+
     '#gmfq-cot-reading-first .gmfq-cot-percentile-list li{font:10px/1.55 Arial,sans-serif;color:#c3d6e0;overflow-wrap:anywhere}'+
     '#gmfq-cot-reading-first .gmfq-cot-rank-footnote{font:10px/1.5 Arial,sans-serif;color:#a7bdcc;margin:7px 0 0}'+
     '@media(max-width:600px){#gmfq-cot-reading-first .gmfq-cot-percentile-list{grid-template-columns:1fr}}';
   doc.head.appendChild(st);
   const signed=v=>(v>0?'+':'')+v.toLocaleString('it-IT');
   const inversions=result.extremeSnapshots.filter(x=>x.rankOpposesNet);
   const box=doc.createElement('div');box.className='gmfq-cot-percentile';
   box.dataset.cftcAsOf=result.asof;
   box.dataset.relativeVsNet='SEPARATE';
   box.dataset.inversionCount=String(inversions.length);
   box.innerHTML=(inversions.length?
     '<p class="gmfq-cot-rank-note"><strong>Percentile ≠ segno del Net.</strong> '+
     inversions.map(x=>FLAG[x.ccy]+' '+x.ccy+' '+x.percentile+'° · '+
       x.percentileClass+', ma Net '+signed(x.net)+' ('+
       (x.net<0?'short':'long')+' netto)').join('; ')+
     '. È un rango rispetto alle 104 settimane, non una posizione net long.</p>':
     '<p class="gmfq-cot-rank-note"><strong>Percentile ≠ segno del Net.</strong> '+
     'Le etichette EXTREME LONG / SHORT indicano il rango storico del posizionamento, non il segno assoluto.</p>')+
     '<details class="gmfq-cot-percentile-details" data-cftc-asof="'+result.asof+
     '"><summary>Apri '+result.extremeSnapshots.length+' estremi: percentile, Net e variazione 1W</summary>'+
     '<ul class="gmfq-cot-percentile-list">'+result.extremeSnapshots.map(x=>
       '<li data-extreme-ccy="'+x.ccy+'" data-extreme-rank="'+x.percentile+
       '" data-extreme-class="'+x.percentileClass+'" data-extreme-net="'+x.net+
       '" data-extreme-week="'+x.deltaNet+'" data-rank-vs-net="'+
       (x.rankOpposesNet?'OPPOSED':'ALIGNED')+'">'+
       FLAG[x.ccy]+' '+x.ccy+' · '+x.percentile+'° · '+x.percentileClass+
       ' · Net '+signed(x.net)+' · ΔNet '+signed(x.deltaNet)+'</li>').join('')+
     '</ul><p class="gmfq-cot-rank-footnote">Percentile 104W arrotondato (≥80 EXTREME LONG; ≤20 EXTREME SHORT). Il Net è il saldo long meno short in contratti futures. “Opposto” non significa errore o inversione di prezzo: indica solo un rango storico elevato/basso mentre il saldo assoluto ha segno diverso.</p></details>';
   rail.querySelector('.gmfq-first-explainer')?.insertAdjacentElement('afterend',box);
   rail.dataset.percentileCount=String(result.extremeSnapshots.length);
   rail.dataset.rankVsNet=String(inversions.length);
 }
 // A small source-reconciled shortlist is the only extra first-screen layer.
 // All 8 CFTC currencies remain in the approved native chart and table.
 if(result&&result.crowdingFocus.length){
   const st=doc.createElement('style');st.id='gmfq-cot-focus-style';
   st.textContent='#gmfq-cot-reading-first .gmfq-cot-focus{margin:8px 0 3px;border-top:1px solid #294657;padding-top:9px;min-width:0}'+
     '#gmfq-cot-reading-first .gmfq-cot-focus-title{margin:0 0 5px;font:600 10px/1.45 Arial,sans-serif;color:#d8c48d}'+
     '#gmfq-cot-reading-first .gmfq-cot-focus-list{display:flex;gap:5px 16px;flex-wrap:wrap;list-style:none;padding:0;margin:0}'+
     '#gmfq-cot-reading-first .gmfq-cot-focus-list li{font:11px/1.55 Arial,sans-serif;color:#cddce6;min-width:0;white-space:normal}'+
     '#gmfq-cot-reading-first .gmfq-cot-focus-list strong{font-weight:600;color:#f1b4af}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-delta{font:10px/1.45 Arial,sans-serif;color:#a9c4d6;white-space:nowrap;margin-left:4px}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-details{margin:7px 0 0;border-top:1px solid #284455;padding-top:6px}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-details>summary{cursor:pointer;color:#dbc58d;font:600 10px/1.55 Arial,sans-serif;outline-offset:3px}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-details:not([open])>:not(summary){display:none!important}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));padding:0;margin:8px 0 3px;list-style:none;gap:3px 16px}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-list li{font:10px/1.65 Arial,sans-serif;color:#bacedd;white-space:normal;overflow-wrap:anywhere}'+
     '#gmfq-cot-reading-first .gmfq-cot-weekly-method{font:10px/1.5 Arial,sans-serif;color:#9db5c5;margin:7px 0 2px}'+
     '@media(max-width:600px){#gmfq-cot-reading-first .gmfq-cot-weekly-list{grid-template-columns:1fr}}'+
     '#gmfq-cot-reading-first .gmfq-cot-focus-note{display:block;font:10px/1.5 Arial,sans-serif;color:#9bb5c6;margin:4px 0 0}'+
     '@media(max-width:600px){#gmfq-cot-reading-first .gmfq-cot-focus-list{gap:4px 12px}#gmfq-cot-reading-first .gmfq-cot-focus-list li{font-size:10px}}';
   doc.head.appendChild(st);
   const box=doc.createElement('div');box.className='gmfq-cot-focus';
   box.dataset.cftcAsOf=result.asof;
   const pct=v=>(v>0?'+':'')+v.toFixed(1)+'%';
   const signedInt=v=>(v>0?'+':'')+v.toLocaleString('it-IT');
   box.innerHTML='<p class="gmfq-cot-focus-title">⚠ CONCENTRAZIONE NET/OI ≥30% · '+htmlEscape(result.asof)+'</p>'+
     '<ul class="gmfq-cot-focus-list">'+result.crowdingFocus.map(x=>
       '<li data-cot-focus-ccy="'+x.ccy+'" data-netoi="'+x.netoi+'" data-percentile-rounded="'+x.percentile+
       '" data-net-direction="'+x.netSign+'" data-percentile-class="'+x.percentileClass+'">'+
       FLAG[x.ccy]+' '+x.ccy+' <strong>'+pct(x.netoi)+'</strong> · '+
       x.percentile+'°/104W <span class="gmfq-cot-weekly-delta" data-weekly-net="'+x.deltaNet+
       '">ΔNet 1W '+signedInt(x.deltaNet)+' contratti</span></li>').join('')+'</ul>'+
     '<small class="gmfq-cot-focus-note">Net/OI = esposizione netta sul totale open interest; percentile = rango storico, non direzione del prezzo. COT non intraday.</small>'+
     '<details class="gmfq-cot-weekly-details" data-prior-asof="'+result.priorAsOf+
     '" data-current-asof="'+result.asof+'"><summary>Apri ΔNet settimanale delle 8 valute ('+
     result.priorAsOf+' → '+result.asof+')</summary>'+
     '<ul class="gmfq-cot-weekly-list">'+result.weeklyPositions.map(x=>
       '<li data-weekly-ccy="'+x.ccy+'" data-weekly-net="'+x.net+'" data-weekly-prev-net="'+
       x.prevNet+'" data-weekly-delta="'+x.deltaNet+'" data-net-direction="'+x.netSign+'">'+
       FLAG[x.ccy]+' '+x.ccy+' · Net '+signedInt(x.net)+' · ΔNet '+signedInt(x.deltaNet)+
       ' contratti</li>').join('')+'</ul>'+
     '<p class="gmfq-cot-weekly-method">ΔNet = Net della settimana CFTC più recente meno Net della precedente, nella stessa valuta future. Positivo significa più verso long (o meno short); negativo più verso short (o meno long). Non confrontare direttamente il numero di contratti tra mercati: dimensioni contrattuali diverse. Nessun segnale FX.</p></details>';
   rail.querySelector('.gmfq-first-claim')?.insertAdjacentElement('afterend',box);
   rail.dataset.focusCount=String(result.crowdingFocus.length);
   rail.dataset.weeklyAsOf=result.priorAsOf;
   rail.dataset.weeklyCount=String(result.weeklyPositions.length);
 }
 // Separate dated FX context: show what spot reference DID, not whether
 // positioning predicted it. The original COT price field stays WITHHELD.
 const priceContext=result&&!result.mismatched.length&&inputs[2].status==='fulfilled'?
   cotBcePriceContext(result.asof,inputs[2].value):null;
 rail.dataset.bcePriceContext=priceContext?'DATED_ONLY':'UNAVAILABLE';
 if(priceContext){
   const box=doc.createElement('details');box.className='gmfq-cot-bce-price';
   box.dataset.cftcAsOf=priceContext.cftc_day;
   box.dataset.ecbAsOf=priceContext.fx_end_day;
   box.dataset.priceConfirmation='NONE';
   const sign=v=>(v>0?'+':'')+v.toFixed(2)+'%';
   box.innerHTML='<summary>Prezzo BCE · '+priceContext.fx_start_day+' → '+
     priceContext.fx_end_day+' · 8 valute (solo contesto)</summary>'+
     '<ul style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));'+
       'gap:4px 14px;list-style:none;padding:6px 0;margin:0">'+
     priceContext.lines.map(x=>'<li data-bce-ccy="'+x.ccy+'" '+
       'data-price-percent="'+x.pct.toFixed(5)+'">'+FLAG[x.ccy]+' '+
       x.side+' · '+sign(x.pct)+'</li>').join('')+'</ul>'+
     '<p style="font-size:11px;line-height:1.5;color:#a9bfcd">'+
       'Fixing BCE giornaliero, NON prezzo eseguibile/intraday. Le posizioni CFTC '+
       'sono riferite al martedì e pubblicate successivamente: il movimento '+
       'del cambio dopo martedì NON dimostra conferma, causalità o rendimento '+
       'delle posizioni. COT e FX non sono un segnale di trading.</p>';
   rail.appendChild(box);
 }
}


/* G8 current economic/rates context: factual observations only.
   This does not resurrect the undocumented 2026-09-25 D score formula,
   estimate macro-FX strength, or alter the 28 canonical pair theses. */
async function mountMacroV2CurrentEvidence(doc){
 if(route()!=='macro'||frame.contentDocument!==doc||
    doc.getElementById('gmfq-macro-v2-current-evidence'))return;
 const hero=doc.querySelector('.desk-hero');
 if(!hero)return;
 const panel=doc.createElement('section');
 panel.id='gmfq-macro-v2-current-evidence';panel.className='desk-panel';
 panel.dataset.status='LOADING';
 panel.setAttribute('aria-label','Evidenze G8 recenti Growth Macro e tassi senza nuovo score FX');
 panel.innerHTML='<h2 class="desk-panel-title">Macro V2 · evidenze disponibili</h2><p>Verifica di date, fonti e qualità in corso.</p>';
 hero.insertAdjacentElement('afterend',panel);
 const gdpUrl='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/validation/macro/fixtures/v2_g8_quarterly_gdp_q2_2026_web_release_ledger_v1.json';
 const results=await Promise.allSettled([
  feed('MACRO_THERMOMETER_DATA.json'),feed('NATIVE_RATES_DATA.json'),
  feed('OIS_OPERATIONAL_VIEW.json'),feed('NZD_CB_PRICING_DIRECTIONAL_PROXY.json'),fetchSecondary2Y(),
  (async()=>{const response=await fetch(gdpUrl,{cache:'no-store'});
    if(!response.ok)throw Error('GDP dossier HTTP '+response.status);
    return response.json()})()
 ]);
 if(route()!=='macro'||frame.contentDocument!==doc||!panel.isConnected)return;
 const [macro,rates,ois,nzdProxy,secondary2y,gdp]=results.map(r=>r.status==='fulfilled'?r.value:null);
 const valid=macro?.schema_version==='GMFQ_MACRO_HEATMAP_V1'&&
   macro.status==='ACTIVE'&&rates&&ois?.currencies&&
   gdp?.schema==='GMFQ_G8_REAL_GDP_Q2_2026_PUBLISHER_WEB_RELEASE_EVENTS_V1'&&
   gdp.eligible_for_macro_scoring===false&&gdp.may_rewrite_D_json===false&&
   gdp.release_artifact_original_day_bytes_archived===false&&
   gdp.gdp_reporting_horizon_not_uniform===true&&
   gdp.observed_first_web_releases===8;
 const first=gdp?.records?.filter(x=>x.stage_order===0)||[];
 const unique=new Set(first.map(x=>x.currency));
 if(!valid||first.length!==8||unique.size!==8||
    !FX.every(c=>unique.has(c)&&macro.currencies?.[c]?.status==='ACTIVE'&&rates[c]&&ois.currencies[c])){
  panel.dataset.status='INCOMPLETE_SOURCE_CONTEXT';
  panel.innerHTML='<h2 class="desk-panel-title">Macro V2 · evidenze disponibili</h2>'+
   '<p>Almeno una fonte G8 non è verificabile. Restano visibili le osservazioni Macro e Rates nelle rispettive sezioni; non si pubblicano valori sostitutivi arbitrari.</p>';
  return;
 }
 const today=romeTodayIso();
 // The Rates addon is the pre-existing governance layer for approved
 // EUR/CHF dated-futures context and NZD bank-bill/OCR scenarios. Never
 // manufacture OIS quotes from a blank operational 6M slot.
 const research=window.GMFQ_OIS_RESEARCH_V1;
 const indicative=research?.indicativeSixMonth?.(ois,today)||{};
 const nzdScenario=research?.scenarioSixMonth?.(ois,nzdProxy,today)||{};
 const safeRate=x=>num(x)!==null?fmt(x,2)+'%':'n.d.';
 const card=ccy=>{
   const growth=first.find(x=>x.currency===ccy);
   const revised=gdp.records.filter(x=>x.currency===ccy&&x.stage_order>0&&x.publisher_release_day<=today)
      .sort((a,b)=>a.publisher_release_day.localeCompare(b.publisher_release_day)).at(-1);
   const observed=revised||growth, heat=macro.currencies[ccy],rate=rates[ccy],policy=ois.currencies[ccy];
   const gdpKnown=/^2026Q2$/.test(observed?.reference_quarter||'')&&
     /^\d{4}-\d{2}-\d{2}$/.test(observed.publisher_release_day)&&
     observed.publisher_release_day<=today&&num(observed.reported_value)!==null;
   let gdpValue='n.d.';
   if(gdpKnown){
     const raw=observed.reported_value;
     // United States headline is annualized. Convert to nonannualized QoQ
     // purely for the descriptive line, not as a comparable model feature.
     const qoq=observed.reported_unit==='PERCENT_SAAR_ANNUALIZED'?
       100*(Math.pow(1+raw/100,1/4)-1):raw;
     gdpValue=fmt(qoq,2)+'% QoQ'+
       (observed.reported_unit==='PERCENT_SAAR_ANNUALIZED'?' · da SAAR':'');
   }
   const field=k=>{const x=heat?.[k],y=macroThermometerObservation(x);
     return y?fmt(y.value,2)+'% · '+htmlEscape(y.period):'n.d.';};
   const d=rate?.date,rateRecent=fresh(d,5);
   const market2y=secondary2YReading(secondary2y,rates,ccy);
   const p=policy?.horizons?.['6m'],policyAsOf=policy?.as_of||'';
   const direct=policy?.operational_status==='GREEN_OFFICIAL'&&
     policy.official_status==='ACTIVE'&&policy.quality==='OFFICIAL_CERTIFIED'&&
     fresh(policyAsOf,4)&&num(p?.rate)!==null;
   const estimated=policy?.operational_status==='GREEN_ESTIMATED'&&
     fresh(policyAsOf,5)&&num(p?.rate)!==null;
   const secondary=['EUR','CHF'].includes(ccy)?indicative[ccy]:
     ccy==='NZD'?nzdScenario.NZD:null;
   const value=direct||estimated?p.rate:
     secondary?.pair_effect==='NONE'&&secondary.is_official_ois===false&&
     fresh(secondary.quote_as_of,5)?secondary.value:null;
   const grade=direct?'UFFICIALE CERTIFICATO':
     estimated?'STIMA · FUTURES':
     num(value)!==null&&ccy==='NZD'?'SCENARIO · BANK BILL–OCR':
     num(value)!==null?'STIMA · FUTURES INDICATIVI':'FONTE NON VERIFICATA';
   const effective6mAsOf=direct||estimated?policyAsOf:
     num(value)!==null?secondary.quote_as_of:policyAsOf;
   const six=safeRate(value);
   return '<article class="gmfq-macro-v2-country" data-ccy="'+ccy+
      '" data-growth-period="'+htmlEscape(observed?.reference_quarter||'')+
      '" data-rates-date="'+htmlEscape(d||'')+
      '" data-ois-quality="'+htmlEscape(grade)+
      '" data-secondary2y-tier="'+(market2y?'SECONDARY_OBSERVED_NOT_OFFICIAL':'NONE')+
      '" data-secondary2y-date="'+htmlEscape(market2y?.date||'')+'">'+
     '<strong>'+FLAG[ccy]+' '+ccy+'</strong>'+
     '<p><b>Growth</b> '+gdpValue+' <small>'+htmlEscape(observed?.reference_quarter||'')+
       ' · web '+htmlEscape(observed?.publisher_release_day||'')+
       (revised?' · revisione':' · prima stima')+'</small></p>'+
     '<p><b>Inflazione</b> '+field('inflation')+
       ' <b>Disoccupazione</b> '+field('labour')+'</p>'+
     '<p><b>2Y ufficiale</b> '+safeRate(rate['2Y'])+' <small>'+htmlEscape(d||'')+
       (rateRecent?'':' · STORICO')+'</small>'+
       ' <b>6M monetario</b> '+six+' <small>'+htmlEscape(effective6mAsOf)+
       ' · '+htmlEscape(grade)+'</small></p>'+
       (market2y?'<p><b>2Y riferimento mercato</b> '+safeRate(market2y.value)+
         ' <small>'+htmlEscape(market2y.date)+' · '+(market2y.stale?'STORICO':'recente')+
         ' · NON ufficiale · '+market2y.sourceCount+' fonti, dispersione '+
         safeRate(market2y.min)+'–'+safeRate(market2y.max)+
         ' · nessuno spread/score</small></p>':'')+'</article>';
 };
 const style=doc.createElement('style');
 style.id='gmfq-macro-v2-current-style';
 style.textContent='#gmfq-macro-v2-current-evidence{margin:0 0 14px;padding:14px 16px;min-width:0}'+
  '#gmfq-macro-v2-current-evidence p{font:12px/1.55 Arial,sans-serif;color:#bed1de;margin:6px 0;overflow-wrap:anywhere}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-intro{color:#e4d3a5;font-size:12px}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-countries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:11px 0}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-country{min-width:0;background:#0b2232;border:1px solid #294557;border-radius:5px;padding:9px 11px}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-country>strong{color:#e3ebf3;font:600 13px Arial,sans-serif}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-country b{color:#d9e6ef;font-weight:600;margin-right:3px}'+
  '#gmfq-macro-v2-current-evidence .gmfq-macro-v2-country small{color:#9db6c8;font-size:10px}'+
  '@media(max-width:680px){#gmfq-macro-v2-current-evidence .gmfq-macro-v2-countries{grid-template-columns:1fr}}';
 doc.head.appendChild(style);
 panel.dataset.status='OBSERVED_RESEARCH_CONTEXT';
 panel.dataset.currencyCount='8';
 panel.dataset.macroScoreEffect='NONE';
 panel.dataset.pairRankEffect='NONE';
 panel.innerHTML='<h2 class="desk-panel-title">Macro V2 · quadro osservato delle 8 economie</h2>'+
  '<p class="gmfq-macro-v2-intro">Growth, inflazione, lavoro e front-end monetario con date distinte. Queste evidenze NON aggiornano i 24 punteggi storici del 25/09 né classificano le 28 coppie.</p>'+
  '<div class="gmfq-macro-v2-countries">'+FX.map(card).join('')+'</div>'+
  '<p>Growth: ultime rilevazioni Q2 2026 documentate nel dossier web dei primi comunicati, con revisioni EUR/GBP quando già pubblicate; non è un archivio PIT completo. Le stime 6M non sono OIS ufficiali. I dati economici possono riferirsi a mesi diversi. Nessun segnale FX o promozione al modello.</p>';
}

function onFrameLoad(){
 let doc;try{doc=frame.contentDocument}catch(_){return}
 if(!doc?.body||mountedDocuments.has(doc))return;
 mountedDocuments.add(doc);
 if(!home()){
   if(route()==='cross')mountCrossGold(doc).catch(e=>console.warn('[GMFQ Cross-Asset Gold WITHHELD]',e));
   if(route()==='cross')mountCrossRisk(doc).catch(e=>console.warn('[GMFQ Cross-Asset Risk WITHHELD]',e));
   if(route()==='tassi'){enhanceRatesDetail(doc);focusRatesSection(doc);applyMarketResearch(doc).catch(e=>console.warn('[GMFQ market pricing WITHHELD]',e))}
   if(route()==='banche')mountCentralBankFirstReading(doc).catch(e=>console.warn('[GMFQ CB first reading WITHHELD]',e));
   if(route()==='cot')mountCotFirstReading(doc).catch(e=>console.warn('[GMFQ COT first reading WITHHELD]',e));
   if(route()==='macro')mountMacroSourceLens(doc).catch(e=>console.warn('[GMFQ Macro source lens WITHHELD]',e));
   if(route()==='macro')mountMacroV2CurrentEvidence(doc).catch(e=>console.warn('[GMFQ Macro V2 context source unavailable]',e));
   if(route()==='valute')mountValuteSourceCompass(doc).catch(e=>console.warn('[GMFQ Valute source compass WITHHELD]',e));
   if(route()==='coppie')mountPairResearch(doc).catch(e=>console.warn('[GMFQ pair research WITHHELD]',e));
   if(route()==='coppie')mountPairRankedList(doc).catch(e=>console.warn('[GMFQ pair ranking WITHHELD]',e));
   if(route()==='screener'){
    mountScreenerPairBridge(doc);
    mountScreenerBlockers(doc).catch(e=>console.warn('[GMFQ Screener blockers WITHHELD]',e));
   }
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
