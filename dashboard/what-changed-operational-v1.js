(()=>{
'use strict';
const FLAGS={USD:'🇺🇸',EUR:'🇪🇺',GBP:'🇬🇧',JPY:'🇯🇵',CHF:'🇨🇭',CAD:'🇨🇦',AUD:'🇦🇺',NZD:'🇳🇿',GLOBAL:'🌐'};
const IMP={HIGH:3,MEDIUM:2,LOW:1};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function css(){
 if(document.getElementById('gmfq-what-changed-operational-style'))return;
 const s=document.createElement('style');s.id='gmfq-what-changed-operational-style';s.textContent=`
 .wcOp{padding:22px 20px 38px;color:#e8eef8;font-family:Inter,system-ui,sans-serif}.wcHero{border:1px solid rgba(110,158,220,.2);background:linear-gradient(135deg,rgba(18,43,78,.95),rgba(9,17,31,.98));border-radius:18px;padding:20px;margin-bottom:16px}.wcEye{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#91b9ec;font-weight:850}.wcTitle{font-size:25px;font-weight:880;line-height:1.08;margin:7px 0}.wcSub{font-size:13px;color:#9baac0;line-height:1.5;max-width:900px}.wcStats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0 18px}.wcStat{background:#101a2a;border:1px solid rgba(135,160,195,.16);border-radius:12px;padding:11px 12px}.wcStat span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:#8194af;font-weight:800}.wcStat b{display:block;font-size:18px;margin-top:4px}.wcSection{font-size:11px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#8ca7c9;margin:18px 0 10px}.wcGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.wcCard{background:#101a2a;border:1px solid rgba(135,160,195,.16);border-radius:15px;padding:15px;min-width:0}.wcCard[data-priority="high"]{border-color:rgba(89,164,255,.30);background:linear-gradient(145deg,rgba(18,31,51,.98),rgba(12,22,37,.98))}.wcTop{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.wcCcy{font-size:16px;font-weight:900}.wcAs{font-size:11px;color:#8396b2;white-space:nowrap}.wcHeadline{font-size:15px;font-weight:800;line-height:1.35;margin:9px 0 7px}.wcDetail{font-size:12px;color:#a9b6c9;line-height:1.45}.wcTags{margin-top:9px}.wcTag{display:inline-flex;align-items:center;border:1px solid rgba(115,145,185,.18);border-radius:999px;padding:3px 7px;font-size:9px;font-weight:800;letter-spacing:.04em;color:#a9bdd8;margin:0 5px 4px 0}.wcTagA{color:#a9e6bf;border-color:rgba(86,185,128,.22);background:rgba(86,185,128,.06)}.wcTagEst{color:#e3c587;border-color:rgba(225,175,79,.22);background:rgba(225,175,79,.06)}.wcFoot{margin-top:15px;border-radius:11px;padding:10px 12px;border:1px solid rgba(125,150,185,.14);background:rgba(255,255,255,.018);font-size:11px;color:#8fa0b8;line-height:1.45}@media(max-width:720px){.wcOp{padding:15px 12px 28px}.wcGrid{grid-template-columns:1fr}.wcStats{grid-template-columns:1fr}.wcHero{padding:16px}.wcTitle{font-size:21px}}
 `;document.head.appendChild(s);
}
function sortItems(items){
 return [...items].sort((a,b)=>{
   const ad=String(a?.as_of||''),bd=String(b?.as_of||'');if(ad!==bd)return bd.localeCompare(ad);
   const ai=IMP[a?.importance]||0,bi=IMP[b?.importance]||0;if(ai!==bi)return bi-ai;
   return String(a?.ccy||'').localeCompare(String(b?.ccy||''));
 });
}
function card(x){
 const qual=String(x.quality||'');
 const cls=qual.includes('OFFICIAL')?'wcTagA':qual.includes('ESTIMATED')?'wcTagEst':'';
 return `<article class="wcCard" data-priority="${String(x.importance||'').toLowerCase()}" data-ccy="${esc(x.ccy||'GLOBAL')}"><div class="wcTop"><div class="wcCcy">${FLAGS[x.ccy]||FLAGS.GLOBAL} ${esc(x.ccy||'GLOBAL')}</div><div class="wcAs">${esc(x.as_of||'—')}</div></div><div class="wcHeadline">${esc(x.title||'Segnale validato')}</div><div class="wcDetail">${esc(x.detail||'')}</div><div class="wcTags"><span class="wcTag">${esc(x.category||'SIGNAL')}</span><span class="wcTag ${cls}">${esc(qual||'QUALITY N/A')}</span><span class="wcTag">CONF ${esc(x.confidence||'—')}</span></div></article>`;
}
function html(data){
 const rows=sortItems(data.items||[]);
 const asof=String(data.content_as_of||'');
 const current=rows.filter(x=>String(x.as_of||'').startsWith(asof));
 const recent=rows.filter(x=>!String(x.as_of||'').startsWith(asof));
 const high=current.filter(x=>x.importance==='HIGH').length;
 return `<div class="wcOp" data-gmfq-operational="wow"><div class="wcHero"><div class="wcEye">Validated change detection</div><div class="wcTitle">What Changed operativo</div><div class="wcSub">Mostra solo cambiamenti provenienti dai layer validati correnti. Non è un feed generico di notizie e non aggiunge interpretazioni non presenti nei dati sorgente.</div></div><div class="wcStats"><div class="wcStat"><span>Content as-of</span><b>${esc(asof||'—')}</b></div><div class="wcStat"><span>Cambiamenti correnti</span><b>${current.length}</b></div><div class="wcStat"><span>High importance</span><b>${high}</b></div></div><div class="wcSection">Cambiato adesso</div><div class="wcGrid">${current.length?current.map(card).join(''):'<div class="wcCard"><div class="wcDetail">Nessun nuovo cambiamento validato per la data corrente.</div></div>'}</div><div class="wcSection">Contesto validato precedente</div><div class="wcGrid">${recent.length?recent.map(card).join(''):'<div class="wcCard"><div class="wcDetail">Nessun contesto precedente disponibile.</div></div>'}</div><div class="wcFoot">Source: ${esc(data.schema||'GMFQ_NEWS_PULSE_OPERATIONAL_V1')} · generated ${esc(data.generated_at_utc||'—')} · Core effect: NONE.</div></div>`;
}
let cache=null,rendering=false;
async function load(){if(cache)return cache;const r=await fetch('live_data/sections/NEWS_PULSE_OPERATIONAL.json',{cache:'no-store'});if(!r.ok)throw new Error(`NEWS_PULSE_OPERATIONAL:${r.status}`);cache=await r.json();return cache;}
async function render(){
 if(rendering)return;rendering=true;css();
 try{const data=await load();const el=document.getElementById('wow');if(el&&!el.querySelector('[data-gmfq-operational="wow"]')){el.innerHTML=html(data);window.GMFQ_WHAT_CHANGED_OPERATIONAL={status:'ACTIVE',schema:'GMFQ_WHAT_CHANGED_OPERATIONAL_UI_V1',content_as_of:data.content_as_of||null,items:(data.items||[]).length,core_effect:'NONE'};}}
 catch(err){console.error('what-changed-operational',err);window.GMFQ_WHAT_CHANGED_OPERATIONAL={status:'ERROR',error:String(err),core_effect:'NONE'};}
 finally{rendering=false;}
}
const obs=new MutationObserver(()=>{const el=document.getElementById('wow');if(el&&!el.querySelector('[data-gmfq-operational="wow"]'))render();});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{render();obs.observe(document.body,{childList:true,subtree:true});},{once:true});else{render();obs.observe(document.body,{childList:true,subtree:true});}
})();
