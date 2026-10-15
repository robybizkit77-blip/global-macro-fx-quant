(()=>{
'use strict';
const CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'];
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿'};
const IMP={HIGH:3,MEDIUM:2,LOW:1};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=v=>Number.isFinite(Number(v))?Number(v):null;
const fmt=(v,d=1)=>num(v)==null?'—':Number(v).toFixed(d);
const bp=v=>num(v)==null?'—':`${v>0?'+':''}${Number(v).toFixed(1)} bp`;
const pct=v=>num(v)==null?'—':`${Number(v).toFixed(1)}%`;

function css(){
 if(document.getElementById('gmfq-top-themes-operational-style'))return;
 const s=document.createElement('style');s.id='gmfq-top-themes-operational-style';s.textContent=`
 .ttOp{padding:22px 20px 38px;color:#e8eef8;font-family:Inter,system-ui,sans-serif}.ttHero{border:1px solid rgba(114,159,220,.2);background:linear-gradient(135deg,rgba(20,45,80,.95),rgba(9,17,31,.98));border-radius:18px;padding:20px;margin-bottom:16px}.ttEye{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#91b9ec;font-weight:850}.ttTitle{font-size:25px;font-weight:880;line-height:1.08;margin:7px 0}.ttSub{font-size:13px;color:#9baac0;line-height:1.5;max-width:900px}.ttGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.ttCard{background:#101a2a;border:1px solid rgba(135,160,195,.16);border-radius:15px;padding:15px;min-width:0}.ttCard[data-tier="top"]{border-color:rgba(89,164,255,.28);background:linear-gradient(145deg,rgba(18,31,51,.98),rgba(12,22,37,.98))}.ttTop{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.ttCcy{font-size:16px;font-weight:900}.ttAs{font-size:11px;color:#8396b2;white-space:nowrap}.ttHeadline{font-size:15px;font-weight:800;line-height:1.35;margin:9px 0 7px}.ttDetail{font-size:12px;color:#a9b6c9;line-height:1.45}.ttSection{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#7fa5d6;font-weight:850;margin:12px 0 6px}.ttRow{display:grid;grid-template-columns:1fr 1fr;gap:8px}.ttMini{border:1px solid rgba(130,155,190,.12);border-radius:10px;padding:8px 9px;background:rgba(255,255,255,.018);font-size:11px;color:#aeb9c9;line-height:1.4}.ttMini b{color:#e7edf6}.ttPath{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.ttBucket{border-radius:9px;padding:8px;background:rgba(63,112,178,.08);border:1px solid rgba(78,130,200,.13);font-size:10px;color:#93a7c2}.ttBucket b{display:block;color:#e3ebf7;font-size:12px;margin-top:2px}.ttTag{display:inline-flex;align-items:center;border:1px solid rgba(115,145,185,.18);border-radius:999px;padding:3px 7px;font-size:9px;font-weight:800;letter-spacing:.04em;color:#a9bdd8;margin:7px 5px 0 0}.ttTagOfficial{color:#a9e6bf;border-color:rgba(86,185,128,.22);background:rgba(86,185,128,.06)}.ttTagEst{color:#e3c587;border-color:rgba(225,175,79,.22);background:rgba(225,175,79,.06)}.ttFoot{margin-top:15px;border-radius:11px;padding:10px 12px;border:1px solid rgba(125,150,185,.14);background:rgba(255,255,255,.018);font-size:11px;color:#8fa0b8;line-height:1.45}.ttDivider{margin:18px 0 10px;font-size:11px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#8ca7c9}@media(max-width:720px){.ttOp{padding:15px 12px 28px}.ttGrid{grid-template-columns:1fr}.ttHero{padding:16px}.ttTitle{font-size:21px}.ttRow{grid-template-columns:1fr}.ttPath{grid-template-columns:repeat(3,minmax(0,1fr))}}
 `;document.head.appendChild(s);
}
function macroMetric(x){
 if(!x||x.status==='WITHHELD')return {label:'Non disponibile',value:'—',as_of:null};
 return {label:[x.temperature_label,x.direction,x.acceleration].filter(Boolean).join(' · '),value:fmt(x.latest_value,2),as_of:x.as_of||null};
}
function derive(news,macro,ois){
 const signals=new Map();
 for(const item of (news.items||[])) if(item?.ccy&&CCYS.includes(item.ccy)&&!signals.has(item.ccy))signals.set(item.ccy,item);
 const rows=CCYS.map(ccy=>{
   const sig=signals.get(ccy)||null;
   const m=macro.currencies?.[ccy]||{};
   const p=ois.currencies?.[ccy]||{};
   const inflation=macroMetric(m.inflation),labour=macroMetric(m.labour);
   const hz={};
   for(const k of ['3m','6m','12m']){
     const x=p.horizons?.[k]||{};
     hz[k]={rate:num(x.rate),policy_delta_bp:num(x.policy_delta_bp),change_1d_bp:num(x.change_1d_bp),change_1w_bp:num(x.change_1w_bp)};
   }
   const asof=[sig?.as_of,p.as_of,inflation.as_of,labour.as_of].filter(Boolean).sort().at(-1)||null;
   return {ccy,signal:sig,inflation,labour,pricing:{as_of:p.as_of||null,policy_rate:num(p.policy_rate),quality:p.quality||'UNKNOWN',official_status:p.official_status||null,operational_status:p.operational_status||null,direction_vs_policy:p.direction_vs_policy||null,horizons:hz,market_direction_proxy:p.market_direction_proxy||null},as_of:asof};
 });
 rows.sort((a,b)=>{
   const ad=a.signal?.as_of||'',bd=b.signal?.as_of||'';if(ad!==bd)return bd.localeCompare(ad);
   const ai=IMP[a.signal?.importance]||0,bi=IMP[b.signal?.importance]||0;if(ai!==bi)return bi-ai;
   return a.ccy.localeCompare(b.ccy);
 });
 return rows;
}
function macroBox(label,x){return `<div class="ttMini"><b>${label}</b><br>${esc(x.label)} · valore ${esc(x.value)}${x.as_of?`<br><span>as-of ${esc(x.as_of)}</span>`:''}</div>`;}
function pathBox(k,x){return `<div class="ttBucket">${k.toUpperCase()}<b>${x.rate==null?'—':`${fmt(x.rate,3)}%`}</b>vs policy ${bp(x.policy_delta_bp)}<br>Δ1D ${bp(x.change_1d_bp)} · Δ1W ${bp(x.change_1w_bp)}</div>`;}
function card(row,tier,rank){
 const s=row.signal;
 const title=s?.title||`${row.ccy}: contesto strutturale · nessun nuovo change validato`;
 const detail=s?.detail||'Nessun nuovo segnale operativo nel News Pulse corrente: mostrare solo Macro e market pricing, senza inventare narrativa.';
 const q=row.pricing.quality||'';const cls=q.includes('OFFICIAL')?'ttTagOfficial':'ttTagEst';
 const proxy=row.pricing.market_direction_proxy;
 return `<article class="ttCard" data-tier="${tier}" data-ccy="${row.ccy}"><div class="ttTop"><div class="ttCcy">${FLAGS[row.ccy]} ${row.ccy}${tier==='top'?` · #${rank}`:''}</div><div class="ttAs">${esc(row.as_of||'—')}</div></div><div class="ttHeadline">${esc(title)}</div><div class="ttDetail">${esc(detail)}</div><div class="ttSection">Macro</div><div class="ttRow">${macroBox('Inflazione',row.inflation)}${macroBox('Lavoro',row.labour)}</div><div class="ttSection">Market pricing</div><div class="ttPath">${pathBox('3m',row.pricing.horizons['3m'])}${pathBox('6m',row.pricing.horizons['6m'])}${pathBox('12m',row.pricing.horizons['12m'])}</div><span class="ttTag ${cls}">${esc(row.pricing.operational_status||'UNKNOWN')}</span><span class="ttTag">POLICY ${row.pricing.policy_rate==null?'—':pct(row.pricing.policy_rate)}</span>${proxy?'<span class="ttTag ttTagEst">DIRECTIONAL PROXY · NON OIS</span>':''}${s?`<span class="ttTag">${esc(s.category||'SIGNAL')} · ${esc(s.importance||'')}</span>`:''}</article>`;
}
function html(rows,news,ois){
 const top=rows.slice(0,4),rest=rows.slice(4);
 return `<div class="ttOp" data-gmfq-operational="themes"><div class="ttHero"><div class="ttEye">Macro → Market Pricing · G8</div><div class="ttTitle">Top Themes operativo</div><div class="ttSub">Ordine deterministico per ultimo segnale validato e importanza. Non è un ranking trade e non modifica score, bias o sizing: serve a mostrare cosa sta cambiando e se il pricing lo accompagna.</div></div><div class="ttGrid">${top.map((r,i)=>card(r,'top',i+1)).join('')}</div><div class="ttDivider">Contesto G8 rimanente</div><div class="ttGrid">${rest.map(r=>card(r,'context','')).join('')}</div><div class="ttFoot">News Pulse content as-of ${esc(news.content_as_of||'—')} · OIS operational ${esc(ois.summary?.operational_green||0)}/8 GREEN · NULL nei Δ non viene mai interpretato come 0. Qualità OFFICIAL ed ESTIMATED restano visivamente e semanticamente separate.</div></div>`;
}
let cache=null,rendering=false;
async function load(){
 if(cache)return cache;
 const urls=['live_data/sections/NEWS_PULSE_OPERATIONAL.json','live_data/sections/MACRO_THERMOMETER_DATA.json','live_data/sections/OIS_OPERATIONAL_VIEW.json'];
 const [news,macro,ois]=await Promise.all(urls.map(async u=>{const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(`${u}:${r.status}`);return r.json();}));
 cache={news,macro,ois};return cache;
}
async function render(){
 if(rendering)return;rendering=true;css();
 try{const {news,macro,ois}=await load();const el=document.getElementById('themes');if(el&&!el.querySelector('[data-gmfq-operational="themes"]')){const rows=derive(news,macro,ois);el.innerHTML=html(rows,news,ois);window.GMFQ_TOP_THEMES_OPERATIONAL={status:'ACTIVE',schema:'GMFQ_TOP_THEMES_OPERATIONAL_UI_V1',currencies:rows.length,top:rows.slice(0,4).map(x=>x.ccy),content_as_of:news.content_as_of,core_effect:'NONE'};}}
 catch(err){console.error('top-themes-operational',err);window.GMFQ_TOP_THEMES_OPERATIONAL={status:'ERROR',error:String(err),core_effect:'NONE'};}
 finally{rendering=false;}
}
const obs=new MutationObserver(()=>{const el=document.getElementById('themes');if(el&&!el.querySelector('[data-gmfq-operational="themes"]'))render();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{render();obs.observe(document.body,{childList:true,subtree:true});},{once:true});else{render();obs.observe(document.body,{childList:true,subtree:true});}
})();