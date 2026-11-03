/* G8 study continuity v1: additive, read-only. Do not change certified feeds, scores or FX signals. */
(()=>{
'use strict';
const FX=['USD','EUR','GBP','JPY','AUD','CAD','NZD','CHF'];
const FLAG={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',AUD:'🇦🇺',CAD:'🇨🇦',NZD:'🇳🇿',CHF:'🇨🇭'};
const root='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/main/live_data/sections/';
const frame=document.getElementById('gmfq-page');
if(!frame)return;
const numeric=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
const fmt=v=>numeric(v)===null?'—':v.toFixed(2)+'%';
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const iso=d=>/^20\d\d-\d\d-\d\d$/.test(d||'');
const urls=['NATIVE_RATES_DATA.json','OIS_OPERATIONAL_VIEW.json'];
const get=async name=>{const res=await fetch(root+name+'?t='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error(name+': '+res.status);return res.json()};
const currentRoute=()=>location.hash.split('?')[0].replace(/^#\/?/,'')||'home';
function points(ccy,rates,ois){
 const o=ois?.currencies?.[ccy]||{},r=rates?.[ccy]||{};
 const policy=numeric(o.policy_rate),base=numeric(r['2Y']);
 return ['3m','6m','12m'].map((tenor,i)=>{
  const h=o.horizons?.[tenor]||{};
  const official=numeric(h.rate);
  if(official!==null&&o.operational_status==='GREEN_OFFICIAL')return {v:official,tier:'CERTIFICATO',date:o.as_of||'',source:o.source||''};
  const price=numeric(h.futures_price);
  if(price!==null&&price>70&&price<110)return {v:100-price,tier:'PROXY FUTURES · NON OIS',date:h.quote_as_of||o.as_of||'',source:o.source||'Prezzo futures'};
  if(official!==null)return {v:official,tier:'STIMA NEL FEED',date:o.as_of||'',source:o.source||''};
  // Zero-slope policy scenario is an explicit neutral assumption, NOT a market quotation.
  if(policy!==null)return {v:policy,tier:'SCENARIO FLAT · NON PRICING',date:o.as_of||'',source:'Ipotesi: tasso policy invariato; nessun repricing inferito'};
  return {v:null,tier:'NON CALCOLABILE',date:'',source:''};
 });
}
function gov(ccy,rates){
 const r=rates?.[ccy]||{};
 return {y2:numeric(r['2Y']),y10:numeric(r['10Y']),date:r.date||'',quality:r.quality||'NON CLASSIFICATO'};
}
function chart(data){
 const v=data.map(x=>x.v);
 if(v.some(x=>numeric(x)===null))return '<p>Serie non ricostruibile dai riferimenti disponibili.</p>';
 const low=Math.min(...v)-.12,high=Math.max(...v)+.12,span=high-low||1;
 const xx=i=>64+i*310, yy=x=>28+(high-x)/span*145;
 const poly=v.map((y,i)=>xx(i)+','+yy(y).toFixed(1)).join(' ');
 return '<svg viewBox="0 0 760 240" role="img" aria-label="Curva monetaria 3M 6M 12M con segmenti e qualità delle fonti" style="display:block;width:100%;height:auto;max-height:250px">'+
  [0,1,2,3].map(i=>{const y=28+i*145/3;return '<line x1="52" x2="700" y1="'+y+'" y2="'+y+'" stroke="#294b5e"/><text x="46" y="'+(y+4)+'" text-anchor="end" fill="#9eb8c9" font-size="11">'+(high-i*span/3).toFixed(2)+'%</text>'}).join('')+
  '<polyline points="'+poly+'" fill="none" stroke="#65bce8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'+
  v.map((y,i)=>'<circle cx="'+xx(i)+'" cy="'+yy(y)+'" r="5" fill="#65bce8"/><text x="'+xx(i)+'" y="'+(yy(y)-12)+'" text-anchor="middle" fill="#e8f2f7" font-size="16">'+y.toFixed(2)+'%</text><text x="'+xx(i)+'" y="205" text-anchor="middle" fill="#acc4d1" font-size="14">'+['3M','6M','12M'][i]+'</text>').join('')+'</svg>';
}
function render(doc,rates,ois){
 if(!doc?.body)return;
 const route=currentRoute();
 if(!['home','tassi','macro','coppie','screener','valute','banche','cross','cot'].includes(route))return;
 const main=doc.querySelector('.desk-main')||doc.querySelector('main');
 if(!main)return;
 let host=doc.getElementById('gmfq-continuity-study-v1');
 if(!host){host=doc.createElement('section');host.id='gmfq-continuity-study-v1';host.className='desk-panel';host.setAttribute('aria-label','Copertura G8: livelli e curve di studio');main.prepend(host);}
 const sel=doc.createElement('style');sel.textContent=
  '#gmfq-continuity-study-v1{margin:0 0 16px;padding:14px 16px;background:#0a1e2d;border:1px solid #385a70;border-radius:8px;color:#e1ebf2;min-width:0}'+
  '#gmfq-continuity-study-v1 h2{margin:0 0 7px;font:650 18px/1.4 Georgia,serif;color:#eef5fa}'+
  '#gmfq-continuity-study-v1 p{margin:6px 0 10px;font:12px/1.55 Arial,sans-serif;color:#b8cbd8}'+
  '#gmfq-continuity-study-v1 .gmfq-cont-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:12px 0}'+
  '#gmfq-continuity-study-v1 button{cursor:pointer;background:#132e40;color:#dbeaf3;border:1px solid #365568;border-radius:6px;padding:8px 4px;font:600 12px Arial}'+
  '#gmfq-continuity-study-v1 button[aria-pressed=true]{border-color:#76c3ee;background:#244358}'+
  '#gmfq-continuity-study-v1 .gmfq-cont-meta{display:flex;gap:8px 20px;flex-wrap:wrap;font:12px/1.6 Arial}'+
  '#gmfq-continuity-study-v1 .gmfq-cont-meta strong{color:#f3f7fa}'+
  '#gmfq-continuity-study-v1 .gmfq-cont-trace{font:11px/1.55 Arial;color:#d1be8d;margin-top:8px}'+
  '#gmfq-continuity-study-v1 .gmfq-cont-trace div{margin:3px 0}'+
  '@media(max-width:550px){#gmfq-continuity-study-v1{padding:12px}#gmfq-continuity-study-v1 .gmfq-cont-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}';
 doc.head.appendChild(sel);
 const all=FX.map(c=>({c,points:points(c,rates,ois),gov:gov(c,rates)}));
 let selected='USD';
 const paint=()=>{
  const row=all.find(x=>x.c===selected);
  host.innerHTML='<h2>G8 · curve e rendimenti sempre consultabili</h2>'+
   '<p>Livelli ufficiali dove disponibili; altrimenti futures indicativi o scenario flat dichiarato. Le stime non sono OIS osservati e non modificano segnali, score o backtest.</p>'+
   '<div class="gmfq-cont-grid">'+all.map(x=>'<button type="button" data-code="'+x.c+'" aria-pressed="'+(x.c===selected)+'">'+FLAG[x.c]+' '+x.c+'</button>').join('')+'</div>'+
   chart(row.points)+
   '<div class="gmfq-cont-meta"><span><strong>2Y governativo:</strong> '+fmt(row.gov.y2)+'</span><span><strong>10Y governativo:</strong> '+fmt(row.gov.y10)+'</span><span><strong>Data rendimenti:</strong> '+safe(row.gov.date||'non presente')+'</span></div>'+
   '<div class="gmfq-cont-trace">'+row.points.map((p,i)=>'<div>'+['3M','6M','12M'][i]+': '+fmt(p.v)+' · '+safe(p.tier)+' · '+safe(p.date||'senza data')+'</div>').join('')+
   '<div>2Y/10Y: '+safe(row.gov.quality)+' · fonte NATIVE_RATES_DATA; i valori storici non sono aggiornamenti odierni.</div></div>';
  host.querySelectorAll('button[data-code]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.code;paint()}));
 };
 paint();
 host.dataset.coverage=String(all.filter(x=>x.points.every(p=>numeric(p.v)!==null)).length)+'/8';
 host.dataset.signalEffect='NONE';
}
async function mount(){
 const doc=frame.contentDocument;if(!doc?.body)return;
 const settled=await Promise.allSettled(urls.map(get));
 if(frame.contentDocument!==doc)return;
 const rates=settled[0].status==='fulfilled'?settled[0].value:null;
 const ois=settled[1].status==='fulfilled'?settled[1].value:null;
 if(!rates&&!ois)return;
 render(doc,rates,ois);
}
frame.addEventListener('load',()=>{mount().catch(e=>console.warn('[G8 continuity]',e))});
if(frame.contentDocument?.readyState==='complete')mount().catch(e=>console.warn('[G8 continuity]',e));
})();